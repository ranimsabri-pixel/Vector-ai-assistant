"""Orchestrateur RAG (S5 J23) — embed + retrieve + augmenter + generate.

Deux modes :
- answer_question_stream : yield les tokens un par un (SSE)
- answer_question_sync   : retourne la réponse complète (pour tests/debug)

Structure du prompt :
- system : instructions générales (français, factuel, citation des sources)
- user   : question + extraits formatés avec marqueurs [Source N, page X]
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.base import Message
from app.ai.providers.openai import OpenAIProvider
from app.core.constants import calculate_cost
from app.services.retrieval import (
    DEFAULT_TOP_K,
    RetrievedChunk,
    embed_query,
    retrieve_from_corpus,
    search_in_document,
    search_in_user_documents,
)

logger = logging.getLogger(__name__)


# ============================================================
# System prompt RAG
# ============================================================

RAG_SYSTEM_PROMPT = """Tu es Vector, l'assistant IA d'analyse documentaire du squad A.I. Commandos.

Ne cite JAMAIS les sources directement dans le texte (elles apparaissent automatiquement sous ta réponse).

RÔLE :
- Réponds à la question de l'utilisateur EN T'APPUYANT UNIQUEMENT sur les extraits fournis ci-dessous.
- Si la réponse n'est pas dans les extraits, dis-le clairement : "Cette information ne figure pas dans les documents fournis."
- N'invente JAMAIS de faits qui ne sont pas dans les extraits.

STYLE :
- Réponds en français, ton clair et professionnel.
- Privilégie les listes à puces quand la réponse comporte plusieurs points.
- Sois concis : 3-6 phrases max sauf si la question demande explicitement du détail.

## Format des réponses
Quand ta réponse contient plusieurs éléments distincts, utilise le Markdown :
- **Gras** pour les concepts clés, chiffres importants, noms propres
- Listes à puces (- item) pour énumérer 3 éléments ou plus
- Listes numérotées (1. item) pour des étapes ordonnées
- Tableaux Markdown pour comparer plusieurs éléments
- Blocs `code` pour les noms techniques, colonnes, fichiers
- Titres ## uniquement pour les réponses longues (5+ paragraphes)

N'utilise PAS de Markdown pour :
- Réponses courtes (1-2 phrases) — reste en texte fluide
- Salutations et échanges conversationnels
- Excuses ou clarifications

Objectif : réponse scannable quand elle contient de la vraie information structurée, fluide et humaine quand elle est courte."""


# ============================================================
# Types
# ============================================================

@dataclass
class RagAnswer:
    """Réponse complète d'une question RAG (mode synchrone)."""
    answer: str
    sources: list[RetrievedChunk]
    tokens_used_estimate: int = 0


# ============================================================
# Construction du prompt
# ============================================================

def build_prompt(question: str, chunks: list[RetrievedChunk]) -> list[Message]:
    """Construit les messages [system, user] pour le LLM.

    Le user message contient la question + les extraits formatés.
    """
    if not chunks:
        # Cas dégénéré : aucun chunk pertinent trouvé
        user_content = (
            f"QUESTION : {question}\n\n"
            "EXTRAITS PERTINENTS : (aucun extrait trouvé dans les documents)"
        )
    else:
        extracts = []
        for i, rc in enumerate(chunks, start=1):
            page = rc.chunk.page_number or "?"
            # document_name rempli uniquement pour le retrieval multi-docs (corpus, J34)
            label = (
                f"[Source {i} - {rc.document_name}, page {page}]"
                if rc.document_name
                else f"[Source {i}, page {page}]"
            )
            extracts.append(f"{label}\n{rc.chunk.content.strip()}")
        extracts_str = "\n\n".join(extracts)

        user_content = (
            f"QUESTION : {question}\n\n"
            f"EXTRAITS PERTINENTS :\n\n{extracts_str}"
        )

    return [
        Message(role="system", content=RAG_SYSTEM_PROMPT),
        Message(role="user", content=user_content),
    ]


# ============================================================
# Mode synchrone (réponse complète)
# ============================================================

