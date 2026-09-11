"""Endpoint REST pour l'agent Vector — tool calling avec traces enrichies."""
import json
import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.ai.agent_loop import _make_tool_summary, run_agent
from app.ai.providers.openai import OpenAIProvider
from app.ai.vector_tools import TOOL_HANDLERS, execute_tool
from app.api.deps import get_current_user
from app.core.demo_guard import ensure_demo_enabled
from app.core.limiter import limiter
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.agent import (
    AgentArtifacts,
    AgentChatRequest,
    AgentChatResponse,
    AgentRunToolRequest,
    ToolCallTrace,
    WebChatRequest,
)
from app.services.web_search import answer_web_question_stream

router = APIRouter(prefix="/agent", tags=["agent"])

# OpenAIProvider partagé (instance unique réutilisée, même pattern que rag.py)
_provider = OpenAIProvider()


@router.post(
    "/chat",
    response_model=AgentChatResponse,
    dependencies=[Depends(ensure_demo_enabled)],
)
@limiter.limit("10/minute")
async def agent_chat(
    request: Request,
    payload: AgentChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AgentChatResponse:
    """
    Envoie un message à l'agent Vector et reçoit sa réponse enrichie.

    L'agent peut appeler plusieurs outils (list_user_datasets,
    get_dataset_summary, generate_dashboard) avant de produire sa réponse
    finale. La réponse expose pour chaque appel d'outil : son nom, un
    résumé lisible du résultat, sa durée et son statut. Les artefacts
    générés (dashboard_id) sont aussi exposés pour permettre au frontend
    d'afficher un CTA « Ouvrir le dashboard ».
    """
    # NEW J49 — conversation_id (deja present dans le schema mais inutilise
    # jusqu'ici) : resout le persona actif de la conversation, si presente.
    # Silencieux si absent/invalide, ne bloque jamais le chat.
    conversation_id: UUID | None = None
    if payload.conversation_id:
        try:
            conversation_id = UUID(payload.conversation_id)
        except ValueError:
            conversation_id = None

    result = await run_agent(
        user_message=payload.message,
        db=db,
        user=current_user,
        attachments=payload.attachments,
        conversation_id=conversation_id,
    )
    return AgentChatResponse(**result)


# =============================================================================
# J41.B — POST /agent/chat-web : question enrichie par recherche web (Tavily)
# =============================================================================


@router.post("/chat-web", dependencies=[Depends(ensure_demo_enabled)])
@limiter.limit("10/minute")
async def agent_chat_web(
    request: Request,
    payload: WebChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Question enrichie par une recherche web live (Tavily), reponse en
    streaming SSE. Meme format d'evenements que les endpoints RAG :

        evt.addEventListener('web_sources', e => {...})
        evt.addEventListener('token', e => append(e.data))
        evt.addEventListener('done', e => {...})
        evt.addEventListener('error', e => {...})
    """

    async def event_generator():
        async for event in answer_web_question_stream(
            question=payload.question,
            provider=_provider,
            max_results=payload.max_results,
        ):
            data = event["data"]
            if not isinstance(data, str):
                data = json.dumps(data, ensure_ascii=False)
            yield {"event": event["event"], "data": data}

    return EventSourceResponse(event_generator())


# =============================================================================
# J20 — POST /agent/run-tool
# Exécution directe d'un outil agentique, SANS passer par le LLM.
# Utilisé par les actions rapides du frontend (formulaires conversationnels).
# =============================================================================


@router.post("/run-tool", response_model=AgentChatResponse)
async def agent_run_tool(
    payload: AgentRunToolRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AgentChatResponse:
    """
    Exécute un outil agentique directement, sans appel LLM.

    Réservé aux workflows où le frontend connaît déjà précisément l'outil
    et ses arguments (ex: clic sur une action rapide après remplissage du
    formulaire). Élimine les hallucinations LLM (UUID tronqué, lien inventé)
    et divise par 5-10 le temps de réponse.

    Réponse identique en structure à /agent/chat pour ne rien casser côté
    frontend : message + tool_calls + artifacts + iterations.
    """
    # 1. Vérifie que l'outil existe avant tout
    if payload.tool_name not in TOOL_HANDLERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Outil inconnu : '{payload.tool_name}'. "
            f"Outils disponibles : {', '.join(sorted(TOOL_HANDLERS.keys()))}",
        )

    # 2. Exécute l'outil avec mesure du temps
    start = time.perf_counter()
    try:
        result = await execute_tool(
            tool_name=payload.tool_name,
            arguments=payload.arguments,
            db=db,
            user=current_user,
        )
    except Exception as e:
        # Erreur Python brute (rare car execute_tool wrap déjà ses exceptions)
        duration_ms = int((time.perf_counter() - start) * 1000)
        trace = ToolCallTrace(
            name=payload.tool_name,
            args=payload.arguments,
            result_summary=f"Erreur d'exécution : {type(e).__name__}",
            status="error",
            duration_ms=duration_ms,
        )
        return AgentChatResponse(
            message=f"Une erreur technique s'est produite : {e}",
            tool_calls=[trace],
            artifacts=None,
            iterations=1,
        )

    duration_ms = int((time.perf_counter() - start) * 1000)

    # 3. Détection erreur "soft" (dict {"error": "..."} sans exception)
    #    Même logique que agent_loop.py ligne 163.
    if isinstance(result, dict) and "error" in result:
        trace = ToolCallTrace(
            name=payload.tool_name,
            args=payload.arguments,
            result_summary=f"Erreur : {str(result['error'])[:120]}",
            status="error",
            duration_ms=duration_ms,
        )
        return AgentChatResponse(
            message=(
                f"L'exécution de {payload.tool_name} a échoué : "
                f"{result['error']}"
            ),
            tool_calls=[trace],
            artifacts=None,
            iterations=1,
        )

    # 4. Succès : on construit une réponse déterministe en français
    summary = _make_tool_summary(payload.tool_name, result)
    trace = ToolCallTrace(
        name=payload.tool_name,
        args=payload.arguments,
        result_summary=summary,
        status="ok",
        duration_ms=duration_ms,
    )

    # 5. Capture des artifacts (même logique que agent_loop.py ligne 177)
    artifacts_dict: dict[str, str] = {}
    if dash_id := result.get("dashboard_id"):
        artifacts_dict["dashboard_id"] = str(dash_id)
    if ds_id := result.get("dataset_id"):
        artifacts_dict["dataset_id"] = str(ds_id)

    artifacts = AgentArtifacts(**artifacts_dict) if artifacts_dict else None

    # 6. Message final déterministe — pas de LLM, pas d'hallucination
    message = _build_deterministic_message(payload.tool_name, result)

    return AgentChatResponse(
        message=message,
        tool_calls=[trace],
        artifacts=artifacts,
        iterations=1,
    )


def _build_deterministic_message(tool_name: str, result: dict) -> str:
    """Construit un message lisible en français à partir du retour de l'outil.

    Remplace ce que faisait le LLM dans /agent/chat (qui pouvait halluciner).
    Réponse 100% prévisible, sans appel API externe.
    """
    if tool_name == "list_user_datasets":
        n = result.get("count", 0)
        if n == 0:
            return "Vous n'avez encore aucun dataset. Uploadez-en un via la page Datasets."
        return (
            f"Vous avez {n} dataset{'s' if n > 1 else ''}. "
            f"Sélectionnez-en un pour lancer une analyse."
        )

    if tool_name == "get_dataset_summary":
        name = result.get("name", "?")
        rows = result.get("rows", "?")
        cols = result.get("columns", "?")
        quality = result.get("quality", 0)
        domain = result.get("domain", "Inconnu")
        return (
            f"Le dataset « {name} » contient {rows} lignes et {cols} colonnes "
            f"(qualité {quality}%, domaine : {domain})."
        )

    # Tous les handlers de dashboard (J16 + J18)
    if tool_name in {
        "generate_dashboard",
        "generate_marketing_dashboard",
        "generate_sales_dashboard",
        "generate_customers_dashboard",
        "generate_trends_dashboard",
    }:
        ds_name = result.get("dataset_name", "?")
        kpi_count = result.get("kpi_count", 0)
        focus_label = result.get("focus_label")
        if focus_label:
            return (
                f"Dashboard **{focus_label}** généré pour « {ds_name} » "
                f"avec {kpi_count} KPIs. Cliquez sur le bouton ci-dessous pour l'ouvrir."
            )
        return (
            f"Dashboard général généré pour « {ds_name} » "
            f"avec {kpi_count} KPIs. Cliquez sur le bouton ci-dessous pour l'ouvrir."
        )

    # Fallback générique
    return f"L'outil {tool_name} a été exécuté avec succès."
