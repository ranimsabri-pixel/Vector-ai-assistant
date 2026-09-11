"""Tests au niveau service de CorpusService (S5 J44 Bloc C).

Meme approche que test_services_conversations.py : pas de methode pure/
statique dans services/corpus.py (tout exige une AsyncSession reelle), donc
tests directs sur la classe de service via db_session, complementaires de
test_corpus.py (HTTP) sans le dupliquer — cible en particulier l'atomicite
de add_documents (tout ou rien) et les court-circuits sur liste vide, non
observes par les tests HTTP existants.
"""
import uuid as uuid_module

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models.document import Document
from app.db.models.user import User
from app.services.corpus import CorpusService


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


async def _make_document(db_session: AsyncSession, user_id) -> Document:
    doc = Document(
        user_id=user_id,
        name="Doc test",
        original_filename="test.pdf",
        file_path=f"fake/{uuid_module.uuid4()}.pdf",
        file_size_bytes=10,
        file_type="pdf",
        status="ready",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


@pytest.mark.asyncio
async def test_get_owned_raises_404_for_wrong_user(db_session: AsyncSession):
    owner = await _make_user(db_session)
    other_user = await _make_user(db_session)
    service = CorpusService(db_session)
    corpus = await service.create_corpus(owner, "Prive")

    with pytest.raises(HTTPException) as exc_info:
        await service._get_owned(other_user, corpus.id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_add_documents_empty_list_is_noop(db_session: AsyncSession):
    user = await _make_user(db_session)
    service = CorpusService(db_session)
    corpus = await service.create_corpus(user, "Test")

    result = await service.add_documents(user, corpus.id, [])
    detail = await service.get_corpus(user, corpus.id)
    assert detail["document_count"] == 0
    assert result.id == corpus.id


@pytest.mark.asyncio
async def test_add_documents_partial_ownership_rejects_atomically(
    db_session: AsyncSession,
):
    """Si un seul document sur plusieurs n'appartient pas a l'user, AUCUN
    n'est ajoute (pas d'ajout partiel silencieux)."""
    user = await _make_user(db_session)
    other_user = await _make_user(db_session)
    service = CorpusService(db_session)
    corpus = await service.create_corpus(user, "Test")

    my_doc = await _make_document(db_session, user.id)
    foreign_doc = await _make_document(db_session, other_user.id)

    with pytest.raises(HTTPException) as exc_info:
        await service.add_documents(user, corpus.id, [my_doc.id, foreign_doc.id])
    assert exc_info.value.status_code == 404

    detail = await service.get_corpus(user, corpus.id)
    assert detail["document_count"] == 0  # meme le document possede n'a pas ete ajoute


@pytest.mark.asyncio
async def test_add_documents_idempotent_no_duplicate(db_session: AsyncSession):
    user = await _make_user(db_session)
    service = CorpusService(db_session)
    corpus = await service.create_corpus(user, "Test")
    doc = await _make_document(db_session, user.id)

    await service.add_documents(user, corpus.id, [doc.id])
    await service.add_documents(user, corpus.id, [doc.id])  # 2e ajout, meme doc

    detail = await service.get_corpus(user, corpus.id)
    assert detail["document_count"] == 1


@pytest.mark.asyncio
async def test_remove_documents_empty_list_is_noop(db_session: AsyncSession):
    user = await _make_user(db_session)
    service = CorpusService(db_session)
    corpus = await service.create_corpus(user, "Test")
    doc = await _make_document(db_session, user.id)
    await service.add_documents(user, corpus.id, [doc.id])

    await service.remove_documents(user, corpus.id, [])

    detail = await service.get_corpus(user, corpus.id)
    assert detail["document_count"] == 1  # inchange


@pytest.mark.asyncio
async def test_update_corpus_partial_update_keeps_other_field(db_session: AsyncSession):
    user = await _make_user(db_session)
    service = CorpusService(db_session)
    corpus = await service.create_corpus(user, "Nom original", description="Desc originale")

    updated = await service.update_corpus(user, corpus.id, name="Nom modifie")
    assert updated.name == "Nom modifie"
    assert updated.description == "Desc originale"  # non touchee (name=None absent)


@pytest.mark.asyncio
async def test_list_corpora_only_returns_own(db_session: AsyncSession):
    user = await _make_user(db_session)
    other_user = await _make_user(db_session)
    service = CorpusService(db_session)
    await service.create_corpus(user, "Le mien")
    await service.create_corpus(other_user, "Pas le mien")

    corpora = await service.list_corpora(user)
    names = [c["name"] for c in corpora]
    assert "Le mien" in names
    assert "Pas le mien" not in names
