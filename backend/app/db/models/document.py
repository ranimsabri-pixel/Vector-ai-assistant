"""Modèles Document et Chunk — pipeline RAG (S5 J21)."""
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.conversation import Conversation
    from app.db.models.corpus import Corpus
    from app.db.models.persona import Persona
    from app.db.models.user import User


class Document(Base, IdMixin, TimestampMixin):
    """Un document PDF / DOCX / TXT uploadé pour le RAG."""
    __tablename__ = "documents"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Métadonnées de fichier (calquées sur Dataset)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # NEW J32 — format du fichier source : "pdf" ou "docx"
    file_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="pdf",
        server_default="pdf",
    )

    # État du traitement (pattern Dataset)
    # uploaded → parsing → chunking → embedding → ready | error
    status: Mapped[str] = mapped_column(
        String(20), default="uploaded", nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Métadonnées d'ingestion (remplies pendant l'ingestion J22)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Métadonnées libres (auteur, date, tags...) extraites du PDF
    doc_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    # Relations
    user: Mapped["User"] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Chunk.chunk_index",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="document",
    )
    corpora: Mapped[list["Corpus"]] = relationship(
        secondary="corpus_documents",
        back_populates="documents",
    )
    personas: Mapped[list["Persona"]] = relationship(
        secondary="personas_documents",
        back_populates="documents",
    )

class Chunk(Base, IdMixin, TimestampMixin):
    """Un fragment de texte d'un document, avec son embedding pour le RAG."""
    __tablename__ = "chunks"

    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Position dans le document (essentielle pour la citation)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Contenu et embedding
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # text-embedding-3-small = 1536 dimensions (cf. .env OPENAI_MODEL_EMBED)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536), nullable=True
    )

    # Relation
    document: Mapped["Document"] = relationship(back_populates="chunks")
