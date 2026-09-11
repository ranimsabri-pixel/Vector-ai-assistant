"""Modèle Dashboard — snapshots des KPIs générés par Vector."""
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.dataset import Dataset


class Dashboard(Base, IdMixin, TimestampMixin):
    __tablename__ = "dashboards"

    # === Relations ===
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
    conversation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )

    # === Métadonnées ===
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(30), default="kpi_general", nullable=False)

    # === Contenu visuel (HTML rendu, pour S4+) ===
    html_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    json_source: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # === Snapshot des KPIs (J14) ===
    kpi_specs: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    kpi_results: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # === Relations ORM ===
    dataset: Mapped["Dataset"] = relationship(back_populates="dashboards")
