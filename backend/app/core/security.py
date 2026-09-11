"""
Fonctions cryptographiques : hashing de mots de passe (bcrypt) et JWT.
"""
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# Contexte bcrypt avec algorithme par défaut
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================
# Mots de passe (bcrypt)
# ============================================================

def hash_password(password: str) -> str:
    """Hash un mot de passe en clair avec bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie qu'un mot de passe en clair correspond au hash."""
    return pwd_context.verify(plain_password, hashed_password)


def validate_password_strength(password: str) -> str:
    """Regle commune signup + changement de mot de passe (S5 J50) :
    min 8 caracteres, au moins une lettre et un chiffre. Les comptes
    crees avant cette regle ne sont pas invalides (le login ne repasse
    pas par cette validation), seuls les nouveaux mots de passe la
    respectent."""
    if not any(c.isalpha() for c in password):
        raise ValueError("Le mot de passe doit contenir au moins une lettre")
    if not any(c.isdigit() for c in password):
        raise ValueError("Le mot de passe doit contenir au moins un chiffre")
    return password


# ============================================================
# JWT (JSON Web Tokens)
# ============================================================

def create_access_token(subject: str | UUID, expires_delta: timedelta | None = None) -> str:
    """
    Crée un JWT avec le sujet (sub = id utilisateur) et une expiration.
    Si expires_delta est None, utilise la valeur par défaut des settings.
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any] | None:
    """
    Décode un JWT. Retourne le payload si valide, None sinon.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
