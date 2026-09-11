"""Schémas Pydantic — Personas (assistants personnalisés, S5 J49)."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.corpus import CorpusSummary
from app.schemas.document import DocumentListItem

# Whitelist d'icônes lucide-react proposées dans le picker frontend.
ALLOWED_ICONS: frozenset[str] = frozenset({
    "Bot", "Sparkles", "Briefcase", "LineChart", "TrendingUp", "Users",
    "MessageCircle", "PieChart", "BarChart3", "Target", "Lightbulb", "Rocket",
    "Building2", "Calculator", "FileText", "Search", "Globe", "ShoppingCart",
    "DollarSign", "Megaphone", "HeartHandshake", "GraduationCap", "Scale",
    "Stethoscope", "Code", "Database", "Newspaper", "Compass", "Award", "Brain",
})

# Palette de couleurs d'accent prédéfinie (cohérente avec le thème sombre existant).
ALLOWED_COLORS: frozenset[str] = frozenset({
    "#2D8659", "#3B82F6", "#8B5CF6", "#F59E0B",
    "#EF4444", "#EC4899", "#14B8A6", "#6366F1",
})


class PersonaCreate(BaseModel):
    """Payload pour créer un persona."""
    name: str = Field(..., min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=500)
    system_prompt: str = Field(..., min_length=10, max_length=5000)
    icon: str
    color: str

    @field_validator("icon")
    @classmethod
    def _validate_icon(cls, v: str) -> str:
        if v not in ALLOWED_ICONS:
            raise ValueError(f"Icône non autorisée : '{v}'")
        return v

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str) -> str:
        if v not in ALLOWED_COLORS:
            raise ValueError(f"Couleur non autorisée : '{v}'")
        return v


class PersonaUpdate(BaseModel):
    """Payload pour modifier un persona (tous les champs optionnels)."""
    name: str | None = Field(default=None, min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=500)
    system_prompt: str | None = Field(default=None, min_length=10, max_length=5000)
    icon: str | None = None
    color: str | None = None

    @field_validator("icon")
    @classmethod
    def _validate_icon(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_ICONS:
            raise ValueError(f"Icône non autorisée : '{v}'")
        return v

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_COLORS:
            raise ValueError(f"Couleur non autorisée : '{v}'")
        return v


class PersonaListItem(BaseModel):
    """Version compacte pour la liste (GET /personas)."""
    id: UUID
    name: str
    description: str | None = None
    icon: str
    color: str
    is_system: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PersonaDetail(PersonaListItem):
    """Version complète (GET/POST/PUT /personas/{id})."""
    system_prompt: str
    documents: list[DocumentListItem] = []
    corpora: list[CorpusSummary] = []

    model_config = ConfigDict(from_attributes=True)


class PersonaAddDocuments(BaseModel):
    document_ids: list[UUID]


class PersonaRemoveDocuments(BaseModel):
    document_ids: list[UUID]


class PersonaAddCorpora(BaseModel):
    corpus_ids: list[UUID]


class PersonaRemoveCorpora(BaseModel):
    corpus_ids: list[UUID]
