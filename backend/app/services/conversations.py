"""Service Conversation — CRUD + business logic (S5 J25.B).

Pattern imité de DocumentService : constructeur (db), méthodes async avec
ownership check systématique via user en 1er arg.
"""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.providers.base import Message as AIMessage
from app.ai.providers.openai import OpenAIProvider
from app.db.models.agent import Agent
from app.db.models.conversation import Conversation, Message
from app.db.models.corpus import Corpus
from app.db.models.document import Document
from app.db.models.persona import Persona
from app.db.models.user import User

# Titres consideres comme "pas encore personnalises" -> ecrasables par l'auto-titrage
_DEFAULT_TITLES = {"nouvelle discussion", "new chat", ""}


# Limite pour le titre auto généré depuis la 1ère question
TITLE_MAX_LEN = 60


class ConversationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # Create
    # ============================================================

    async def create(
        self,
        user: User,
        title: str | None = None,
        document_id: UUID | None = None,
        corpus_id: UUID | None = None,
        persona_id: UUID | None = None,
        agent_slug: str = "vector",
    ) -> Conversation:
        """Crée une nouvelle conversation.

        - Si document_id est fourni, on valide l'ownership du PDF
        - Si corpus_id est fourni, on valide l'ownership du corpus (NEW J34)
        - Si persona_id est fourni, on valide qu'il est visible par l'user
          (le sien, ou le persona système Vector) — NEW J49
        - Le titre est auto généré si None : nom du PDF/corpus ou "Nouvelle discussion"
        - agent_slug par défaut = "vector" (récupère l'ID en BDD)
        """
        # 1. Résoudre l'agent depuis son slug
        agent_result = await self.db.execute(
            select(Agent).where(Agent.slug == agent_slug)
        )
        agent = agent_result.scalar_one_or_none()
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_slug}' introuvable en BDD",
            )

        # 2. Résoudre le document si fourni (avec ownership check)
        document = None
        if document_id is not None:
            doc_result = await self.db.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.user_id == user.id,
                )
            )
            document = doc_result.scalar_one_or_none()
            if document is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document introuvable ou accès refusé",
                )

        # 2bis. Résoudre le corpus si fourni (avec ownership check) — NEW J34
        corpus = None
        if corpus_id is not None:
            corpus_result = await self.db.execute(
                select(Corpus).where(
                    Corpus.id == corpus_id,
                    Corpus.user_id == user.id,
                )
            )
            corpus = corpus_result.scalar_one_or_none()
            if corpus is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Corpus introuvable ou accès refusé",
                )

        # 2ter. Résoudre le persona si fourni (le sien, ou le système) — NEW J49
        if persona_id is not None:
            persona_result = await self.db.execute(
                select(Persona.id).where(
                    Persona.id == persona_id,
                    or_(Persona.user_id == user.id, Persona.is_system.is_(True)),
                )
            )
            if persona_result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Persona introuvable ou accès refusé",
                )

        # 3. Titre auto si non fourni
        if not title:
            if document is not None:
                # Retire l'extension .pdf pour un titre plus propre
                title = document.name.rsplit(".", 1)[0][:TITLE_MAX_LEN]
            elif corpus is not None:
                title = corpus.name[:TITLE_MAX_LEN]
            else:
                title = "Nouvelle discussion"

        # 4. Créer la conversation
        conv = Conversation(
            user_id=user.id,
            agent_id=agent.id,
            document_id=document_id,
            corpus_id=corpus_id,
            persona_id=persona_id,
            title=title,
        )
        self.db.add(conv)
        await self.db.commit()
        await self.db.refresh(conv)
        return conv

    # ============================================================
    # Read
    # ============================================================

    async def list_user_conversations(
        self, user: User, limit: int = 50
    ) -> list[dict]:
        """Liste des conversations de l'utilisateur avec métadonnées enrichies.

        Retourne un dict enrichi (pas juste Conversation) pour inclure
        document_name et message_count sans faire N+1 en SQL séparé.
        """
        # Sous-requête : nombre de messages par conversation
        msg_count_subq = (
            select(
                Message.conversation_id,
                func.count(Message.id).label("msg_count"),
            )
            .group_by(Message.conversation_id)
            .subquery()
        )

        # Query principale avec LEFT JOIN Document + Corpus + Persona + count messages
        query = (
            select(
                Conversation,
                Document.name.label("document_name"),
                Corpus.name.label("corpus_name"),
                Persona.name.label("persona_name"),
                Persona.icon.label("persona_icon"),
                Persona.color.label("persona_color"),
                func.coalesce(msg_count_subq.c.msg_count, 0).label("message_count"),
            )
            .outerjoin(Document, Conversation.document_id == Document.id)
            .outerjoin(Corpus, Conversation.corpus_id == Corpus.id)
            .outerjoin(Persona, Conversation.persona_id == Persona.id)
            .outerjoin(msg_count_subq, msg_count_subq.c.conversation_id == Conversation.id)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )

        result = await self.db.execute(query)
        rows = result.all()

        # Enrichir chaque conv avec document_name/corpus_name/persona_* + message_count
        enriched = []
        for row in rows:
            conv = row[0]
            enriched.append({
                "id": conv.id,
                "title": conv.title,
                "is_pinned": conv.is_pinned,  # NEW J27
                "document_id": conv.document_id,
                "document_name": row[1],  # peut être None
                "corpus_id": conv.corpus_id,  # NEW J34
                "corpus_name": row[2],  # NEW J34, peut être None
                "persona_id": conv.persona_id,  # NEW J49
                "persona_name": row[3],  # NEW J49, peut être None
                "persona_icon": row[4],
                "persona_color": row[5],
                "message_count": row[6],
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
            })

        return enriched

    async def get_conversation(
        self, user: User, conversation_id: UUID
    ) -> dict:
        """Récupère une conversation complète avec ses messages."""
        query = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .outerjoin(Document, Conversation.document_id == Document.id)
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id,
            )
        )
        result = await self.db.execute(query)
        conv = result.scalar_one_or_none()

        if conv is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation introuvable ou accès refusé",
            )

        # Charger le nom du document si présent (sans re-query grâce à la relation)
        document_name = None
        if conv.document_id is not None:
            doc_result = await self.db.execute(
                select(Document.name).where(Document.id == conv.document_id)
            )
            document_name = doc_result.scalar_one_or_none()

        # Charger le nom du corpus si présent (NEW J34)
        corpus_name = None
        if conv.corpus_id is not None:
            corpus_result = await self.db.execute(
                select(Corpus.name).where(Corpus.id == conv.corpus_id)
            )
            corpus_name = corpus_result.scalar_one_or_none()

        # Charger les infos du persona si présent (NEW J49)
        persona_name = persona_icon = persona_color = None
        if conv.persona_id is not None:
            persona_result = await self.db.execute(
                select(Persona.name, Persona.icon, Persona.color).where(
                    Persona.id == conv.persona_id
                )
            )
            persona_row = persona_result.first()
            if persona_row is not None:
                persona_name, persona_icon, persona_color = persona_row

        return {
            "id": conv.id,
            "title": conv.title,
            "is_pinned": conv.is_pinned,  # NEW J27
            "document_id": conv.document_id,
            "document_name": document_name,
            "corpus_id": conv.corpus_id,  # NEW J34
            "corpus_name": corpus_name,  # NEW J34
            "persona_id": conv.persona_id,  # NEW J49
            "persona_name": persona_name,
            "persona_icon": persona_icon,
            "persona_color": persona_color,
            "agent_id": conv.agent_id,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
            "messages": conv.messages,  # déjà chargés via selectinload
        }

    # ============================================================
    # Update
    # ============================================================

    async def update_title(
        self, user: User, conversation_id: UUID, new_title: str
    ) -> Conversation:
        """Renomme une conversation."""
        conv = await self._get_owned(user, conversation_id)
        conv.title = new_title[:TITLE_MAX_LEN]
        await self.db.commit()
        await self.db.refresh(conv)
        return conv
    async def generate_title(
        self, user: User, conversation_id: UUID
    ) -> Conversation:
        """Genere un titre court via LLM leger, une seule fois par conversation
        (S5 J41+ — feature 1). N'ecrase jamais un titre deja personnalise par
        l'utilisateur, et echoue silencieusement (best-effort, nice-to-have)."""
        conv = await self._get_owned(user, conversation_id)

        if conv.title and conv.title.strip().lower() not in _DEFAULT_TITLES:
            return conv

        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.asc())
            .limit(2)
        )
        messages = list(result.scalars().all())
        if len(messages) < 2:
            return conv

        prompt = (
            "Genere un titre court (5-8 mots max) pour cette conversation en "
            "francais. Le titre doit resumer le sujet principal sans "
            "ponctuation finale, sans guillemets, sans preambule.\n\n"
            f"Question : {messages[0].content[:500]}\n"
            f"Reponse : {messages[1].content[:500]}\n\n"
            "Titre :"
        )

        try:
            provider = OpenAIProvider()
            raw_title = await provider.chat(
                [AIMessage(role="user", content=prompt)],
                model="gpt-4o-mini",
                temperature=0.3,
                max_tokens=30,
            )
        except Exception:
            return conv

        new_title = raw_title.strip().strip('".').replace("Titre :", "").strip()
        new_title = new_title[:TITLE_MAX_LEN]

        if new_title:
            conv.title = new_title
            await self.db.commit()
            await self.db.refresh(conv)

        return conv

    async def toggle_pin(
        self, user: User, conversation_id: UUID, is_pinned: bool
    ) -> Conversation:
        """Épingle ou désépingle une conversation."""
        conv = await self._get_owned(user, conversation_id)
        conv.is_pinned = is_pinned
        await self.db.commit()
        await self.db.refresh(conv)
        return conv

    async def set_persona(
        self, user: User, conversation_id: UUID, persona_id: UUID | None
    ) -> Conversation:
        """Change le persona actif d'une conversation (NEW J49).

        Uniquement possible tant que la conversation n'a AUCUN message —
        le persona est verrouillé dès le premier échange (choix structurant
        du system prompt / contexte RAG, pas modifiable en cours de route).
        persona_id=None remet le persona système Vector par défaut.
        """
        conv = await self._get_owned(user, conversation_id)

        count_result = await self.db.execute(
            select(func.count(Message.id)).where(
                Message.conversation_id == conversation_id
            )
        )
        if count_result.scalar_one() > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Le persona ne peut plus être changé : la conversation a déjà des messages",
            )

        if persona_id is not None:
            persona_result = await self.db.execute(
                select(Persona.id).where(
                    Persona.id == persona_id,
                    or_(Persona.user_id == user.id, Persona.is_system.is_(True)),
                )
            )
            if persona_result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Persona introuvable ou accès refusé",
                )

        conv.persona_id = persona_id
        await self.db.commit()
        await self.db.refresh(conv)
        return conv

    # ============================================================
    # Delete
    # ============================================================

    async def delete_conversation(
        self, user: User, conversation_id: UUID
    ) -> None:
        """Supprime une conversation (et ses messages par cascade)."""
        conv = await self._get_owned(user, conversation_id)
        await self.db.delete(conv)
        await self.db.commit()

    # ============================================================
    # Messages — append
    # ============================================================

    async def add_message(
        self,
        user: User,
        conversation_id: UUID,
        role: str,
        message_kind: str,
        content: str,
        tool_calls: list | None = None,
        sources: list | None = None,
        extra_data: dict | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        cost_usd: float | None = None,
        model_used: str | None = None,
        attachments: list | None = None,
    ) -> Message:
        """Ajoute un message à une conversation.

        Met à jour updated_at de la conversation pour que la sidebar
        remonte les conv actives en premier.

        prompt_tokens/completion_tokens/total_tokens/cost_usd/model_used
        (NEW J41+ Feature 2) : fournis par le frontend pour les messages
        assistant issus d'un appel LLM reel, None sinon.
        """
        conv = await self._get_owned(user, conversation_id)

        msg = Message(
            conversation_id=conv.id,
            role=role,
            message_kind=message_kind,
            content=content,
            tool_calls=tool_calls,
            sources=sources,
            extra_data=extra_data,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            model_used=model_used,
            attachments=attachments,
        )
        self.db.add(msg)

        # Bump updated_at de la conversation
        # (via un flag pour forcer SQLAlchemy à considérer la conv "dirty")
        from sqlalchemy.sql import func as sql_func
        conv.updated_at = sql_func.now()

        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    # ============================================================
    # Messages — feedback
    # ============================================================

    async def update_message_feedback(
        self,
        user: User,
        message_id: UUID,
        feedback: str | None,
    ) -> Message:
        """Met à jour le feedback (positive/negative/None) d'un message.

        Ownership check via la conversation parente : le message doit
        appartenir à une conversation dont l'user est propriétaire.
        """
        result = await self.db.execute(
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Message.id == message_id,
                Conversation.user_id == user.id,
            )
        )
        msg = result.scalar_one_or_none()
        if msg is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message introuvable ou accès refusé",
            )

        msg.feedback = feedback
        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    async def delete_message(self, user: User, message_id: UUID) -> None:
        """Supprime un message (utilisé par la régénération de réponse).

        Ownership check via la conversation parente, comme update_message_feedback.
        """
        result = await self.db.execute(
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Message.id == message_id,
                Conversation.user_id == user.id,
            )
        )
        msg = result.scalar_one_or_none()
        if msg is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message introuvable ou accès refusé",
            )

        await self.db.delete(msg)
        await self.db.commit()

    # ============================================================
    # Stats tokens/cout (NEW J41+ Feature 2)
    # ============================================================

    async def get_stats(self, user: User, conversation_id: UUID) -> dict:
        """Stats agregees tokens/cout d'une conversation.

        Ne compte que les messages qui ont reellement un total_tokens
        (assistant issus d'un appel LLM) — les messages user/tool/status
        sont NULL et donc ignores par les agregats SQL (sum/avg NULL-safe).
        """
        conv = await self._get_owned(user, conversation_id)

        count_result = await self.db.execute(
            select(func.count(Message.id)).where(
                Message.conversation_id == conv.id
            )
        )
        total_messages = count_result.scalar_one()

        agg_result = await self.db.execute(
            select(
                func.coalesce(func.sum(Message.prompt_tokens), 0),
                func.coalesce(func.sum(Message.completion_tokens), 0),
                func.coalesce(func.sum(Message.total_tokens), 0),
                func.coalesce(func.sum(Message.cost_usd), 0.0),
                func.coalesce(func.avg(Message.total_tokens), 0.0),
            ).where(Message.conversation_id == conv.id)
        )
        prompt_sum, completion_sum, total_sum, cost_sum, avg_tokens = agg_result.one()

        return {
            "total_messages": total_messages,
            "total_prompt_tokens": int(prompt_sum),
            "total_completion_tokens": int(completion_sum),
            "total_tokens": int(total_sum),
            "total_cost_usd": round(float(cost_sum), 6),
            "avg_response_tokens": round(float(avg_tokens), 1),
        }

    # ============================================================
    # Helper interne
    # ============================================================

    async def _get_owned(
        self, user: User, conversation_id: UUID
    ) -> Conversation:
        """Récupère une conv + ownership check. Raise 404 si absent."""
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id,
            )
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation introuvable ou accès refusé",
            )
        return conv
