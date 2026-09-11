"""Boucle d'agent Vector — orchestration tool calling avec traces enrichies."""
from __future__ import annotations

import json
import time
import traceback
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.openai import OpenAIProvider
from app.ai.vector_tools import TOOLS_SCHEMA, execute_tool
from app.core.constants import calculate_cost
from app.db.models.conversation import Conversation
from app.db.models.user import User
from app.services.dataset_tools import get_compute_tool_schema
from app.services.datasets import DatasetService
from app.services.image_attachments import build_vision_content_block
from app.services.personas import PersonaService
from app.services.storage import FileStorage

SYSTEM_PROMPT = """Tu es Vector, l'agent IA d'analyse de données du squad A.I. Commandos.

OUTILS DISPONIBLES :
- list_user_datasets : retourne la liste des datasets avec leur UUID, leur nom, et
  matches_for_action (les actions rapides auxquelles chaque dataset correspond)
- get_dataset_summary : retourne le profil détaillé d'un dataset (requiert l'UUID)
- generate_dashboard : génère un dashboard ÉQUILIBRÉ et GÉNÉRAL (requiert l'UUID)
- generate_marketing_dashboard : dashboard MARKETING spécialisé (canaux, conversion)
  Params optionnels : period (7d/30d/90d/all), channel_focus (texte libre)
- generate_sales_dashboard : dashboard VENTES spécialisé (CA, panier, top produits)
  Params optionnels : priority_metric (revenue/basket/volume/conversion),
  granularity (day/week/month/quarter)
- generate_customers_dashboard : dashboard CLIENTS spécialisé (RFM, top N)
  Params optionnels : segmentation (rfm/revenue_only/frequency_only), top_n (10/20/50)
- generate_trends_dashboard : dashboard TENDANCES spécialisé (comparaisons, anomalies)
  Params optionnels : comparison_period (previous_month/previous_quarter/previous_year),
  sensitivity (low/medium/high)

CHOIX DE L'OUTIL DE DASHBOARD :
- "dashboard général", "vue d'ensemble", "KPIs principaux" → generate_dashboard
- "marketing", "canaux", "campagnes", "conversion" → generate_marketing_dashboard
- "ventes", "commercial", "CA", "produits", "vendeurs" → generate_sales_dashboard
- "clients", "segments", "RFM", "valeur client" → generate_customers_dashboard
- "tendances", "anomalies", "comparaison", "évolution" → generate_trends_dashboard

RETOURS DES OUTILS :
- generate_*_dashboard retourne : dashboard_id, dataset_name, kpi_count, focus_label.
  Quand tu réponds, mentionne le focus, le nombre de KPIs et le nom du dataset.
- get_dataset_summary retourne : name, rows, columns, quality, domain.
- list_user_datasets retourne : datasets (liste avec id, name, status, matches_for_action).

WORKFLOW OBLIGATOIRE pour les actions sur dataset :
1. Si l'utilisateur référence un dataset par son NOM (ex: "le fichier BA"),
   tu DOIS d'abord appeler list_user_datasets pour récupérer l'UUID correspondant.
2. JAMAIS inventer un dataset_id. JAMAIS passer un nom à la place d'un UUID.
3. Les UUID ressemblent à : 550e8400-e29b-41d4-a716-446655440000 (36 caractères).
4. Si plusieurs datasets, choisis celui dont le nom correspond le mieux (insensible casse).

WORKFLOW SI ERREUR :
- Si un outil retourne {"error": "..."}, explique le problème à l'utilisateur en français
  en citant le détail de l'erreur (pas un message générique).
- Ne dis JAMAIS "problème technique" sans expliquer ce qui a vraiment échoué.

COMMUNICATION :
- Réponds toujours en français.
- Sois concis : 2 à 4 phrases dans ta réponse finale.
- Quand tu génères un dashboard, mentionne le focus, le nom du dataset et le nombre de KPIs.
- Si l'utilisateur n'a pas de dataset, propose-lui d'en uploader un via la page Datasets."""

MAX_ITERATIONS = 5

# Provider singleton — réutilise le client OpenAI entre les requêtes
_llm = OpenAIProvider()


