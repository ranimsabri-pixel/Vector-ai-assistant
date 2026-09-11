"""Schemas Pydantic pour Conversation + Message (S5 J25.B)."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ============================================================
# Message schemas
# ============================================================

class MessageBase(BaseModel):
    """Base commune : role + kind + content + payloads optionnels."""

    model_config = ConfigDict(protected_namespaces=())

    role: str = Field(..., description="user | assistant | system")
    message_kind: str = Field(
        default="agent",
        description="Discriminant UI : user / agent / status / tool / pdf_attachment / form",
    )
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    sources: list[dict[str, Any]] | None = None
    extra_data: dict[str, Any] | None = None
    # NEW J41+ Feature 2 — compteur de tokens/cout, fourni par le frontend
    # apres un appel LLM (RAG stream, web search stream, agent chat classique)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    model_used: str | None = None
    # NEW J41+ Feature 3 — pieces jointes (images pour l'instant)
    attachments: list[dict[str, Any]] | None = None


class MessageCreate(MessageBase):
    """Payload pour créer un message (POST /conversations/{id}/messages)."""
    pass


class MessageResponse(MessageBase):
    """Message tel que retourné par l'API."""
    id: UUID
    conversation_id: UUID
    created_at: datetime
    feedback: Literal["positive", "negative"] | None = None  # NEW J30

    model_config = ConfigDict(from_attributes=True)


class MessageFeedbackUpdate(BaseModel):
    """Payload pour PATCH /messages/{id}/feedback (NEW J30)."""
    feedback: Literal["positive", "negative"] | None = None


# ============================================================
# Conversation schemas
# ============================================================

class ConversationCreate(BaseModel):
    """Payload pour créer une nouvelle conversation."""
    title: str | None = None
    document_id: UUID | None = None
    corpus_id: UUID | None = None  # NEW J34
    persona_id: UUID | None = None  # NEW J49 — None = persona système Vector
    agent_slug: str = "vector"


class ConversationUpdate(BaseModel):
    """Payload pour PATCH (renommage, épinglage, et/ou changement de persona).

    persona_id : None = champ non fourni, ne touche pas au persona actuel.
    Le persona système Vector est un choix explicite comme un autre (son
    UUID réel), pas un cas particulier — pas besoin de distinguer "absent"
    de "reset vers Vector".
    """
    title: str | None = None
    is_pinned: bool | None = None
    persona_id: UUID | None = None  # NEW J49


class ConversationSummary(BaseModel):
    """Conversation légère (pour la liste dans la sidebar)."""
    id: UUID
    title: str
    document_id: UUID | None
    corpus_id: UUID | None = None  # NEW J34
    persona_id: UUID | None = None  # NEW J49
    persona_name: str | None = None  # NEW J49, dénormalisé pour éviter N+1
    persona_icon: str | None = None  # NEW J49
    persona_color: str | None = None  # NEW J49
    is_pinned: bool = False  # NEW J27
    document_name: str | None = None  # dénormalisé pour éviter N+1
    corpus_name: str | None = None  # NEW J34, dénormalisé pour éviter N+1
    message_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetail(BaseModel):
    """Conversation complète avec tous ses messages (pour reprise)."""
    id: UUID
    title: str
    document_id: UUID | None
    document_name: str | None = None
    corpus_id: UUID | None = None  # NEW J34
    corpus_name: str | None = None  # NEW J34
    persona_id: UUID | None = None  # NEW J49
    persona_name: str | None = None  # NEW J49
    persona_icon: str | None = None  # NEW J49
    persona_color: str | None = None  # NEW J49
    is_pinned: bool = False  # NEW J27
    agent_id: UUID
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# Stats tokens/cout (NEW J41+ Feature 2)
# ============================================================

class ConversationStats(BaseModel):
    """Stats agregees tokens/cout d'une conversation (GET /{id}/stats)."""
    total_messages: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_response_tokens: float = 0.0


# ============================================================
# Piece jointe image (NEW J41+ Feature 3)
# ============================================================

class ImageAttachmentResponse(BaseModel):
    """Reponse de POST /{id}/attach-image — a repasser telle quelle dans
    MessageCreate.attachments quand le message est envoye."""
    type: Literal["image"] = "image"
    attachment_id: str
    file_name: str
    mime_type: str
    file_size: int
    width: int
    height: int
    storage_path: str
    preview_base64: str
