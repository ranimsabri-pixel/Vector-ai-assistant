"""Schémas Pydantic — Agents (squad) + Agent runtime (chat)."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Schémas SQUAD — Agent entité BDD (Vector, futurs commandos)
# Utilisés par app/api/agents.py (pluriel)
# =============================================================================

class AgentResponse(BaseModel):
    """Lecture complète d'un agent du squad."""
    id: UUID
    slug: str
    name: str
    role: str
    system_prompt: str | None = None
    accent_color: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentListItem(BaseModel):
    """Item compact pour la liste des agents (sidebar)."""
    id: UUID
    slug: str
    name: str
    role: str
    accent_color: str | None = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Schémas RUNTIME — Agent en action (tool calling)
# Utilisés par app/api/agent.py (singulier)
# =============================================================================

class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None
    # NEW J41+ Feature 3 — images jointes (memes dicts que ImageAttachmentResponse)
    attachments: list[dict[str, Any]] | None = None


class WebChatRequest(BaseModel):
    """Requete pour /agent/chat-web (S5 J41.B) — question enrichie par
    recherche web live (Tavily). La persistance du message se fait cote
    frontend apres reception du stream, comme pour les endpoints RAG."""
    question: str = Field(..., min_length=1, max_length=2000)
    max_results: int = Field(default=5, ge=1, le=10)


class ToolCallTrace(BaseModel):
    """Trace lisible d'un appel d'outil — affichée en bulle dans le chat."""
    name: str
    args: dict[str, Any]
    result_summary: str
    status: Literal["ok", "error"]
    duration_ms: int


class AgentArtifacts(BaseModel):
    """Artefacts générés par l'agent (CTAs frontend)."""
    dashboard_id: str | None = None
    dataset_id: str | None = None


class AgentChatResponse(BaseModel):
    """Réponse enrichie du /agent/chat."""

    model_config = ConfigDict(protected_namespaces=())

    message: str
    tool_calls: list[ToolCallTrace] = []
    artifacts: AgentArtifacts | None = None
    iterations: int = 0
    # NEW J41+ Feature 2 — compteur de tokens/cout (None pour /agent/run-tool,
    # qui n'appelle pas le LLM)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    model_used: str | None = None

# =============================================================================
# J20 — Schéma pour POST /agent/run-tool (exécution directe d'outil, sans LLM)
# =============================================================================


class AgentRunToolRequest(BaseModel):
    """Exécute un outil agentique directement, en court-circuitant le LLM.

    Utilisé par les actions rapides du frontend qui connaissent déjà
    précisément quel outil appeler et avec quels arguments.
    """
    tool_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nom de l'outil dans TOOL_HANDLERS (cf. vector_tools.py)",
    )
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments structurés à passer à l'outil",
    )