async def run_agent(
    user_message: str,
    db: AsyncSession,
    user: User,
    attachments: list[dict[str, Any]] | None = None,
    conversation_id: UUID | None = None,
) -> dict[str, Any]:
    """
    Exécute la boucle d'agent Vector avec tool calling.

    attachments (NEW J41+ Feature 3) : images jointes au message (dicts
    ImageAttachmentResponse). Si presentes, le premier message user est
    envoye au LLM en contenu multimodal (texte + image_url) pour la vision.

    conversation_id (NEW J49 — Personas) : si fourni et que la conversation
    (appartenant a `user`) a un persona_id, le system_prompt de ce persona
    remplace SYSTEM_PROMPT, et ses documents/corpus associes enrichissent le
    contexte (RAG). Silencieux si absent/non trouve — ne bloque jamais le chat.

    Returns:
        dict avec les clés :
        - message (str)         : réponse finale en langage naturel
        - tool_calls (list)     : trace de chaque appel d'outil (nom, args,
                                  résumé, statut, durée en ms)
        - artifacts (dict|None) : artefacts générés (dashboard_id, dataset_id)
        - iterations (int)      : nombre d'itérations du loop consommées
    """
    image_attachments = [a for a in (attachments or []) if a.get("type") == "image"]
    if image_attachments:
        user_content: Any = [
            {"type": "text", "text": user_message},
            *[build_vision_content_block(a) for a in image_attachments],
        ]
    else:
        user_content = user_message

    base_prompt = SYSTEM_PROMPT
    persona_rag_context = None

    # NEW J49 — Personas : resout le persona actif de la conversation (si
    # fournie) et bascule sur son system_prompt. Aucune conversation_id ou
    # conversation sans persona_id -> comportement inchange (SYSTEM_PROMPT).
    if conversation_id is not None:
        conv_result = await db.execute(
            select(Conversation.persona_id).where(
                Conversation.id == conversation_id, Conversation.user_id == user.id
            )
        )
        persona_id = conv_result.scalar_one_or_none()
        if persona_id is not None:
            persona_service = PersonaService(db)
            persona = await persona_service.get_persona(user, persona_id)
            base_prompt = persona.system_prompt
            persona_rag_context = await persona_service.build_rag_context(
                persona, user_message, _llm
            )

    system_prompt = base_prompt
    if persona_rag_context:
        system_prompt = f"{system_prompt}\n\n{persona_rag_context}"

    # NEW J41+ Feature 4 — dataset joint au message (CSV/Excel envoye dans le
    # chat) : injecte un extrait de ses donnees dans le system prompt pour
    # le contexte visuel. NEW J46 — Option A : les questions chiffrees ne
    # sont plus repondues depuis cet extrait, elles passent obligatoirement
    # par le tool compute_from_dataset (voir plus bas), ajoute aux tools
    # disponibles uniquement quand un dataset est actif.
    has_dataset_context = False
    dataset_attachment = next(
        (a for a in (attachments or []) if a.get("type") == "dataset" and a.get("dataset_id")),
        None,
    )
    if dataset_attachment:
        service = DatasetService(db, FileStorage())
        context_block = await service.build_chat_context_block(
            user, UUID(dataset_attachment["dataset_id"])
        )
        if context_block:
            system_prompt = f"{system_prompt}\n\n{context_block}"
            has_dataset_context = True

    tools = [*TOOLS_SCHEMA, get_compute_tool_schema()] if has_dataset_context else TOOLS_SCHEMA

    # Temperature basse quand des donnees sont deja fournies en contexte :
    # reduit la tendance du LLM a appeler des outils (dashboard, summary...)
    # de facon non sollicitee au lieu de repondre directement depuis l'extrait.
    tool_call_temperature = 0.2 if has_dataset_context else 0.7

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    tool_calls_trace: list[dict[str, Any]] = []
    artifacts: dict[str, Any] = {}
    iterations = 0

    # Accumule l'usage sur toutes les iterations du loop (chaque appel LLM
    # consomme des tokens, y compris les allers-retours tool calling)
    total_prompt_tokens = 0
    total_completion_tokens = 0
    used_model = _llm.default_chat_model

    for i in range(MAX_ITERATIONS):
        iterations = i + 1

        response = await _llm.chat_with_tools(
            messages=messages,
            tools=tools,
            temperature=tool_call_temperature,
        )

        if usage := response.get("usage"):
            total_prompt_tokens += usage["prompt_tokens"]
            total_completion_tokens += usage["completion_tokens"]
            used_model = usage["model"]

        response_tool_calls = response.get("tool_calls") or []
        response_content = response.get("content")

        # Si le LLM répond sans appel d'outil → réponse finale
        if not response_tool_calls:
            return {
                "message": response_content or "",
                "tool_calls": tool_calls_trace,
                "artifacts": artifacts or None,
                "iterations": iterations,
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_prompt_tokens + total_completion_tokens,
                "cost_usd": calculate_cost(
                    used_model, total_prompt_tokens, total_completion_tokens
                ),
                "model_used": used_model,
            }

        # Sinon : on enregistre l'assistant message (avec ses tool_calls bruts)
        # Format OpenAI attendu pour la suite : id + function.name + function.arguments
        messages.append({
            "role": "assistant",
            "content": response_content,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"]
                        if isinstance(tc["arguments"], str)
                        else json.dumps(tc["arguments"], ensure_ascii=False),
                    },
                }
                for tc in response_tool_calls
            ],
        })

        # Et on exécute chaque outil demandé
        for tc in response_tool_calls:
            tc_name = tc["name"]
            tc_id = tc["id"]
            raw_args = tc.get("arguments") or {}

            # Les arguments arrivent en string JSON (cf. providers/openai.py).
            # On parse pour passer un dict à execute_tool.
            if isinstance(raw_args, str):
                try:
                    tc_args = json.loads(raw_args) if raw_args.strip() else {}
                except json.JSONDecodeError:
                    tc_args = {}
            else:
                tc_args = raw_args

            start = time.perf_counter()
            try:
                result = await execute_tool(
                    tool_name=tc_name,
                    arguments=tc_args,
                    db=db,
                    user=user,
                )

                # execute_tool peut renvoyer un dict {"error": "..."} sans lever
                # d'exception (cf. vector_tools.py — try/except interne).
                # On détecte ce cas pour ne pas marquer faussement status="ok".
                if isinstance(result, dict) and "error" in result:
                    status = "error"
                    summary = f"Erreur : {str(result['error'])[:120]}"
                    print(
                        f"\n[AGENT TOOL ERROR] {tc_name}\n"
                        f"  args sent: {tc_args}\n"
                        f"  error: {result['error']}\n",
                        flush=True,
                    )
                else:
                    status = "ok"
                    summary = _make_tool_summary(tc_name, result)

                    # Capture les artefacts intéressants pour le frontend
                    if tc_name == "generate_dashboard":
                        if dash_id := result.get("dashboard_id"):
                            artifacts["dashboard_id"] = str(dash_id)
                        if ds_id := result.get("dataset_id"):
                            artifacts["dataset_id"] = str(ds_id)

            except Exception as e:
                full_trace = traceback.format_exc()
                print(
                    f"\n[AGENT EXCEPTION] {tc_name}\n"
                    f"  args sent: {tc_args}\n"
                    f"  exception: {type(e).__name__}: {e}\n"
                    f"  traceback:\n{full_trace}\n",
                    flush=True,
                )
                result = {"error": str(e), "exception_type": type(e).__name__}
                status = "error"
                summary = f"Erreur : {type(e).__name__}: {str(e)[:100]}"

            duration_ms = int((time.perf_counter() - start) * 1000)

            tool_calls_trace.append({
                "name": tc_name,
                "args": tc_args,
                "result_summary": summary,
                "status": status,
                "duration_ms": duration_ms,
            })

            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": json.dumps(result, default=str, ensure_ascii=False),
            })

    # Limite d'itérations atteinte sans réponse finale
    return {
        "message": (
            "J'ai atteint ma limite d'itérations sans pouvoir conclure. "
            "Reformule ta demande de manière plus précise."
        ),
        "tool_calls": tool_calls_trace,
        "artifacts": artifacts or None,
        "iterations": iterations,
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "cost_usd": calculate_cost(
            used_model, total_prompt_tokens, total_completion_tokens
        ),
        "model_used": used_model,
    }


