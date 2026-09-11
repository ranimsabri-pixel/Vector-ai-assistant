"""Schémas Pydantic pour les datasets."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class DatasetResponse(BaseModel):
    """Réponse API complète d'un dataset (avec sample)."""

    id: UUID
    user_id: UUID
    name: str
    description: str | None = None

    original_filename: str
    file_path: str
    file_size_bytes: int

    row_count: int | None = None
    column_count: int | None = None

    status: str
    error_message: str | None = None
    quality_score: float | None = None
    quality_issues: dict[str, Any] | None = None

    raw_data_sample: dict[str, Any] | None = None
    semantic_analysis: dict[str, Any] | None = None
    auto_kpis: dict[str, Any] | None = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DatasetListResponse(BaseModel):
    """Version allégée pour les listes (sans le sample qui peut être gros)."""

    id: UUID
    name: str
    description: str | None = None
    original_filename: str
    file_size_bytes: int
    row_count: int | None = None
    column_count: int | None = None
    status: str
    quality_score: float | None = None
    semantic_analysis: dict[str, Any] | None = None
    auto_kpis: dict[str, Any] | None = None
    created_at: datetime

    # NEW J20 : actions rapides auxquelles ce dataset correspond
    # (calculé par le service à partir des noms de colonnes profilées)
    matches_for_action: list[str] = []

    class Config:
        from_attributes = True


class ColumnOverrideItem(BaseModel):
    """Une correction de colonne (rename / delete / force-type), demandee a
    l'upload (J38.D) ou apres coup via PATCH /datasets/{id}/columns (J38.E)."""

    original_name: str
    new_name: str | None = None
    type: str | None = None
    deleted: bool | None = None


class ColumnOverridesUpdateRequest(BaseModel):
    """Corps du PATCH /datasets/{id}/columns : liste des corrections a
    fusionner avec celles deja appliquees, avant de relancer le profilage."""

    overrides: list[ColumnOverrideItem]


class DatasetColumnResponse(BaseModel):
    """Métadonnées d'une colonne profilée d'un dataset."""

    id: UUID
    dataset_id: UUID
    name: str
    dtype: str | None = None
    is_nullable: bool | None = None
    is_date_main: bool | None = None
    null_count: int | None = None
    unique_count: int | None = None
    sample_values: dict[str, Any] | None = None

    # Statistiques enrichies par colonne (S5 J39)
    numeric_stats: dict[str, Any] | None = None
    categorical_stats: dict[str, Any] | None = None
    date_stats: dict[str, Any] | None = None

    class Config:
        from_attributes = True


class KPISpecResponse(BaseModel):
    """Spec d'un KPI auto-calculable."""

    id: str
    title: str
    description: str
    type: str
    column: str | None = None
    unit: str | None = None
    icon: str | None = None
    category: str = "general"


class KPIResultResponse(BaseModel):
    """Résultat d'un calcul de KPI."""

    spec_id: str
    value: float | int | str
    raw_value: float | int | None = None
    formatted: str
    unit: str | None = None
    chart_type: str = "number"
    metadata: dict[str, Any] | None = None
