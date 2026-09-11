"""CorpusService (S5 J34) — CRUD + gestion des documents d'un corpus.

Pattern identique a ConversationService : constructeur (db), methodes
async avec ownership check systematique via user en 1er arg.
"""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.corpus import Corpus, CorpusDocument
from app.db.models.document import Document
from app.db.models.user import User


class CorpusService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # Create
    # ============================================================

    async def create_corpus(
        self, user: User, name: str, description: str | None = None
    ) -> Corpus:
        """Cree un corpus vide."""
        corpus = Corpus(user_id=user.id, name=name, description=description)
        self.db.add(corpus)
        await self.db.commit()
        await self.db.refresh(corpus)
        return corpus

    # ============================================================
    # Read
    # ============================================================

    async def list_corpora(self, user: User) -> list[dict]:
        """Liste des corpus de l'utilisateur avec document_count (sans N+1)."""
        doc_count_subq = (
            select(
                CorpusDocument.corpus_id,
                func.count(CorpusDocument.document_id).label("doc_count"),
            )
            .group_by(CorpusDocument.corpus_id)
            .subquery()
        )

        query = (
            select(
                Corpus,
                func.coalesce(doc_count_subq.c.doc_count, 0).label("document_count"),
            )
            .outerjoin(doc_count_subq, doc_count_subq.c.corpus_id == Corpus.id)
            .where(Corpus.user_id == user.id)
            .order_by(Corpus.updated_at.desc())
        )

        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "id": corpus.id,
                "name": corpus.name,
                "description": corpus.description,
                "document_count": doc_count,
                "created_at": corpus.created_at,
                "updated_at": corpus.updated_at,
            }
            for corpus, doc_count in rows
        ]

    async def get_corpus(self, user: User, corpus_id: UUID) -> dict:
        """Recupere un corpus complet avec ses documents (ownership check)."""
        result = await self.db.execute(
            select(Corpus)
            .options(selectinload(Corpus.documents))
            .where(Corpus.id == corpus_id, Corpus.user_id == user.id)
        )
        corpus = result.scalar_one_or_none()
        if corpus is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Corpus introuvable ou accès refusé"
            )

        return {
            "id": corpus.id,
            "name": corpus.name,
            "description": corpus.description,
            "document_count": len(corpus.documents),
            "created_at": corpus.created_at,
            "updated_at": corpus.updated_at,
            "documents": corpus.documents,
        }

    # ============================================================
    # Update
    # ============================================================

    async def update_corpus(
        self,
        user: User,
        corpus_id: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> Corpus:
        """Renomme et/ou change la description d'un corpus."""
        corpus = await self._get_owned(user, corpus_id)
        if name is not None:
            corpus.name = name
        if description is not None:
            corpus.description = description
        await self.db.commit()
        await self.db.refresh(corpus)
        return corpus

    # ============================================================
    # Delete
    # ============================================================

    async def delete_corpus(self, user: User, corpus_id: UUID) -> None:
        """Supprime un corpus. Les documents lies ne sont PAS supprimes
        (seule la table de jointure corpus_documents est videe par cascade)."""
        corpus = await self._get_owned(user, corpus_id)
        await self.db.delete(corpus)
        await self.db.commit()

    # ============================================================
    # Documents — add / remove
    # ============================================================

    async def add_documents(
        self, user: User, corpus_id: UUID, document_ids: list[UUID]
    ) -> Corpus:
        """Ajoute des documents a un corpus.

        Verifie que TOUS les documents appartiennent a l'user AVANT
        d'en ajouter un seul (pas d'ajout partiel silencieux).
        """
        corpus = await self._get_owned(user, corpus_id)
        if not document_ids:
            return corpus

        requested_ids = set(document_ids)

        result = await self.db.execute(
            select(Document.id).where(
                Document.id.in_(requested_ids),
                Document.user_id == user.id,
            )
        )
        owned_ids = {row[0] for row in result.all()}
        missing = requested_ids - owned_ids
        if missing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Document(s) introuvable(s) ou accès refusé : "
                + ", ".join(str(m) for m in missing),
            )

        existing_result = await self.db.execute(
            select(CorpusDocument.document_id).where(
                CorpusDocument.corpus_id == corpus_id
            )
        )
        existing_ids = {row[0] for row in existing_result.all()}

        for doc_id in owned_ids - existing_ids:
            self.db.add(CorpusDocument(corpus_id=corpus_id, document_id=doc_id))

        await self.db.commit()
        await self.db.refresh(corpus)
        return corpus

    async def remove_documents(
        self, user: User, corpus_id: UUID, document_ids: list[UUID]
    ) -> Corpus:
        """Retire des documents d'un corpus (les documents eux-memes restent)."""
        corpus = await self._get_owned(user, corpus_id)
        if not document_ids:
            return corpus

        await self.db.execute(
            CorpusDocument.__table__.delete().where(
                CorpusDocument.corpus_id == corpus_id,
                CorpusDocument.document_id.in_(document_ids),
            )
        )
        await self.db.commit()
        await self.db.refresh(corpus)
        return corpus

    # ============================================================
    # Helper interne
    # ============================================================

    async def _get_owned(self, user: User, corpus_id: UUID) -> Corpus:
        """Recupere un corpus + ownership check. Raise 404 si absent."""
        result = await self.db.execute(
            select(Corpus).where(
                Corpus.id == corpus_id,
                Corpus.user_id == user.id,
            )
        )
        corpus = result.scalar_one_or_none()
        if corpus is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Corpus introuvable ou accès refusé"
            )
        return corpus
