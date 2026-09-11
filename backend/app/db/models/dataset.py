"""Modèles Dataset et DatasetColumn."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.analysis import Analysis
    from app.db.models.dashboard import Dashboard
    from app.db.models.kpi import KPI
    from app.db.models.saved_dashboard import SavedDashboard
    from app.db.models.user import User


class Dataset(Base, IdMixin, TimestampMixin):
    """Un fichier de données uploadé par un utilisateur."""

    __tablename__ = "datasets"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Métadonnées utilisateur
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)

    # Informations de fichier
    original_filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    file_size_bytes: Mapped[int] = mapped_column(Integer)

    # Métadonnées du dataset
    row_count: Mapped[int | None] = mapped_column(Integer)
    column_count: Mapped[int | None] = mapped_column(Integer)

    # Qualité du dataset (rempli en J7)
    quality_score: Mapped[float | None] = mapped_column(Float)
    quality_issues: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # État du traitement
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    error_message: Mapped[str | None] = mapped_column(Text)

    # Aperçu des 5 premières lignes (rempli à l'upload)
    raw_data_sample: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    semantic_analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    auto_kpis: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Corrections colonnes soumises a l'upload (S5 J38), appliquees au
    # prochain profilage puis effacees. Voir DatasetService.profile().
    pending_column_overrides: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)

    # Relations
    user: Mapped[User] = relationship(back_populates="datasets")
    columns: Mapped[list[DatasetColumn]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
    )
    analyses: Mapped[list[Analysis]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
    )
    dashboards: Mapped[list[Dashboard]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
    )
    saved_dashboards: Mapped[list[SavedDashboard]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
    )
    kpis: Mapped[list[KPI]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
    )


class DatasetColumn(Base, IdMixin):
    """Métadonnées et profilage d'une colonne d'un dataset."""

    __tablename__ = "dataset_columns"

    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )

    # Métadonnées de la colonne
    name: Mapped[str] = mapped_column(String(255))
    dtype: Mapped[str | None] = mapped_column(String(50))
    is_nullable: Mapped[bool | None] = mapped_column(Boolean)
    is_date_main: Mapped[bool | None] = mapped_column(Boolean)

    # Profilage (rempli en J7)
    unique_count: Mapped[int | None] = mapped_column(Integer)
    null_count: Mapped[int | None] = mapped_column(Integer)
    sample_values: Mapped[list[Any] | None] = mapped_column(JSONB)

    # Statistiques enrichies par colonne (S5 J39) : histogramme, top-10,
    # distribution temporelle. Nullable — absentes tant qu'un dataset n'a
    # pas été (re)profilé depuis leur introduction.
    numeric_stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    categorical_stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    date_stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Relation
    dataset: Mapped[Dataset] = relationship(back_populates="columns")
