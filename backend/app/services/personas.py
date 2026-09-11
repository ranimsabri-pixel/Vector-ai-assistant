"""PersonaService (S5 J49) — CRUD + association documents/corpus.

Pattern identique a CorpusService : constructeur (db), methodes async avec
ownership check systematique via user en 1er arg, toujours 404 (jamais 403)
sur acces refuse — convention du projet.

Protection du persona systeme : _get_owned() filtre sur user_id == user.id.
Comme le persona systeme a toujours user_id=NULL, cette requete ne peut
JAMAIS le retourner — modification/suppression impossibles par construction,
meme via appel direct au service (pas seulement via l'API), pas de check
is_system separe a oublier.
"""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.providers.openai import OpenAIProvider
from app.db.models.corpus import Corpus, CorpusDocument
from app.db.models.document import Document
from app.db.models.persona import Persona, PersonaCorpus, PersonaDocument
from app.db.models.user import User
from app.services import retrieval

# NEW J49 — nombre de chunks remontes pour enrichir le system prompt d'un
# persona ayant des documents/corpus associes (meme ordre de grandeur que
# DEFAULT_TOP_K des autres flux RAG).
PERSONA_RAG_TOP_K = 5


class PersonaService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # Create
    # ============================================================

    async def create_persona(
        self,
        user: User,
        name: str,
        system_prompt: str,
        icon: str,
        color: str,
        description: str | None = None,
    ) -> Persona:
        """Cree un persona utilisateur (jamais is_system=True via l'API)."""
        persona = Persona(
            user_id=user.id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            icon=icon,
            color=color,
            is_system=False,
        )
        self.db.add(persona)
        await self.db.commit()
        await self.db.refresh(persona)
        return persona

    # ============================================================
    # Read
    # ============================================================

    async def list_personas(self, user: User) -> list[Persona]:
        """Personas de l'utilisateur + le persona systeme Vector, actifs uniquement."""
        result = await self.db.execute(
            select(Persona)
            .where(
                Persona.is_active.is_(True),
                or_(Persona.user_id == user.id, Persona.is_system.is_(True)),
            )
            .order_by(Persona.is_system.desc(), Persona.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_persona(self, user: User, persona_id: UUID) -> Persona:
        """Recupere un persona visible (le sien, ou le persona systeme) avec ses sources."""
        result = await self.db.execute(
            select(Persona)
            .options(selectinload(Persona.documents), selectinload(Persona.corpora))
            .where(
                Persona.id == persona_id,
                or_(Persona.user_id == user.id, Persona.is_system.is_(True)),
            )
        )
        persona = result.scalar_one_or_none()
        if persona is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Persona introuvable ou accès refusé"
            )
        return persona

    # ============================================================
    # Update
    # ============================================================

    async def update_persona(
        self,
        user: User,
        persona_id: UUID,
        name: str | None = None,
        description: str | None = None,
        system_prompt: str | None = None,
        icon: str | None = None,
        color: str | None = None,
    ) -> Persona:
        """Modifie un persona (jamais le persona systeme, cf. _get_owned)."""
        persona = await self._get_owned(user, persona_id)
        if name is not None:
            persona.name = name
        if description is not None:
            persona.description = description
        if system_prompt is not None:
            persona.system_prompt = system_prompt
        if icon is not None:
            persona.icon = icon
        if color is not None:
            persona.color = color
        await self.db.commit()
        await self.db.refresh(persona)
        return persona

    # ============================================================
    # Delete
    # ============================================================

    async def delete_persona(self, user: User, persona_id: UUID) -> None:
        """Supprime un persona (jamais le persona systeme, cf. _get_owned).

        Les conversations liees gardent leur historique (persona_id -> NULL,
        ondelete SET NULL sur Conversation.persona_id)."""
        persona = await self._get_owned(user, persona_id)
        await self.db.delete(persona)
        await self.db.commit()

    # ============================================================
    # Documents — add / remove
    # ============================================================

    async def add_documents(
        self, user: User, persona_id: UUID, document_ids: list[UUID]
    ) -> Persona:
        """Associe des documents (obligatoirement possedes par l'user) a un persona."""
        persona = await self._get_owned(user, persona_id)
        if not document_ids:
            return persona

        requested_ids = set(document_ids)
        result = await self.db.execute(
            select(Document.id).where(
                Document.id.in_(requested_ids), Document.user_id == user.id
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
            select(PersonaDocument.document_id).where(
                PersonaDocument.persona_id == persona_id
            )
        )
        existing_ids = {row[0] for row in existing_result.all()}

        for doc_id in owned_ids - existing_ids:
            self.db.add(PersonaDocument(persona_id=persona_id, document_id=doc_id))

        await self.db.commit()
        await self.db.refresh(persona)
        return persona

    async def remove_document(
        self, user: User, persona_id: UUID, document_id: UUID
    ) -> Persona:
        """Retire un document d'un persona (le document lui-meme reste)."""
        persona = await self._get_owned(user, persona_id)
        await self.db.execute(
            PersonaDocument.__table__.delete().where(
                PersonaDocument.persona_id == persona_id,
                PersonaDocument.document_id == document_id,
            )
        )
        await self.db.commit()
        await self.db.refresh(persona)
        return persona

    # ============================================================
    # Corpus — add / remove
    # ============================================================

    async def add_corpora(
        self, user: User, persona_id: UUID, corpus_ids: list[UUID]
    ) -> Persona:
        """Associe des corpus (obligatoirement possedes par l'user) a un persona."""
        persona = await self._get_owned(user, persona_id)
        if not corpus_ids:
            return persona

        requested_ids = set(corpus_ids)
        result = await self.db.execute(
            select(Corpus.id).where(
                Corpus.id.in_(requested_ids), Corpus.user_id == user.id
            )
        )
        owned_ids = {row[0] for row in result.all()}
        missing = requested_ids - owned_ids
        if missing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Corpus introuvable(s) ou accès refusé : "
                + ", ".join(str(m) for m in missing),
            )

        existing_result = await self.db.execute(
            select(PersonaCorpus.corpus_id).where(
                PersonaCorpus.persona_id == persona_id
            )
        )
        existing_ids = {row[0] for row in existing_result.all()}

        for corpus_id in owned_ids - existing_ids:
            self.db.add(PersonaCorpus(persona_id=persona_id, corpus_id=corpus_id))

        await self.db.commit()
        await self.db.refresh(persona)
        return persona

    async def remove_corpus(
        self, user: User, persona_id: UUID, corpus_id: UUID
    ) -> Persona:
        """Retire un corpus d'un persona (le corpus lui-meme reste)."""
        persona = await self._get_owned(user, persona_id)
        await self.db.execute(
            PersonaCorpus.__table__.delete().where(
                PersonaCorpus.persona_id == persona_id,
                PersonaCorpus.corpus_id == corpus_id,
            )
        )
        await self.db.commit()
        await self.db.refresh(persona)
        return persona

    # ============================================================
    # RAG — contexte documentaire du persona (S5 J49)
    # ============================================================

    async def build_rag_context(
        self, persona: Persona, query: str, provider: OpenAIProvider
    ) -> str | None:
        """Contexte RAG a injecter dans le system prompt du chat quand ce
        persona a des documents/corpus associes.

        None si le persona n'a aucune source associee, ou si aucun chunk
        pertinent n'est trouve (jamais d'erreur bloquante pour le chat).
        persona.documents/persona.corpora doivent deja etre charges
        (selectinload, voir get_persona()).
        """
        document_ids = {d.id for d in persona.documents if d.status == "ready"}

        if persona.corpora:
            corpus_ids = [c.id for c in persona.corpora]
            result = await self.db.execute(
                select(CorpusDocument.document_id)
                .join(Document, Document.id == CorpusDocument.document_id)
                .where(
                    CorpusDocument.corpus_id.in_(corpus_ids),
                    Document.status == "ready",
                )
            )
            document_ids.update(row[0] for row in result.all())

        if not document_ids:
            return None

        query_vector = await retrieval.embed_query(query, provider)
        chunks = await retrieval.search_in_document_set(
            self.db, list(document_ids), query_vector, top_k=PERSONA_RAG_TOP_K
        )
        if not chunks:
            return None

        extracts = []
        for i, rc in enumerate(chunks, start=1):
            page = rc.chunk.page_number or "?"
            label = f"[Source {i} - {rc.document_name}, page {page}]"
            extracts.append(f"{label}\n{rc.chunk.content.strip()}")

        return (
            "CONTEXTE DOCUMENTAIRE (sources associées à ce persona) :\n\n"
            + "\n\n".join(extracts)
            + "\n\nCite le nom du document quand tu t'appuies sur un de ces extraits."
        )

    # ============================================================
    # Helper interne
    # ============================================================

    async def _get_owned(self, user: User, persona_id: UUID) -> Persona:
        """Recupere un persona STRICTEMENT possede par l'user (jamais le
        systeme, jamais celui d'un autre). Raise 404 sinon."""
        result = await self.db.execute(
            select(Persona).where(
                Persona.id == persona_id,
                Persona.user_id == user.id,
            )
        )
        persona = result.scalar_one_or_none()
        if persona is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Persona introuvable ou accès refusé"
            )
        return persona
