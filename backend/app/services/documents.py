"""DocumentService (S5 J22) — orchestre upload + ingestion en background.

Pattern identique à DatasetService (J6) :
- __init__(db, storage)
- upload() : sauve fichier + crée record BDD, ingestion en BackgroundTask
- list / get / delete : CRUD standard
"""
from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Chunk, Document
from app.db.models.user import User
from app.services.storage import FileStorage

logger = logging.getLogger(__name__)

# Limites
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 Mo
# NEW J32 (docx) + J35 (pptx) + J51 (txt/md)
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md"}

# Extension -> file_type stocke en BDD
EXTENSION_TO_FILE_TYPE = {
    ".pdf": "pdf", ".docx": "docx", ".pptx": "pptx", ".txt": "txt", ".md": "md",
}

# Anciens formats binaires Office non supportes -> message d'erreur dedie
LEGACY_OFFICE_EXTENSIONS = {
    ".doc": "Word",
    ".ppt": "PowerPoint",
}


class DocumentService:
    def __init__(self, db: AsyncSession, storage: FileStorage):
        self.db = db
        self.storage = storage

    # ============================================================
    # Upload
    # ============================================================

    async def upload(
        self,
        user: User,
        file: UploadFile,
        name: str | None = None,
    ) -> Document:
        """Upload un PDF et crée un record Document (status='uploaded').

        L'ingestion (parse + chunk + embed) sera lancée en BackgroundTask
        depuis l'endpoint après le commit.
        """
        # Validation extension
        if not file.filename:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Nom de fichier manquant"
            )

        ext = Path(file.filename).suffix.lower()

        # .doc / .ppt (anciens formats binaires Office) : message dédié,
        # python-docx/python-pptx ne savent lire que le format OpenXML
        if ext in LEGACY_OFFICE_EXTENSIONS:
            app_name = LEGACY_OFFICE_EXTENSIONS[ext]
            new_ext = ".docx" if ext == ".doc" else ".pptx"
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Format {ext} (ancien {app_name} binaire) non supporté. "
                f"Enregistre le fichier au format {new_ext} et réessaie.",
            )

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Format non supporté. PDF, DOCX, PPTX, TXT ou MD uniquement. "
                f"Acceptées : {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        file_type = EXTENSION_TO_FILE_TYPE[ext]

        # Sauvegarde disque (réutilise la méthode de FileStorage)
        try:
            relative_path, size = await self.storage.save_upload(
                file, user.id, max_size=MAX_FILE_SIZE
            )
        except ValueError as e:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(e)
            ) from e

        # Création record BDD
        document = Document(
            user_id=user.id,
            name=name or file.filename,
            original_filename=file.filename,
            file_type=file_type,
            file_path=relative_path,
            file_size_bytes=size,
            status="uploaded",
            chunk_count=0,
        )
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        logger.info(
            "Document uploaded by user %s : %s (%d bytes)",
            user.id, file.filename, size,
        )
        return document

    # ============================================================
    # Read
    # ============================================================

    async def list_user_documents(self, user: User) -> list[Document]:
        """Liste les documents de l'utilisateur (récents d'abord)."""
        result = await self.db.execute(
            select(Document)
            .where(Document.user_id == user.id)
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_document(self, user: User, document_id: UUID) -> Document:
        """Récupère un document avec ownership check."""
        document = await self.db.get(Document, document_id)
        if not document or document.user_id != user.id:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Document introuvable"
            )
        return document

    async def list_chunks(
        self, user: User, document_id: UUID
    ) -> list[Chunk]:
        """Liste les chunks d'un document (pour debug/visualisation)."""
        # Vérifie l'ownership
        await self.get_document(user, document_id)

        result = await self.db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        )
        return list(result.scalars().all())

    # ============================================================
    # Delete
    # ============================================================

    async def delete_document(self, user: User, document_id: UUID) -> None:
        """Supprime un document (et ses chunks par cascade)."""
        document = await self.get_document(user, document_id)
        # Cascade Postgres supprime aussi les chunks
        await self.db.delete(document)
        await self.db.commit()

    # ============================================================
    # Reingest (S5 J36) — refait extraction + chunking + embedding
    # ============================================================

    async def prepare_reingest(self, user: User, document_id: UUID) -> Document:
        """Prépare un document pour une ré-ingestion complète.

        Supprime les anciens chunks (sinon doublons au prochain retrieval),
        remet le status à 'parsing'. Le BackgroundTask d'ingestion est
        déclenché par l'endpoint après l'appel à cette méthode.
        """
        document = await self.get_document(user, document_id)

        if document.status in ("parsing", "chunking", "embedding"):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Une ingestion est déjà en cours (status={document.status}).",
            )

        # Supprime les chunks existants pour éviter les doublons
        await self.db.execute(
            Chunk.__table__.delete().where(Chunk.document_id == document_id)
        )

        document.status = "parsing"
        document.chunk_count = 0
        document.page_count = None
        document.error_message = None

        await self.db.commit()
        await self.db.refresh(document)
        return document
