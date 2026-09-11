"""Modeles SavedDashboard et DashboardWidget — dashboards personnalises (S5 J36).

Couche separee de l'ancien modele Dashboard (db/models/dashboard.py, snapshots
generes par les tools LLM) : un SavedDashboard est une collection de widgets
configures manuellement par l'utilisateur, editable dans le temps.
"""
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.dataset import Dataset
    from app.db.models.user import User


class SavedDashboard(Base, IdMixin, TimestampMixin):
    """Un dashboard personnalise : nom, dataset source, collection de widgets."""
    __tablename__ = "saved_dashboards"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    dataset_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relations
    user: Mapped["User"] = relationship(back_populates="saved_dashboards")
    dataset: Mapped["Dataset"] = relationship(back_populates="saved_dashboards")
    widgets: Mapped[list["DashboardWidget"]] = relationship(
        back_populates="dashboard",
        cascade="all, delete-orphan",
        order_by="DashboardWidget.position",
    )


class DashboardWidget(Base, IdMixin, TimestampMixin):
    """Un widget autonome (type + config + position) au sein d'un SavedDashboard."""
    __tablename__ = "dashboard_widgets"

    dashboard_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("saved_dashboards.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Valeurs : kpi, bar_chart, line_chart, pie_chart, data_table,
    #           donut_chart, radar_chart, scatter_plot, heatmap,
    #           correlation_matrix, histogram
    widget_type: Mapped[str] = mapped_column(String(30), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relation
    dashboard: Mapped["SavedDashboard"] = relationship(back_populates="widgets")
