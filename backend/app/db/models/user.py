"""Modèle User — comptes utilisateurs."""
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.conversation import Conversation
    from app.db.models.corpus import Corpus
    from app.db.models.dataset import Dataset
    from app.db.models.document import Document
    from app.db.models.persona import Persona
    from app.db.models.saved_dashboard import SavedDashboard

class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Onboarding (S5 J40) : passe a true une fois l'ecran de bienvenue vu/ferme.
    has_seen_welcome: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    # Relations
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    datasets: Mapped[list["Dataset"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    corpora: Mapped[list["Corpus"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    saved_dashboards: Mapped[list["SavedDashboard"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    personas: Mapped[list["Persona"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

