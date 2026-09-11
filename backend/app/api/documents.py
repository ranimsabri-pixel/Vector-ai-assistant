"""Endpoints Documents (S5 J22) — pipeline RAG complet.

J21 : squelette CRUD (list + get + delete)
J22 : enrichissement upload + ingestion BackgroundTask + visualisation chunks
J25.A : endpoint /download pour le viewer PDF frontend
"""
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.demo_guard import ensure_demo_enabled
from app.core.limiter import limiter
from app.db.models.document import Document
from app.db.models.user import User
from app.db.session import AsyncSessionLocal, get_db
from app.schemas.document import (
    ChunkPreview,
    DocumentListItem,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.services.documents import DocumentService
from app.services.ingestion import ingest_document
from app.services.storage import FileStorage, get_storage

router = APIRouter(prefix="/documents", tags=["documents"])


# ============================================================
# Helper : trigger ingestion en BackgroundTask avec sa propre session
# ============================================================

async def _trigger_ingestion(
    document_id: UUID,
    absolute_file_path: str,
) -> None:
    """Wrapper qui crée sa propre AsyncSession pour la background task.

    On ne peut PAS réutiliser la session de la requête HTTP : elle est
    fermée dès que la réponse 201 est envoyée. On ouvre donc une session
    dédiée via AsyncSessionLocal (exporté par db/session.py).
    """
    async with AsyncSessionLocal() as bg_db:
        try:
            await ingest_document(
                document_id=document_id,
                absolute_file_path=absolute_file_path,
                db=bg_db,
            )
        except Exception:
            # ingest_document gère déjà ses erreurs (status='error').
            # Ce except est juste une ceinture de sécurité.
            await bg_db.rollback()


# ============================================================
# Upload + déclenchement de l'ingestion
# ============================================================

@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(ensure_demo_enabled)],
)
@limiter.limit("3/hour")
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
    file: Annotated[UploadFile, File(description="Fichier PDF (max 50 Mo)")],
    name: Annotated[str | None, Form()] = None,
):
    """Upload un PDF. L'ingestion (parse + chunk + embed) se fait en background.

    Le client doit poller GET /documents/{id} pour suivre l'avancement.
    """
    service = DocumentService(db, storage)
    document = await service.upload(current_user, file, name=name)

    # Chemin absolu disque pour la background task
    absolute_path = str(storage.get_full_path(document.file_path))

    # Déclenche l'ingestion en arrière-plan (la réponse 201 part immédiatement)
    background_tasks.add_task(
        _trigger_ingestion,
        document_id=document.id,
        absolute_file_path=absolute_path,
    )

    return document


# ============================================================
# Reingest (S5 J36) — refait extraction + chunking + embedding
# ============================================================

@router.post("/{document_id}/reingest", response_model=DocumentResponse)
async def reingest_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Refait l'ingestion complete d'un document deja uploade.

    Utile apres une amelioration de l'extraction (ex: passage a pymupdf) :
    supprime les anciens chunks, remet le status a 'parsing', relance le
    pipeline extract -> chunk -> embed en background. Ownership verifie
    par DocumentService.get_document (appele dans prepare_reingest).
    """
    service = DocumentService(db, storage)
    document = await service.prepare_reingest(current_user, document_id)

    absolute_path = str(storage.get_full_path(document.file_path))
    background_tasks.add_task(
        _trigger_ingestion,
        document_id=document.id,
        absolute_file_path=absolute_path,
    )

    return document


# ============================================================
# Read
# ============================================================

@router.get("", response_model=list[DocumentListItem])
async def list_documents(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Liste les documents de l'utilisateur (récents d'abord)."""
    service = DocumentService(db, storage)
    return await service.list_user_documents(current_user)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Récupère un document. Sert au polling (status passe à ready)."""
    service = DocumentService(db, storage)
    return await service.get_document(current_user, document_id)


@router.get(
    "/{document_id}/chunks",
    response_model=list[ChunkPreview],
)
async def list_chunks(
    document_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Liste les chunks d'un document (visualisation/debug)."""
    service = DocumentService(db, storage)
    chunks = await service.list_chunks(current_user, document_id)
    # Conversion en ChunkPreview (booléen has_embedding au lieu du vecteur)
    return [
        ChunkPreview(
            id=c.id,
            document_id=c.document_id,
            chunk_index=c.chunk_index,
            page_number=c.page_number,
            content=c.content,
            token_count=c.token_count,
            has_embedding=c.embedding is not None,
        )
        for c in chunks
    ]


# ============================================================
# Download (J25.A — pour le viewer PDF frontend)
# ============================================================

@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """
    Retourne le fichier PDF binaire pour affichage inline (react-pdf).
    Ownership check : le user doit être propriétaire du document.
    """
    # 1. Récupère le document + ownership check
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document introuvable ou accès refusé",
        )

    # 2. Vérifie que le document n'est pas en erreur
    if doc.status == "error":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "Document en erreur : "
                f"{doc.error_message or 'ingestion échouée'}"
            ),
        )

    # 3. Convertit le relative_path (BDD) en Path absolu (disque)
    file_path = storage.get_full_path(doc.file_path)

    # 4. Vérifie que le fichier existe physiquement
    if not file_path.exists():
        # TEMPORARY diagnostic (cf commit diag(temp): expose file
        # resolution details in 410 response) -- a revert immediatement
        # apres identification de la cause racine du 410 en prod.
        import os

        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "message": "Fichier physique introuvable sur disque",
                "debug": {
                    "file_path_db": doc.file_path,
                    "resolved_path": str(file_path.absolute()),
                    "cwd": os.getcwd(),
                    "base_dir": str(storage.base_dir.absolute()),
                    "parent_exists": file_path.parent.exists(),
                    "parent_listing": (
                        [p.name for p in file_path.parent.iterdir()]
                        if file_path.parent.exists()
                        else None
                    ),
                },
            },
        )

    # 5. MIME selon le format (inline pour PDF affiché par react-pdf,
    #    attachment pour DOCX/PPTX qu'on ne sait pas prévisualiser côté frontend)
    if doc.file_type == "docx":
        media_type = (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        )
        disposition = "attachment"
    elif doc.file_type == "pptx":
        media_type = (
            "application/vnd.openxmlformats-officedocument"
            ".presentationml.presentation"
        )
        disposition = "attachment"
    else:
        media_type = "application/pdf"
        disposition = "inline"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=doc.original_filename,
        headers={
            "Content-Disposition": f'{disposition}; filename="{doc.original_filename}"',
        },
    )


# ============================================================
# Delete
# ============================================================

@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Supprime un document et ses chunks (par cascade)."""
    service = DocumentService(db, storage)
    await service.delete_document(current_user, document_id)
