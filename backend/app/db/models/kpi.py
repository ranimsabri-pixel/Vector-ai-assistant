"""Modèles KPI et KPIValue."""
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.dataset import Dataset


class KPI(Base, IdMixin, TimestampMixin):
    __tablename__ = "kpis"

    dataset_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    display_format: Mapped[str] = mapped_column(String(50), default="number", nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    dataset: Mapped["Dataset"] = relationship(back_populates="kpis")
    values: Mapped[list["KPIValue"]] = relationship(
        back_populates="kpi", cascade="all, delete-orphan", order_by="KPIValue.computed_at.desc()"
    )


class KPIValue(Base, IdMixin):
    """Historique des valeurs calculées d'un KPI."""
    __tablename__ = "kpi_values"

    kpi_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("kpis.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    kpi: Mapped["KPI"] = relationship(back_populates="values")
