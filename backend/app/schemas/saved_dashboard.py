"""Schémas Pydantic pour les SavedDashboard / DashboardWidget (S5 J36)."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

WidgetType = Literal[
    "kpi", "bar_chart", "line_chart", "pie_chart", "data_table",
    "donut_chart", "radar_chart", "scatter_plot", "heatmap",
    "correlation_matrix", "histogram",
]


class DashboardWidgetCreate(BaseModel):
    """Payload pour créer un widget (POST /saved-dashboards/{id}/widgets)."""
    widget_type: WidgetType
    title: str
    config: dict[str, Any]
    position: int = 0


class DashboardWidgetUpdate(BaseModel):
    """Payload pour PATCH d'un widget."""
    title: str | None = None
    config: dict[str, Any] | None = None
    position: int | None = None


class DashboardWidgetResponse(DashboardWidgetCreate):
    """Widget tel que retourné par l'API."""
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class SavedDashboardCreate(BaseModel):
    """Payload pour créer un dashboard (avec ou sans widgets initiaux)."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    dataset_id: UUID
    widgets: list[DashboardWidgetCreate] = []


class SavedDashboardUpdate(BaseModel):
    """Payload pour PATCH (renommer / redécrire)."""
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class SavedDashboardSummary(BaseModel):
    """Dashboard léger (pour la liste)."""
    id: UUID
    name: str
    description: str | None = None
    dataset_id: UUID
    dataset_name: str  # dénormalisé pour éviter N+1
    widget_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SavedDashboardDetail(SavedDashboardSummary):
    """Dashboard complet avec tous ses widgets."""
    widgets: list[DashboardWidgetResponse] = []

    model_config = ConfigDict(from_attributes=True)


class WidgetReorderPayload(BaseModel):
    """Payload pour POST /saved-dashboards/{id}/widgets/reorder."""
    widget_ids: list[UUID]


class WidgetPreviewRequest(BaseModel):
    """Payload pour POST /saved-dashboards/{id}/preview (widget non persisté)."""
    widget_type: WidgetType
    config: dict[str, Any]
