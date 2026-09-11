"""Schémas Pydantic pour les Documents et Chunks (S5 J21)."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    """Représentation complète d'un document (renvoyée par GET /documents/{id})."""
    id: UUID
    user_id: UUID
    name: str
    original_filename: str
    file_type: str  # NEW J32 : "pdf" | "docx"
    file_size_bytes: int
    status: str  # uploaded | parsing | chunking | embedding | ready | error
    error_message: str | None = None
    chunk_count: int
    page_count: int | None = None
    doc_metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListItem(BaseModel):
    """Version compacte pour la liste (renvoyée par GET /documents)."""
    id: UUID
    name: str
    original_filename: str
    file_type: str  # NEW J32 : "pdf" | "docx"
    status: str
    chunk_count: int
    page_count: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
# ============================================================
# J22 — Upload + Chunks
# ============================================================


class DocumentUploadResponse(BaseModel):
    """Réponse immédiate après upload, avant l'ingestion en background."""
    id: UUID
    name: str
    status: str
    file_size_bytes: int
    message: str = (
        "Upload réussi. L'ingestion (parsing, chunking, embeddings) "
        "se déroule en arrière-plan. Pollez GET /documents/{id} pour "
        "suivre l'avancement (status: uploaded → parsing → chunking → "
        "embedding → ready)."
    )

    model_config = ConfigDict(from_attributes=True)


class ChunkPreview(BaseModel):
    """Aperçu d'un chunk (sans le vecteur embedding qui est trop volumineux)."""
    id: UUID
    document_id: UUID
    chunk_index: int
    page_number: int | None = None
    content: str
    token_count: int
    has_embedding: bool  # juste un bool, pas le vecteur entier

    model_config = ConfigDict(from_attributes=True)
