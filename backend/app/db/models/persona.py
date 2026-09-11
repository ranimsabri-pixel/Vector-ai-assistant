"""Modeles Persona, PersonaDocument et PersonaCorpus — assistants personnalises (S5 J49).

Un Persona regroupe un system prompt custom + une identite visuelle (icone,
couleur) + des documents/corpus associes (contexte RAG auto-enrichi quand le
persona est actif dans une conversation). Le persona systeme "Vector"
(is_system=True, user_id=NULL) est partage par tous les utilisateurs et ne
peut jamais etre modifie ni supprime (contrainte appliquee cote service).
"""
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.conversation import Conversation
    from app.db.models.corpus import Corpus
    from app.db.models.document import Document
    from app.db.models.user import User


class Persona(Base, IdMixin, TimestampMixin):
    """Assistant personnalise : system prompt + identite visuelle + sources RAG."""
    __tablename__ = "personas"

    # NULL pour le persona systeme "Vector" (partage par tous les utilisateurs).
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relations
    user: Mapped["User | None"] = relationship(back_populates="personas")
    documents: Mapped[list["Document"]] = relationship(
        secondary="personas_documents",
        back_populates="personas",
    )
    corpora: Mapped[list["Corpus"]] = relationship(
        secondary="personas_corpora",
        back_populates="personas",
    )
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="persona")


class PersonaDocument(Base):
    """Table de jointure many-to-many Persona <-> Document."""
    __tablename__ = "personas_documents"

    persona_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        primary_key=True,
    )
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PersonaCorpus(Base):
    """Table de jointure many-to-many Persona <-> Corpus."""
    __tablename__ = "personas_corpora"

    persona_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        primary_key=True,
    )
    corpus_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("corpora.id", ondelete="CASCADE"),
        primary_key=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