def _make_tool_summary(tool_name: str, result: dict[str, Any]) -> str:
    """Résumé lisible (français) du résultat d'un outil — affiché en bulle chat."""
    if tool_name == "list_user_datasets":
        datasets = result.get("datasets", [])
        n = len(datasets)
        if n == 0:
            return "Aucun dataset trouvé"
        return f"{n} dataset{'s' if n > 1 else ''} trouvé{'s' if n > 1 else ''}"

    if tool_name == "compute_from_dataset":
        return result.get("summary") or "Calcul exécuté"

    if tool_name == "get_dataset_summary":
        name = result.get("name") or result.get("dataset_name") or "?"
        rows = result.get("rows", result.get("row_count", "?"))
        cols = result.get("columns", result.get("column_count", "?"))
        if isinstance(cols, list):
            cols = len(cols)
        return f"« {name} » — {rows} lignes, {cols} colonnes"

    # J16 + J18 : tous les handlers de dashboard partagent la même forme de retour
    if tool_name in {
        "generate_dashboard",
        "generate_marketing_dashboard",
        "generate_sales_dashboard",
        "generate_customers_dashboard",
        "generate_trends_dashboard",
    }:
        n_kpis = (
            result.get("kpi_count")
            or result.get("kpis_count")
            or len(result.get("kpis", []) or [])
            or len(result.get("kpi_specs", []) or [])
        )
        ds_name = result.get("dataset_name", "")
        focus = result.get("focus_label", "")
        if ds_name and focus:
            return f"Dashboard {focus} « {ds_name} » généré ({n_kpis} KPIs)"
        if ds_name:
            return f"Dashboard « {ds_name} » généré ({n_kpis} KPIs)"
        return f"Dashboard généré ({n_kpis} KPIs)"

    return "Outil exécuté"
