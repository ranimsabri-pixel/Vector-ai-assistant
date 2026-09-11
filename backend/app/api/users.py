"""Endpoints utilisateurs."""
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import hash_password, verify_password
from app.db.models.conversation import Conversation
from app.db.models.dataset import Dataset
from app.db.models.document import Document
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.dataset import DatasetResponse
from app.schemas.user import (
    AccountDelete,
    OnboardingStatusResponse,
    PasswordChange,
    UserResponse,
    UserUpdate,
)
from app.services.datasets import DatasetService, reprofile_in_background
from app.services.storage import FileStorage, get_storage

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Retourne les infos de l'utilisateur connecté."""
    return current_user


@router.get("/me/onboarding-status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OnboardingStatusResponse:
    """Etat d'onboarding (S5 J40) : permet au frontend de decider s'il faut
    afficher l'ecran de bienvenue a un utilisateur qui vient de s'inscrire."""
    has_datasets = await db.scalar(
        select(exists().where(Dataset.user_id == current_user.id))
    )
    has_documents = await db.scalar(
        select(exists().where(Document.user_id == current_user.id))
    )
    has_conversations = await db.scalar(
        select(exists().where(Conversation.user_id == current_user.id))
    )

    return OnboardingStatusResponse(
        has_seen_welcome=current_user.has_seen_welcome,
        has_datasets=bool(has_datasets),
        has_documents=bool(has_documents),
        has_conversations=bool(has_conversations),
        is_new=(
            not current_user.has_seen_welcome
            and not has_datasets
            and not has_documents
            and not has_conversations
        ),
    )


@router.post("/me/onboarding-complete", response_model=UserResponse)
async def complete_onboarding(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Marque l'ecran de bienvenue comme vu (S5 J40)."""
    current_user.has_seen_welcome = True
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/me/load-example-dataset", response_model=DatasetResponse)
async def load_example_dataset(
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[FileStorage, Depends(get_storage)],
) -> Dataset:
    """Charge le dataset d'exemple e-commerce dans le compte de l'utilisateur
    et lance le profilage en tache de fond (S5 J40, onboarding)."""
    service = DatasetService(db, storage)
    dataset = await service.load_example_dataset(current_user)
    background_tasks.add_task(reprofile_in_background, dataset.id, current_user.id)
    return dataset


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Met à jour le nom de l'utilisateur connecté (S5 J50)."""
    current_user.full_name = payload.full_name
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/me/password", status_code=status.HTTP_200_OK)
async def change_password(
    payload: PasswordChange,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Change le mot de passe de l'utilisateur connecté (S5 J50). Les comptes
    crees avec l'ancienne regle (min 8 caracteres, sans contrainte de
    complexite) restent utilisables pour le login ; seul le NOUVEAU mot de
    passe doit respecter la regle renforcee (validee par le schema)."""
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mot de passe actuel incorrect",
        )
    current_user.password_hash = hash_password(payload.new_password)
    await db.commit()
    return {"detail": "Mot de passe mis à jour"}


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    payload: AccountDelete,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Suppression definitive du compte (S5 J50) — hard delete, aucune
    corbeille. Le cascade ondelete='CASCADE' en base (verifie sur toutes
    les tables liees a users) vide automatiquement conversations, messages,
    datasets, documents, chunks, corpora, personas et leurs associations."""
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mot de passe incorrect",
        )
    await db.delete(current_user)
    await db.commit()
