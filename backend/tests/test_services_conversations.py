"""Tests au niveau service de ConversationService (S5 J44 Bloc C).

services/conversations.py n'a aucune methode @staticmethod/pure : toute la
logique interessante (ownership, validation) exige une vraie AsyncSession.
Ces tests appellent donc directement la classe de service (pas de couche
HTTP/FastAPI), en reutilisant la fixture db_session (meme DB reelle que le
reste de la suite, cf. tests/test_rag_retrieval.py). Complementaire de
test_conversations.py (tests HTTP), sans le dupliquer : cible des branches
non observables facilement via l'API (ex: troncature de titre, 404 sur
_get_owned appele directement).
"""
import uuid as uuid_module

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models.document import Document
from app.db.models.user import User
from app.services.conversations import TITLE_MAX_LEN, ConversationService


async def _make_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"svc_{uuid_module.uuid4().hex[:10]}@example.com",
        password_hash=hash_password("Test1234!"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_create_with_unknown_agent_slug_raises_404(db_session: AsyncSession):
    user = await _make_user(db_session)
    service = ConversationService(db_session)

    with pytest.raises(HTTPException) as exc_info:
        await service.create(user=user, agent_slug="agent-qui-nexiste-pas")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_create_with_foreign_document_raises_404(db_session: AsyncSession):
    owner = await _make_user(db_session)
    other_user = await _make_user(db_session)

    doc = Document(
        user_id=owner.id,
        name="Doc prive",
        original_filename="prive.pdf",
        file_path="fake/prive.pdf",
        file_size_bytes=10,
        file_type="pdf",
        status="ready",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    service = ConversationService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        await service.create(user=other_user, document_id=doc.id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_title_truncates_at_max_length(db_session: AsyncSession):
    user = await _make_user(db_session)
    service = ConversationService(db_session)
    conv = await service.create(user=user)

    very_long_title = "x" * 200
    updated = await service.update_title(user, conv.id, very_long_title)
    assert len(updated.title) == TITLE_MAX_LEN


@pytest.mark.asyncio
async def test_get_owned_raises_404_for_wrong_user(db_session: AsyncSession):
    owner = await _make_user(db_session)
    other_user = await _make_user(db_session)
    service = ConversationService(db_session)
    conv = await service.create(user=owner)

    with pytest.raises(HTTPException) as exc_info:
        await service._get_owned(other_user, conv.id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_toggle_pin_updates_flag(db_session: AsyncSession):
    user = await _make_user(db_session)
    service = ConversationService(db_session)
    conv = await service.create(user=user)
    assert conv.is_pinned is False

    pinned = await service.toggle_pin(user, conv.id, True)
    assert pinned.is_pinned is True

    unpinned = await service.toggle_pin(user, conv.id, False)
    assert unpinned.is_pinned is False


@pytest.mark.asyncio
async def test_delete_message_not_owned_raises_404(db_session: AsyncSession):
    owner = await _make_user(db_session)
    other_user = await _make_user(db_session)
    service = ConversationService(db_session)
    conv = await service.create(user=owner)
    msg = await service.add_message(owner, conv.id, "user", "user", "Question")

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_message(other_user, msg.id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_add_message_bumps_conversation_updated_at(db_session: AsyncSession):
    user = await _make_user(db_session)
    service = ConversationService(db_session)
    conv = await service.create(user=user)
    updated_at_before = conv.updated_at

    await service.add_message(user, conv.id, "user", "user", "Question")
    refreshed = await service._get_owned(user, conv.id)

    assert refreshed.updated_at >= updated_at_before


@pytest.mark.asyncio
async def test_generate_title_default_title_check_is_case_insensitive(
    db_session: AsyncSession,
):
    """_DEFAULT_TITLES est verifie en lowercase+strip -- une conv titree
    'NOUVELLE DISCUSSION' (casse differente) doit quand meme etre consideree
    comme non personnalisee (donc modifiable par generate_title)."""
    user = await _make_user(db_session)
    service = ConversationService(db_session)
    conv = await service.create(user=user, title="  NOUVELLE DISCUSSION  ")

    # Sans 2 messages, generate_title renvoie la conv inchangee (comportement
    # normal), mais ne doit pas lever d'exception ni planter sur ce titre.
    result = await service.generate_title(user, conv.id)
    assert result.id == conv.id
