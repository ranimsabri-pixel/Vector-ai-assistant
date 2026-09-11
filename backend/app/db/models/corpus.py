"""Modeles Corpus et CorpusDocument — collections thematiques de documents (S5 J34).

Un Corpus regroupe plusieurs Document (PDF/DOCX/PPTX) via une table de
jointure many-to-many : un document peut appartenir a plusieurs corpus.
"""
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.conversation import Conversation
    from app.db.models.document import Document
    from app.db.models.persona import Persona
    from app.db.models.user import User


class Corpus(Base, IdMixin, TimestampMixin):
    """Collection thematique de documents, creee par l'utilisateur."""
    __tablename__ = "corpora"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relations
    user: Mapped["User"] = relationship(back_populates="corpora")
    documents: Mapped[list["Document"]] = relationship(
        secondary="corpus_documents",
        back_populates="corpora",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="corpus",
    )
    personas: Mapped[list["Persona"]] = relationship(
        secondary="personas_corpora",
        back_populates="corpora",
    )


class CorpusDocument(Base):
    """Table de jointure many-to-many Corpus <-> Document."""
    __tablename__ = "corpus_documents"

    corpus_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("corpora.id", ondelete="CASCADE"),
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
