"""Modèles Conversation et Message — fils de discussion.

S1 : version initiale (user + agent + messages basiques)
S5 J25.B : enrichissement pour persistance UI riche
  - Conversation.document_id (FK nullable → documents.id, ondelete SET NULL)
  - Message.message_kind (discriminant: user/agent/status/tool/pdf_attachment/form)
  - Message.tool_calls (JSONB) — traces d'outils pour bulles kind='tool'
  - Message.sources (JSONB) — sources RAG pour bulles kind='agent'
"""
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.agent import Agent
    from app.db.models.conversation_share import ConversationShare
    from app.db.models.corpus import Corpus
    from app.db.models.document import Document
    from app.db.models.persona import Persona
    from app.db.models.user import User


class Conversation(Base, IdMixin, TimestampMixin):
    __tablename__ = "conversations"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # NEW J25.B — document_id nullable : conversation liée à un PDF pour RAG,
    # ou NULL pour une conversation classique (chat agent normal).
    # ondelete='SET NULL' : suppression du PDF garde l'historique (badge côté UI).
    document_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # NEW J34 — corpus_id nullable : conversation liée à un corpus (RAG multi-docs).
    # Mutuellement exclusif avec document_id en pratique (une conv cible soit
    # un doc, soit un corpus), mais pas contraint en BDD pour rester simple.
    corpus_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("corpora.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # NEW J49 — persona_id nullable : NULL = persona systeme "Vector" par
    # defaut. Verrouille des que la conversation a des messages (cote service).
    persona_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255), default="Nouvelle discussion", nullable=False
    )
    # NEW J27 — épinglage : conversations épinglées apparaissent en haut de la sidebar
    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    # Relations
    user: Mapped["User"] = relationship(back_populates="conversations")
    agent: Mapped["Agent"] = relationship(back_populates="conversations")
    document: Mapped["Document | None"] = relationship(back_populates="conversations")
    corpus: Mapped["Corpus | None"] = relationship(back_populates="conversations")
    persona: Mapped["Persona | None"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    shares: Mapped[list["ConversationShare"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class Message(Base, IdMixin):
    """Messages d'une conversation (immuables : pas d'updated_at)."""
    __tablename__ = "messages"

    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # role : compat historique (user/assistant/system)
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    # NEW J25.B — message_kind : discriminant riche pour reproduire l'UI exacte
    # au reload. Valeurs : user / agent / status / tool / pdf_attachment / form
    message_kind: Mapped[str] = mapped_column(
        String(30), nullable=False, default="agent", server_default="agent"
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # NEW J25.B — payloads JSONB pour reconstruire les bulles enrichies
    # tool_calls : liste des ToolCallTrace pour message_kind='tool'
    tool_calls: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # sources : liste des RagSource pour message_kind='agent' avec RAG
    sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # extra_data : payload flexible (form action, pdf attachment metadata...)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # NEW J30 — feedback utilisateur sur une réponse agent : positive / negative / NULL
    feedback: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # NEW J41+ Feature 2 — compteur de tokens / cout, rempli pour les
    # messages message_kind='agent' produits par un appel LLM. NULL pour
    # les messages user/tool/status (pas de completion associee).
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # NEW J41+ Feature 3 — pieces jointes (images pour l'instant, dataset
    # plus tard en Feature 4). Liste de dicts JSONB, voir schemas/conversation.py.
    attachments: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
