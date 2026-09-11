"""Endpoints Corpus (S5 J34) — collections thematiques de documents.

8 endpoints :
- POST   /corpora                     Creer un corpus
- GET    /corpora                     Lister mes corpus (avec document_count)
- GET    /corpora/{corpus_id}         Detail d'un corpus (avec documents)
- PATCH  /corpora/{corpus_id}         Renommer / editer description
- DELETE /corpora/{corpus_id}         Supprimer (les documents restent)
- POST   /corpora/{corpus_id}/documents           Ajouter des documents existants
- DELETE /corpora/{corpus_id}/documents           Retirer des documents
- POST   /corpora/{corpus_id}/documents/upload    Uploader et attacher (S5 J51)
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.documents import _trigger_ingestion
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.corpus import (
    CorpusAddDocuments,
    CorpusCreate,
    CorpusDetail,
    CorpusRemoveDocuments,
    CorpusSummary,
    CorpusUpdate,
    CorpusUploadedFile,
    CorpusUploadError,
    CorpusUploadResponse,
)
from app.services.corpus import CorpusService
from app.services.documents import DocumentService
from app.services.storage import FileStorage, get_storage

router = APIRouter(prefix="/corpora", tags=["corpus"])

MAX_FILES_PER_UPLOAD = 10


# ============================================================
# Create
# ============================================================

@router.post("", response_model=CorpusDetail, status_code=status.HTTP_201_CREATED)
async def create_corpus(
    payload: CorpusCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Cree un nouveau corpus (vide au depart)."""
    service = CorpusService(db)
    corpus = await service.create_corpus(
        user=current_user, name=payload.name, description=payload.description
    )
    return await service.get_corpus(current_user, corpus.id)


# ============================================================
# Read
# ============================================================

@router.get("", response_model=list[CorpusSummary])
async def list_corpora(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Liste mes corpus (avec le nombre de documents inclus)."""
    service = CorpusService(db)
    return await service.list_corpora(current_user)


@router.get("/{corpus_id}", response_model=CorpusDetail)
async def get_corpus(
    corpus_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Detail d'un corpus avec la liste de ses documents."""
    service = CorpusService(db)
    return await service.get_corpus(current_user, corpus_id)


# ============================================================
# Update
# ============================================================

@router.patch("/{corpus_id}", response_model=CorpusDetail)
async def update_corpus(
    corpus_id: UUID,
    payload: CorpusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Renomme et/ou change la description d'un corpus."""
    service = CorpusService(db)
    await service.update_corpus(
        current_user, corpus_id, name=payload.name, description=payload.description
    )
    return await service.get_corpus(current_user, corpus_id)


# ============================================================
# Delete
# ============================================================

@router.delete("/{corpus_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_corpus(
    corpus_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Supprime un corpus (les documents lies restent intacts)."""
    service = CorpusService(db)
    await service.delete_corpus(current_user, corpus_id)


# ============================================================
# Documents — add / remove
# ============================================================

@router.post("/{corpus_id}/documents", response_model=CorpusDetail)
async def add_documents_to_corpus(
    corpus_id: UUID,
    payload: CorpusAddDocuments,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Ajoute des documents existants a un corpus."""
    service = CorpusService(db)
    await service.add_documents(current_user, corpus_id, payload.document_ids)
    return await service.get_corpus(current_user, corpus_id)


@router.post(
    "/{corpus_id}/documents/upload",
    response_model=CorpusUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_documents_to_corpus(
    corpus_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
    files: Annotated[list[UploadFile], File(description="1 a 10 fichiers")],
):
    """Upload direct de nouveaux documents, attaches au corpus (S5 J51).

    PDF, DOCX, PPTX, TXT, MD -- max 50 Mo par fichier, 10 fichiers par
    requete. Chaque fichier est valide independamment : un fichier
    invalide/corrompu n'empeche pas les autres d'etre crees et ingeres.
    Si AUCUN fichier n'a pu etre cree, l'erreur du premier echec est levee
    telle quelle (400/413/...) plutot que de renvoyer un 201 vide.
    """
    corpus_service = CorpusService(db)
    document_service = DocumentService(db, storage)

    # Ownership du corpus verifie AVANT de traiter le moindre fichier (sinon
    # un upload sur un corpus d'autrui sauverait des fichiers orphelins sur
    # disque avant d'echouer au moment de les lier).
    await corpus_service.get_corpus(current_user, corpus_id)

    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Maximum {MAX_FILES_PER_UPLOAD} fichiers par requête "
            f"({len(files)} reçus).",
        )

    uploaded: list[CorpusUploadedFile] = []
    errors: list[CorpusUploadError] = []
    first_error: HTTPException | None = None

    for file in files:
        try:
            document = await document_service.upload(current_user, file)
        except HTTPException as e:
            errors.append(
                CorpusUploadError(filename=file.filename or "?", error=str(e.detail))
            )
            if first_error is None:
                first_error = e
            continue

        await corpus_service.add_documents(current_user, corpus_id, [document.id])

        absolute_path = str(storage.get_full_path(document.file_path))
        background_tasks.add_task(
            _trigger_ingestion,
            document_id=document.id,
            absolute_file_path=absolute_path,
        )

        uploaded.append(
            CorpusUploadedFile(
                document_id=document.id, filename=file.filename or "?", status=document.status
            )
        )

    if not uploaded and errors:
        # Rien n'a pu etre cree : on remonte la vraie erreur (400/413/...)
        # plutot qu'un 201 avec une liste "uploaded" vide.
        raise first_error  # type: ignore[misc]

    return CorpusUploadResponse(uploaded=uploaded, errors=errors)


@router.delete("/{corpus_id}/documents", response_model=CorpusDetail)
async def remove_documents_from_corpus(
    corpus_id: UUID,
    payload: CorpusRemoveDocuments,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Retire des documents d'un corpus (les documents eux-memes restent)."""
    service = CorpusService(db)
    await service.remove_documents(current_user, corpus_id, payload.document_ids)
    return await service.get_corpus(current_user, corpus_id)
