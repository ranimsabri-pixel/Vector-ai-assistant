"""Modèle Analysis — résultats des analyses spécialisées."""
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.dataset import Dataset


class Analysis(Base, IdMixin, TimestampMixin):
    __tablename__ = "analyses"

    dataset_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)

    dataset: Mapped["Dataset"] = relationship(back_populates="analyses")
