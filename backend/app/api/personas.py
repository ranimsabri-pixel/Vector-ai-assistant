"""Endpoints Personas (S5 J49) — assistants personnalises.

9 endpoints :
- POST   /personas                          Creer un persona
- GET    /personas                          Lister mes personas + le systeme Vector
- GET    /personas/{persona_id}             Detail (avec documents/corpus lies)
- PUT    /personas/{persona_id}             Modifier (jamais le systeme)
- DELETE /personas/{persona_id}             Supprimer (jamais le systeme)
- POST   /personas/{persona_id}/documents           Lier des documents
- DELETE /personas/{persona_id}/documents/{doc_id}  Delier un document
- POST   /personas/{persona_id}/corpora             Lier des corpus
- DELETE /personas/{persona_id}/corpora/{corpus_id} Delier un corpus
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.persona import (
    PersonaAddCorpora,
    PersonaAddDocuments,
    PersonaCreate,
    PersonaDetail,
    PersonaListItem,
    PersonaUpdate,
)
from app.services.personas import PersonaService

router = APIRouter(prefix="/personas", tags=["personas"])


# ============================================================
# Create
# ============================================================

@router.post("", response_model=PersonaDetail, status_code=status.HTTP_201_CREATED)
async def create_persona(
    payload: PersonaCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Cree un nouveau persona utilisateur."""
    service = PersonaService(db)
    persona = await service.create_persona(
        user=current_user,
        name=payload.name,
        description=payload.description,
        system_prompt=payload.system_prompt,
        icon=payload.icon,
        color=payload.color,
    )
    return await service.get_persona(current_user, persona.id)


# ============================================================
# Read
# ============================================================

@router.get("", response_model=list[PersonaListItem])
async def list_personas(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Liste mes personas + le persona systeme Vector."""
    service = PersonaService(db)
    return await service.list_personas(current_user)


@router.get("/{persona_id}", response_model=PersonaDetail)
async def get_persona(
    persona_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Detail d'un persona (le sien, ou le persona systeme) avec ses sources."""
    service = PersonaService(db)
    return await service.get_persona(current_user, persona_id)


# ============================================================
# Update
# ============================================================

@router.put("/{persona_id}", response_model=PersonaDetail)
async def update_persona(
    persona_id: UUID,
    payload: PersonaUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Modifie un persona. 404 si non possede ou si c'est le persona systeme."""
    service = PersonaService(db)
    await service.update_persona(
        current_user,
        persona_id,
        name=payload.name,
        description=payload.description,
        system_prompt=payload.system_prompt,
        icon=payload.icon,
        color=payload.color,
    )
    return await service.get_persona(current_user, persona_id)


# ============================================================
# Delete
# ============================================================

@router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_persona(
    persona_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Supprime un persona. 404 si non possede ou si c'est le persona systeme."""
    service = PersonaService(db)
    await service.delete_persona(current_user, persona_id)


# ============================================================
# Documents — link / unlink
# ============================================================

@router.post("/{persona_id}/documents", response_model=PersonaDetail)
async def link_documents(
    persona_id: UUID,
    payload: PersonaAddDocuments,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Associe des documents (possedes par l'user) a un persona."""
    service = PersonaService(db)
    await service.add_documents(current_user, persona_id, payload.document_ids)
    return await service.get_persona(current_user, persona_id)


@router.delete("/{persona_id}/documents/{document_id}", response_model=PersonaDetail)
async def unlink_document(
    persona_id: UUID,
    document_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Retire un document d'un persona (le document lui-meme reste)."""
    service = PersonaService(db)
    await service.remove_document(current_user, persona_id, document_id)
    return await service.get_persona(current_user, persona_id)


# ============================================================
# Corpus — link / unlink
# ============================================================

@router.post("/{persona_id}/corpora", response_model=PersonaDetail)
async def link_corpora(
    persona_id: UUID,
    payload: PersonaAddCorpora,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Associe des corpus (possedes par l'user) a un persona."""
    service = PersonaService(db)
    await service.add_corpora(current_user, persona_id, payload.corpus_ids)
    return await service.get_persona(current_user, persona_id)


@router.delete("/{persona_id}/corpora/{corpus_id}", response_model=PersonaDetail)
async def unlink_corpus(
    persona_id: UUID,
    corpus_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Retire un corpus d'un persona (le corpus lui-meme reste)."""
    service = PersonaService(db)
    await service.remove_corpus(current_user, persona_id, corpus_id)
    return await service.get_persona(current_user, persona_id)
