"""Schémas Pydantic RAG (S5 J23)."""
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RagAskRequest(BaseModel):
    """Requête de question RAG."""
    question: str = Field(..., min_length=3, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class RagCorpusAskRequest(BaseModel):
    """Requête de question RAG sur un corpus (S5 J34)."""
    corpus_id: UUID
    question: str = Field(..., min_length=3, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=20)


class ChunkSource(BaseModel):
    """Une source utilisée dans la réponse RAG."""
    chunk_id: UUID
    document_id: UUID
    document_name: str | None = None  # NEW J34 : rempli pour les reponses corpus
    document_file_type: str = "pdf"  # "pdf" | "docx" | "pptx" | "txt" | "md"
    page_number: int | None = None
    content_preview: str  # 200 premiers caractères du chunk
    similarity: float  # [0, 1]

    model_config = ConfigDict(from_attributes=True)


class RagAnswerResponse(BaseModel):
    """Réponse synchrone (non-streaming) d'une question RAG."""
    answer: str
    sources: list[ChunkSource]
    tokens_used_estimate: int = 0

    model_config = ConfigDict(from_attributes=True)
