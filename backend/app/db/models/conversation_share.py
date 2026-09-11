"""Modèle ConversationShare — lien public en lecture seule (S5 J48)."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base, IdMixin

if TYPE_CHECKING:
    from app.db.models.conversation import Conversation
    from app.db.models.user import User


class ConversationShare(Base, IdMixin):
    """Un lien de partage public pour une conversation (lecture seule, sans
    compte requis). Pas de TimestampMixin : created_at a une sémantique
    propre ici (date du partage, pas de updated_at pertinent — un share
    n'est jamais modifié, seulement révoqué via revoked_at)."""

    __tablename__ = "conversation_shares"

    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Généré via secrets.token_urlsafe(32) — ~43 caractères URL-safe,
    # jamais un UUID (prévisible). Unique + indexé : c'est la clé de lookup
    # de l'endpoint public GET /share/{token}.
    share_token: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # NULL = actif. Un DELETE /conversations/{id}/share met revoked_at à
    # now() sur tous les shares actifs — le token reste en base (audit)
    # mais devient immédiatement invalide côté GET public.
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # V1 : jamais renseigné (pas de TTL par défaut, décision produit J48).
    # Colonne prête pour une évolution future sans nouvelle migration.
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # NEW J49 — opt-in explicite pour exposer les miniatures d'images dans
    # la vue publique. Sécurité par défaut : False partout (colonne,
    # endpoint, frontend) — les shares créés avant cette migration restent
    # donc identiques au comportement J48 (jamais d'image).
    include_attachments: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    conversation: Mapped[Conversation] = relationship(back_populates="shares")
    created_by: Mapped[User] = relationship()
