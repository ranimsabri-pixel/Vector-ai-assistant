"""Endpoints Conversations (S5 J25.B) — CRUD + messages.

6 endpoints :
- POST   /conversations         Créer une nouvelle conversation
- GET    /conversations         Lister mes conversations (sidebar)
- GET    /conversations/{id}    Détail avec tous les messages (reprise)
- PATCH  /conversations/{id}    Renommer
- DELETE /conversations/{id}    Supprimer (+ cascade messages)
- POST   /conversations/{id}/messages    Append un message
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationStats,
    ConversationSummary,
    ConversationUpdate,
    ImageAttachmentResponse,
    MessageCreate,
    MessageResponse,
)
from app.services.conversations import ConversationService
from app.services.image_attachments import save_image_attachment

router = APIRouter(prefix="/conversations", tags=["conversations"])


# ============================================================
# Create
# ============================================================

@router.post(
    "",
    response_model=ConversationDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: ConversationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Crée une nouvelle conversation (avec ou sans PDF/corpus attaché)."""
    service = ConversationService(db)
    conv = await service.create(
        user=current_user,
        title=payload.title,
        document_id=payload.document_id,
        corpus_id=payload.corpus_id,
        persona_id=payload.persona_id,
        agent_slug=payload.agent_slug,
    )
    # Retour au format ConversationDetail (messages vide)
    return await service.get_conversation(current_user, conv.id)


# ============================================================
# Read
# ============================================================

@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
):
    """Liste mes conversations (récentes d'abord)."""
    service = ConversationService(db)
    return await service.list_user_conversations(current_user, limit=limit)


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Détail d'une conversation avec tous ses messages (pour reprise)."""
    service = ConversationService(db)
    return await service.get_conversation(current_user, conversation_id)


# ============================================================
# Update
# ============================================================

@router.post("/{conversation_id}/generate-title", response_model=ConversationSummary)
async def generate_conversation_title(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Genere un titre court via LLM apres le premier echange complet
    (best-effort, n'ecrase jamais un titre deja personnalise)."""
    service = ConversationService(db)
    return await service.generate_title(current_user, conversation_id)


@router.patch("/{conversation_id}", response_model=ConversationDetail)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Renomme et/ou épingle une conversation."""
    service = ConversationService(db)
    if payload.title is not None:
        await service.update_title(
            current_user, conversation_id, payload.title
        )
    if payload.is_pinned is not None:
        await service.toggle_pin(
            current_user, conversation_id, payload.is_pinned
        )
    if payload.persona_id is not None:
        await service.set_persona(
            current_user, conversation_id, payload.persona_id
        )
    return await service.get_conversation(current_user, conversation_id)


# ============================================================
# Delete
# ============================================================

@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Supprime une conversation et tous ses messages."""
    service = ConversationService(db)
    await service.delete_conversation(current_user, conversation_id)


# ============================================================
# Messages — append
# ============================================================

@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def append_message(
    conversation_id: UUID,
    payload: MessageCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Ajoute un message à une conversation existante."""
    service = ConversationService(db)
    return await service.add_message(
        user=current_user,
        conversation_id=conversation_id,
        role=payload.role,
        message_kind=payload.message_kind,
        content=payload.content,
        tool_calls=payload.tool_calls,
        sources=payload.sources,
        extra_data=payload.extra_data,
        prompt_tokens=payload.prompt_tokens,
        completion_tokens=payload.completion_tokens,
        total_tokens=payload.total_tokens,
        cost_usd=payload.cost_usd,
        model_used=payload.model_used,
        attachments=payload.attachments,
    )


# ============================================================
# Piece jointe image (NEW J41+ Feature 3)
# ============================================================

@router.post("/{conversation_id}/attach-image", response_model=ImageAttachmentResponse)
async def attach_image(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: Annotated[UploadFile, File()],
):
    """Upload une image dans le chat. Ne cree PAS de message : le frontend
    attache le resultat au brouillon en cours, envoye avec /messages une
    fois la question validee (comme les pieces jointes ChatGPT)."""
    service = ConversationService(db)
    await service.get_conversation(current_user, conversation_id)  # ownership check (404 si refuse)
    return await save_image_attachment(file, current_user.id, conversation_id)


# ============================================================
# Stats tokens/cout (NEW J41+ Feature 2)
# ============================================================

@router.get("/{conversation_id}/stats", response_model=ConversationStats)
async def get_conversation_stats(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Stats agregees tokens/cout d'une conversation."""
    service = ConversationService(db)
    return await service.get_stats(current_user, conversation_id)
