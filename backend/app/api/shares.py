"""Endpoints de partage public de conversations — S5 J48.

Deux routers dans ce fichier :
- router (prefix /conversations) : POST/DELETE {id}/share — authentifiés,
  ownership check strict (même pattern 404 que ConversationService._get_owned,
  pas de 403 pour rester cohérent avec le reste de l'API).
- public_router (prefix /share) : GET {token} — PUBLIC, aucune dépendance
  d'auth. Premier endpoint de contenu public du projet : la surface de
  sortie est strictement filtrée via PublicConversationShare (voir
  app/schemas/share.py), jamais le modèle interne directement.
"""
import secrets
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.models.conversation import Conversation, Message
from app.db.models.conversation_share import ConversationShare
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.share import (
    PublicAttachment,
    PublicConversationShare,
    PublicMessage,
    PublicRagSource,
    ShareCreate,
    ShareResponse,
)

router = APIRouter(prefix="/conversations", tags=["shares"])
public_router = APIRouter(prefix="/share", tags=["shares"])

# Kinds de bulle inclus dans la vue publique — "status" (indicateurs de
# chargement transitoires) et "tool" (traces d'exécution d'outils) sont des
# artefacts internes de l'UI, pas du contenu destiné à un lecteur externe.
_PUBLIC_MESSAGE_KINDS = {"user", "agent", "pdf_attachment", "form"}


def _build_share_url(token: str) -> str:
    # S5 J55 : /share/[token] -> /share?token=... (routes a parametre de
    # requete, requis par l'export statique Next.js -- voir
    # docs/DEPLOYMENT_RENDER.md decision F).
    base = get_settings().cors_origins_list[0].rstrip("/")
    return f"{base}/share?token={token}"


async def _get_owned_conversation(
    db: AsyncSession, user: User, conversation_id: UUID
) -> Conversation:
    """Ownership check — 404 (pas 403) pour rester cohérent avec le reste
    de l'API (ConversationService._get_owned, DatasetService.get_dataset)."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Conversation introuvable ou accès refusé"
        )
    return conv


def _to_public_message(message: Message, include_attachments: bool) -> PublicMessage:
    sources = None
    if message.sources:
        sources = [
            PublicRagSource(
                document_name=s.get("document_name"),
                page_number=s.get("page_number"),
                content_preview=s.get("content_preview"),
            )
            for s in message.sources
        ]

    has_image_attachments = bool(
        message.attachments and any(a.get("type") == "image" for a in message.attachments)
    )

    attachments = None
    # include_attachments=False (défaut) : jamais construit, même pas un
    # PublicAttachment vide — le champ reste absent, pas juste filtré.
    if include_attachments and has_image_attachments:
        attachments = [
            PublicAttachment(
                file_name=a.get("file_name", "image"),
                mime_type=a.get("mime_type", "image/png"),
                preview_base64=a["preview_base64"],
            )
            for a in message.attachments
            if a.get("type") == "image" and a.get("preview_base64")
        ] or None

    return PublicMessage(
        role=message.role,
        message_kind=message.message_kind,
        content=message.content,
        sources=sources,
        attachments=attachments,
        has_hidden_attachments=has_image_attachments and not include_attachments,
        created_at=message.created_at,
    )


@router.post("/{conversation_id}/share", response_model=ShareResponse)
async def create_share(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: ShareCreate = ShareCreate(),
) -> ShareResponse:
    """Crée un lien de partage public (ou retourne l'actif existant — pas
    de doublon). Si un share actif existe déjà et que la préférence
    include_attachments soumise diffère, elle est mise à jour sur place
    (même token) plutôt qu'ignorée silencieusement."""
    await _get_owned_conversation(db, current_user, conversation_id)

    result = await db.execute(
        select(ConversationShare).where(
            ConversationShare.conversation_id == conversation_id,
            ConversationShare.revoked_at.is_(None),
        )
    )
    existing = result.scalars().first()
    if existing:
        if existing.include_attachments != payload.include_attachments:
            existing.include_attachments = payload.include_attachments
            await db.commit()
        return ShareResponse(
            share_token=existing.share_token,
            share_url=_build_share_url(existing.share_token),
            include_attachments=existing.include_attachments,
        )

    share = ConversationShare(
        conversation_id=conversation_id,
        # secrets.token_urlsafe (CSPRNG), jamais uuid4() qui est prévisible.
        # 32 bytes -> 43 caractères base64 URL-safe.
        share_token=secrets.token_urlsafe(32),
        created_by_user_id=current_user.id,
        include_attachments=payload.include_attachments,
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)

    return ShareResponse(
        share_token=share.share_token,
        share_url=_build_share_url(share.share_token),
        include_attachments=share.include_attachments,
    )


@router.delete("/{conversation_id}/share", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Révoque tous les shares actifs de cette conversation — invalidation
    immédiate côté GET public."""
    await _get_owned_conversation(db, current_user, conversation_id)

    result = await db.execute(
        select(ConversationShare).where(
            ConversationShare.conversation_id == conversation_id,
            ConversationShare.revoked_at.is_(None),
        )
    )
    now = datetime.now(UTC)
    for share in result.scalars().all():
        share.revoked_at = now
    await db.commit()


@public_router.get("/{token}", response_model=PublicConversationShare)
async def get_public_share(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PublicConversationShare:
    """PUBLIC — aucune authentification. Filtrage strict de la sortie
    (voir PublicConversationShare) : jamais de tokens/coût/tool_calls
    internes, jamais l'email de l'utilisateur qui a partagé."""
    not_found = HTTPException(status.HTTP_404_NOT_FOUND, "Ce lien n'est plus valide")

    result = await db.execute(
        select(ConversationShare)
        .options(selectinload(ConversationShare.created_by))
        .where(ConversationShare.share_token == token)
    )
    share = result.scalar_one_or_none()

    if share is None or share.revoked_at is not None:
        raise not_found
    if share.expires_at is not None and share.expires_at < datetime.now(UTC):
        raise not_found

    conv_result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == share.conversation_id)
    )
    conversation = conv_result.scalar_one_or_none()
    if conversation is None:
        # Conversation supprimee (share orpheline malgre le cascade normal —
        # defense en profondeur, ne devrait pas arriver).
        raise not_found

    return PublicConversationShare(
        title=conversation.title,
        shared_by=share.created_by.full_name or "un utilisateur Vector",
        messages=[
            _to_public_message(m, share.include_attachments)
            for m in conversation.messages
            if m.message_kind in _PUBLIC_MESSAGE_KINDS
        ],
    )
