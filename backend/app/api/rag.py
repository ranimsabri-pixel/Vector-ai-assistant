"""Endpoints RAG (S5 J23) — question-réponse documentaire avec citations.

4 endpoints :
- POST /rag/ask/{document_id}        : streaming SSE sur UN document
- POST /rag/ask                       : streaming SSE sur TOUS les documents user
- POST /rag/ask-sync/{document_id}    : version non-streaming (pour tests)
- POST /rag/corpus-query               : streaming SSE sur TOUS les documents d'un corpus (S5 J34)
"""
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.ai.providers.openai import OpenAIProvider
from app.api.deps import get_current_user
from app.db.models.corpus import Corpus
from app.db.models.document import Document
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.rag import (
    ChunkSource,
    RagAnswerResponse,
    RagAskRequest,
    RagCorpusAskRequest,
)
from app.services.rag import (
    answer_question_stream,
    answer_question_sync,
)

router = APIRouter(prefix="/rag", tags=["rag"])

# OpenAIProvider partagé (instance unique réutilisée)
_provider = OpenAIProvider()


# ============================================================
# Helper : ownership check d'un document
# ============================================================

async def _verify_document_ownership(
    db: AsyncSession, user: User, document_id: UUID
) -> Document:
    """Vérifie que le document appartient à l'utilisateur ET qu'il est ready."""
    document = await db.get(Document, document_id)
    if not document or document.user_id != user.id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Document introuvable"
        )
    if document.status != "ready":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Le document n'est pas prêt (status={document.status}). "
            f"Attendez que l'ingestion soit terminée.",
        )
    return document


# ============================================================
# Helper : ownership check d'un corpus (S5 J34)
# ============================================================

async def _verify_corpus_ownership(
    db: AsyncSession, user: User, corpus_id: UUID
) -> Corpus:
    """Vérifie que le corpus appartient à l'utilisateur AVANT toute recherche.

    Défense en profondeur : retrieve_from_corpus filtre déjà par
    Corpus.user_id au niveau SQL, mais ce check permet de retourner un 404
    explicite plutôt qu'une liste de sources silencieusement vide.
    """
    result = await db.execute(
        select(Corpus).where(Corpus.id == corpus_id, Corpus.user_id == user.id)
    )
    corpus = result.scalar_one_or_none()
    if corpus is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Corpus introuvable ou accès refusé"
        )
    return corpus


# ============================================================
# Streaming SSE sur UN document
# ============================================================

@router.post("/ask/{document_id}")
async def ask_document_stream(
    document_id: UUID,
    payload: RagAskRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Question sur UN document spécifique, réponse en streaming SSE.

    Le frontend consomme via EventSource :
        const evt = new EventSource('/rag/ask/{doc_id}', {method: 'POST', ...})
        evt.addEventListener('sources', e => {...})
        evt.addEventListener('token', e => append(e.data))
        evt.addEventListener('done', e => {...})
    """
    await _verify_document_ownership(db, current_user, document_id)

    async def event_generator():
        async for event in answer_question_stream(
            question=payload.question,
            db=db,
            provider=_provider,
            document_id=document_id,
            top_k=payload.top_k,
        ):
            # sse-starlette attend des dicts avec "event" et "data"
            data = event["data"]
            if not isinstance(data, str):
                data = json.dumps(data, ensure_ascii=False)
            yield {"event": event["event"], "data": data}

    return EventSourceResponse(event_generator())


# ============================================================
# Streaming SSE sur TOUS les documents user
# ============================================================

@router.post("/ask")
async def ask_global_stream(
    payload: RagAskRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Question sur TOUS les documents de l'utilisateur (ready uniquement).

    Utile quand l'utilisateur ne sait pas dans quel doc chercher.
    """

    async def event_generator():
        async for event in answer_question_stream(
            question=payload.question,
            db=db,
            provider=_provider,
            user_id=current_user.id,
            top_k=payload.top_k,
        ):
            data = event["data"]
            if not isinstance(data, str):
                data = json.dumps(data, ensure_ascii=False)
            yield {"event": event["event"], "data": data}

    return EventSourceResponse(event_generator())


# ============================================================
# Streaming SSE sur TOUS les documents d'un CORPUS (S5 J34)
# ============================================================

@router.post("/corpus-query")
async def ask_corpus_stream(
    payload: RagCorpusAskRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Question sur TOUS les documents d'un corpus (streaming SSE).

    Meme format d'evenements que /rag/ask : sources -> token(s) -> done.
    Chaque source inclut document_name et document_file_type pour que le
    frontend identifie clairement le document d'origine.
    """
    await _verify_corpus_ownership(db, current_user, payload.corpus_id)

    async def event_generator():
        async for event in answer_question_stream(
            question=payload.question,
            db=db,
            provider=_provider,
            corpus_id=payload.corpus_id,
            user_id=current_user.id,
            top_k=payload.top_k,
        ):
            data = event["data"]
            if not isinstance(data, str):
                data = json.dumps(data, ensure_ascii=False)
            yield {"event": event["event"], "data": data}

    return EventSourceResponse(event_generator())


# ============================================================
# Version non-streaming (test / debug)
# ============================================================

@router.post(
    "/ask-sync/{document_id}",
    response_model=RagAnswerResponse,
)
async def ask_document_sync(
    document_id: UUID,
    payload: RagAskRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Version NON-STREAMING — retourne la réponse complète d'un coup.

    Plus simple pour les tests Swagger (l'UI Swagger gère mal le SSE).
    """
    await _verify_document_ownership(db, current_user, document_id)

    rag_answer = await answer_question_sync(
        question=payload.question,
        db=db,
        provider=_provider,
        document_id=document_id,
        top_k=payload.top_k,
    )

    sources = [
        ChunkSource(
            chunk_id=rc.chunk.id,
            document_id=rc.chunk.document_id,
            document_name=rc.document_name,
            document_file_type=rc.document_file_type,
            page_number=rc.chunk.page_number,
            content_preview=rc.chunk.content[:200],
            similarity=round(rc.similarity, 3),
        )
        for rc in rag_answer.sources
    ]

    return RagAnswerResponse(
        answer=rag_answer.answer,
        sources=sources,
        tokens_used_estimate=rag_answer.tokens_used_estimate,
    )
