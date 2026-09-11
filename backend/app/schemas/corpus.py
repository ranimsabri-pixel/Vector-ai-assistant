"""Schémas Pydantic pour les Corpus (S5 J34)."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.document import DocumentListItem


class CorpusCreate(BaseModel):
    """Payload pour créer un corpus."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class CorpusUpdate(BaseModel):
    """Payload pour PATCH (renommage et/ou description)."""
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class CorpusAddDocuments(BaseModel):
    """Payload pour ajouter des documents a un corpus."""
    document_ids: list[UUID]


class CorpusRemoveDocuments(BaseModel):
    """Payload pour retirer des documents d'un corpus."""
    document_ids: list[UUID]


class CorpusSummary(BaseModel):
    """Corpus léger (pour la liste)."""
    id: UUID
    name: str
    description: str | None = None
    document_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CorpusDetail(CorpusSummary):
    """Corpus complet avec la liste de ses documents."""
    documents: list[DocumentListItem] = []

    model_config = ConfigDict(from_attributes=True)


class CorpusUploadedFile(BaseModel):
    """Un fichier du batch qui a ete accepte (S5 J51)."""
    document_id: UUID
    filename: str
    status: str


class CorpusUploadError(BaseModel):
    """Un fichier du batch qui a ete refuse (S5 J51)."""
    filename: str
    error: str


class CorpusUploadResponse(BaseModel):
    """Reponse du POST /corpora/{id}/documents/upload -- erreur granulaire
    par fichier, un fichier invalide ne bloque pas les autres."""
    uploaded: list[CorpusUploadedFile]
    errors: list[CorpusUploadError]
