"""Schémas Pydantic pour les utilisateurs."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import validate_password_strength


class UserCreate(BaseModel):
    """Données d'inscription."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str | None = Field(default=None, max_length=255)

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UserUpdate(BaseModel):
    """Payload pour PATCH /users/me — mise a jour du profil."""
    full_name: str = Field(min_length=1, max_length=60)

    @field_validator("full_name")
    @classmethod
    def _trim_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Le nom ne peut pas être vide")
        return v


class PasswordChange(BaseModel):
    """Payload pour POST /users/me/password."""
    old_password: str
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class AccountDelete(BaseModel):
    """Payload pour DELETE /users/me — confirmation par mot de passe."""
    password: str


class UserResponse(BaseModel):
    """Données publiques d'un utilisateur (jamais le password)."""
    id: UUID
    email: EmailStr
    full_name: str | None = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True  # Permet de créer le schema depuis un objet SQLAlchemy


class OnboardingStatusResponse(BaseModel):
    """Etat d'onboarding d'un utilisateur (S5 J40)."""
    has_seen_welcome: bool
    has_datasets: bool
    has_documents: bool
    has_conversations: bool
    is_new: bool