async def answer_question_sync(
    question: str,
    db: AsyncSession,
    provider: OpenAIProvider,
    document_id: UUID | None = None,
    corpus_id: UUID | None = None,
    user_id: UUID | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> RagAnswer:
    """Réponse complète en une fois (mode batch).

    Soit document_id (scope = 1 doc), soit corpus_id (scope = tous les docs
    du corpus), soit user_id seul (scope = tous les docs de l'user).
    corpus_id nécessite obligatoirement user_id (ownership check).
    """
    if document_id is None and corpus_id is None and user_id is None:
        raise ValueError("Il faut fournir document_id, corpus_id ou user_id")
    if corpus_id is not None and user_id is None:
        raise ValueError("corpus_id nécessite user_id (ownership check)")

    # 1. Embed la question
    query_vector = await embed_query(question, provider)

    # 2. Retrieval
    if document_id is not None:
        chunks = await search_in_document(db, document_id, query_vector, top_k)
    elif corpus_id is not None:
        chunks = await retrieve_from_corpus(db, corpus_id, user_id, query_vector, top_k)
    else:
        chunks = await search_in_user_documents(db, user_id, query_vector, top_k)

    # 3. Build prompt
    messages = build_prompt(question, chunks)

    # 4. Generate
    answer_text = await provider.chat(messages, temperature=0.3)

    # 5. Estimation tokens (rough : 1 token ≈ 4 caractères)
    tokens_estimate = (
        sum(len(m.content) for m in messages) + len(answer_text)
    ) // 4

    return RagAnswer(
        answer=answer_text,
        sources=chunks,
        tokens_used_estimate=tokens_estimate,
    )


# ============================================================
# Mode streaming (SSE)
# ============================================================

async def answer_question_stream(
    question: str,
    db: AsyncSession,
    provider: OpenAIProvider,
    document_id: UUID | None = None,
    corpus_id: UUID | None = None,
    user_id: UUID | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> AsyncIterator[dict]:
    """Yield des événements SSE un par un.

    Soit document_id (scope = 1 doc), soit corpus_id (scope = tous les docs
    du corpus), soit user_id seul (scope = tous les docs de l'user).
    corpus_id nécessite obligatoirement user_id (ownership check).

    Format des événements :
    - {"event": "sources", "data": {...}} : envoyé EN PREMIER (avant les tokens)
    - {"event": "token", "data": "Pour"} : un token à la fois
    - {"event": "done", "data": {...}} : envoyé EN DERNIER (stats finales)
    - {"event": "error", "data": "..."} : en cas d'erreur
    """
    if document_id is None and corpus_id is None and user_id is None:
        yield {"event": "error", "data": "Il faut fournir document_id, corpus_id ou user_id"}
        return
    if corpus_id is not None and user_id is None:
        yield {"event": "error", "data": "corpus_id nécessite user_id (ownership check)"}
        return

    try:
        # 1. Embed la question
        query_vector = await embed_query(question, provider)

        # 2. Retrieval
        if document_id is not None:
            chunks = await search_in_document(db, document_id, query_vector, top_k)
        elif corpus_id is not None:
            chunks = await retrieve_from_corpus(db, corpus_id, user_id, query_vector, top_k)
        else:
            chunks = await search_in_user_documents(db, user_id, query_vector, top_k)

        # 3. Envoie les sources EN PREMIER (le frontend pourra les afficher
        #    pendant que les tokens arrivent)
        yield {
            "event": "sources",
            "data": {
                "chunks": [
                    {
                        "chunk_id": str(rc.chunk.id),
                        "document_id": str(rc.chunk.document_id),
                        "document_name": rc.document_name,
                        "document_file_type": rc.document_file_type,
                        "page_number": rc.chunk.page_number,
                        "content_preview": rc.chunk.content[:200],
                        "similarity": round(rc.similarity, 3),
                    }
                    for rc in chunks
                ],
            },
        }

        # 4. Build prompt
        messages = build_prompt(question, chunks)

        # 5. Stream les tokens un par un (usage_holder rempli par l'API via
        #    stream_options include_usage — cf. providers/openai.py)
        token_count = 0
        usage: dict = {}
        async for token in provider.chat_stream(
            messages, temperature=0.3, usage_holder=usage
        ):
            token_count += 1
            yield {"event": "token", "data": token}

        # 6. Stats finales — usage reel si dispo (Feature 2), sinon juste le
        #    compteur de tokens de streaming existant
        done_data: dict = {
            "chunks_retrieved": len(chunks),
            "tokens_streamed": token_count,
        }
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
        logger.exception("Erreur dans answer_question_stream : %s", e)
        yield {
            "event": "error",
            "data": f"{type(e).__name__}: {str(e)[:300]}",
        }
