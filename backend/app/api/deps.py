"""
Dependencies FastAPI partagées entre tous les endpoints.
"""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import TokenPayload

# OAuth2 scheme pointant vers notre endpoint de login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Décode le JWT du header Authorization, retourne l'utilisateur correspondant.
    Lève 401 si le token est invalide, expiré, ou si l'utilisateur n'existe plus.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Identifiants invalides",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    try:
        token_data = TokenPayload(**payload)
    except (ValueError, TypeError):
        raise credentials_exception from None

    # Récupérer l'utilisateur depuis la base
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Utilisateur inactif",
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Alias de get_current_user pour clarté sémantique."""
    return current_user
