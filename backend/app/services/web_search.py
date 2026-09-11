"""Service de recherche web live via Tavily (S5 J41.B)."""
import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from tavily import TavilyClient

from app.ai.providers.base import Message
from app.ai.providers.openai import OpenAIProvider
from app.core.config import get_settings
from app.core.constants import calculate_cost

settings = get_settings()
logger = logging.getLogger(__name__)


class WebSearchService:
    def __init__(self) -> None:
        self._mock = settings.USE_MOCK_LLM
        if self._mock or not settings.TAVILY_API_KEY:
            self.client: TavilyClient | None = None
        else:
            self.client = TavilyClient(api_key=settings.TAVILY_API_KEY)

    async def search(self, query: str, max_results: int = 5) -> dict[str, Any]:
        """
        Retourne les resultats de recherche web pour le contexte LLM.
        Structure : {
            "results": [
                { "title": str, "url": str, "content": str (extrait), "score": float }
            ],
            "answer": str (synthese Tavily, optionnelle),
            "error": str | None
        }
        """
        if self._mock:
            return {
                "results": [
                    {
                        "title": f"Résultat mock pour « {query} »",
                        "url": "https://example.com/mock",
                        "content": "Contenu de test déterministe (S5 J52, USE_MOCK_LLM).",
                        "score": 0.9,
                    }
                ],
                "answer": None,
                "error": None,
            }

        if not self.client:
            return {"results": [], "answer": None, "error": "Tavily API key manquante"}

        try:
            # tavily-python est synchrone (bloquant) : on le lance dans un
            # thread pour ne pas geler la boucle d'evenements asyncio pendant
            # l'appel HTTP (utilise dans un endpoint SSE streaming).
            response = await asyncio.to_thread(
                self.client.search,
                query=query,
                max_results=max_results,
                include_answer=True,
                include_raw_content=False,
                search_depth="basic",
            )
            return {
                "results": response.get("results", []),
                "answer": response.get("answer"),
                "error": None,
            }
        except Exception as e:
            return {"results": [], "answer": None, "error": str(e)}


SYSTEM_PROMPT = (
    "Tu es Vector, un assistant IA francophone. Tu reponds en t'appuyant sur "
    "les resultats de recherche web fournis ci-dessous. Sois precis et concis. "
    "Cite systematiquement les sources que tu utilises en fin de reponse, au "
    "format [1], [2], etc., en te referant a leur numero dans la liste fournie."
)


def _format_sources_for_prompt(results: list[dict[str, Any]]) -> str:
    parts = []
    for i, r in enumerate(results):
        title = r.get("title", "")
        url = r.get("url", "")
        excerpt = (r.get("content") or "")[:600]
        parts.append(f"[{i + 1}] {title}\n{url}\n{excerpt}")
    return "\n\n".join(parts)


async def answer_web_question_stream(
    question: str,
    provider: OpenAIProvider,
    max_results: int = 5,
) -> AsyncIterator[dict[str, Any]]:
    """Yield des evenements SSE pour une question enrichie par recherche web.

    Format des evenements (identique dans l'esprit au RAG existant) :
    - {"event": "web_sources", "data": [...]} : envoye EN PREMIER
    - {"event": "token", "data": "..."} : un token a la fois
    - {"event": "done", "data": {...}} : envoye EN DERNIER
    - {"event": "error", "data": "..."} : en cas d'erreur (recherche OU LLM)
    """
    service = WebSearchService()

    try:
        search_result = await service.search(question, max_results=max_results)

        if search_result["error"]:
            yield {"event": "error", "data": search_result["error"]}
            return

        results = search_result["results"]
        yield {
            "event": "web_sources",
            "data": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": (r.get("content") or "")[:240],
                }
                for r in results
            ],
        }

        sources_text = _format_sources_for_prompt(results)
        answer_hint = (
            f"\n\nSYNTHESE TAVILY (a titre indicatif) :\n{search_result['answer']}"
            if search_result.get("answer")
            else ""
        )
        user_prompt = (
            "Reponds a cette question en t'appuyant sur les resultats de "
            "recherche web ci-dessous. Cite systematiquement les sources en "
            "fin de reponse au format [1], [2], etc.\n\n"
            f"QUESTION : {question}\n\n"
            f"RESULTATS WEB :\n{sources_text}"
            f"{answer_hint}"
        )

        messages = [
            Message(role="system", content=SYSTEM_PROMPT),
            Message(role="user", content=user_prompt),
        ]

        token_count = 0
        usage: dict = {}
        async for token in provider.chat_stream(
            messages, temperature=0.4, usage_holder=usage
        ):
            token_count += 1
            yield {"event": "token", "data": token}

        done_data: dict = {"tokens_streamed": token_count, "sources_count": len(results)}
        if usage:
            done_data["prompt_tokens"] = usage["prompt_tokens"]
            done_data["completion_tokens"] = usage["completion_tokens"]
            done_data["total_tokens"] = usage["total_tokens"]
            done_data["model_used"] = usage["model"]
            done_data["cost_usd"] = calculate_cost(
                usage["model"], usage["prompt_tokens"], usage["completion_tokens"]
            )
        yield {"event": "done", "data": done_data}

    except Exception as e:
        logger.exception("Erreur dans answer_web_question_stream : %s", e)
        yield {
            "event": "error",
            "data": f"{type(e).__name__}: {str(e)[:300]}",
        }
