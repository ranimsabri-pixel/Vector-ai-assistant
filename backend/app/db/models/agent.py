"""Modèle Agent — agents IA (Vector et futurs)."""
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.conversation import Conversation


class Agent(Base, IdMixin, TimestampMixin):
    __tablename__ = "agents"

    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    accent_color: Mapped[str] = mapped_column(String(7), default="#2D8659", nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relations
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="agent")
