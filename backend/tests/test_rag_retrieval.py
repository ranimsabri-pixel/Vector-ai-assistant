"""Tests du retrieval RAG (recherche vectorielle pgvector, S5 J23/J34/J37).

Les chunks sont inseres directement en base avec des embeddings fabriques
a la main (vecteurs 1536-dim controles) plutot que via une vraie ingestion +
appel OpenAI reel : ca permet de connaitre a l'avance l'ordre de similarite
exact attendu (proche/loin/orthogonal), sans mock ni latence reseau.
"""
import uuid as uuid_module

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.corpus import Corpus, CorpusDocument
from app.db.models.document import Chunk, Document
from app.services.retrieval import (
    MIN_CHUNK_TOKENS,
    retrieve_from_corpus,
    search_in_document,
    search_in_user_documents,
)

# Vecteurs de test : QUERY et CLOSE sont identiques (distance cosine = 0),
# FAR est l'oppose exact (distance cosine = 2), ORTHOGONAL est a mi-chemin.
QUERY_VECTOR = [1.0] + [0.0] * 1535
CLOSE_VECTOR = [1.0] + [0.0] * 1535
FAR_VECTOR = [-1.0] + [0.0] * 1535
ORTHOGONAL_VECTOR = [0.0, 1.0] + [0.0] * 1534


async def _make_document(
    db_session: AsyncSession, user_id, name: str = "Doc", status: str = "ready"
) -> Document:
    doc = Document(
        user_id=user_id,
        name=name,
        original_filename=f"{name}.pdf",
        file_path=f"fake/{uuid_module.uuid4()}.pdf",
        file_size_bytes=100,
        file_type="pdf",
        status=status,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


async def _make_chunk(
    db_session: AsyncSession,
    document_id,
    content: str,
    embedding: list[float],
    chunk_index: int = 0,
    token_count: int = 50,
) -> Chunk:
    chunk = Chunk(
        document_id=document_id,
        chunk_index=chunk_index,
        page_number=1,
        content=content,
        token_count=token_count,
        embedding=embedding,
    )
    db_session.add(chunk)
    await db_session.commit()
    await db_session.refresh(chunk)
    return chunk


@pytest.mark.asyncio
async def test_search_in_document_orders_by_similarity(
    db_session: AsyncSession, registered_user: dict
):
    """Le chunk le plus proche du vecteur de requete arrive en premier."""
    doc = await _make_document(db_session, registered_user["id"])
    await _make_chunk(db_session, doc.id, "loin du sujet", FAR_VECTOR, chunk_index=0)
    await _make_chunk(db_session, doc.id, "pile le sujet", CLOSE_VECTOR, chunk_index=1)

    results = await search_in_document(db_session, doc.id, QUERY_VECTOR, top_k=5)
    assert len(results) == 2
    assert results[0].chunk.content == "pile le sujet"
    assert results[0].distance < results[1].distance


@pytest.mark.asyncio
async def test_search_in_document_scoped_to_single_document(
    db_session: AsyncSession, registered_user: dict
):
    """search_in_document ne remonte que les chunks du document demande."""
    doc1 = await _make_document(db_session, registered_user["id"], name="Doc1")
    doc2 = await _make_document(db_session, registered_user["id"], name="Doc2")
    await _make_chunk(db_session, doc1.id, "chunk du doc 1", CLOSE_VECTOR)
    await _make_chunk(db_session, doc2.id, "chunk du doc 2", CLOSE_VECTOR)

    results = await search_in_document(db_session, doc1.id, QUERY_VECTOR, top_k=5)
    assert len(results) == 1
    assert results[0].chunk.content == "chunk du doc 1"


@pytest.mark.asyncio
async def test_search_in_user_documents_excludes_non_ready(
    db_session: AsyncSession, registered_user: dict
):
    """Un document pas encore 'ready' n'est jamais retourne (ingestion en cours)."""
    ready_doc = await _make_document(db_session, registered_user["id"], status="ready")
    pending_doc = await _make_document(db_session, registered_user["id"], status="embedding")
    await _make_chunk(db_session, ready_doc.id, "document pret", CLOSE_VECTOR)
    await _make_chunk(db_session, pending_doc.id, "document en cours", CLOSE_VECTOR)

    results = await search_in_user_documents(
        db_session, registered_user["id"], QUERY_VECTOR, top_k=5
    )
    contents = [r.chunk.content for r in results]
    assert "document pret" in contents
    assert "document en cours" not in contents


@pytest.mark.asyncio
async def test_search_in_user_documents_ownership_isolation(
    db_session: AsyncSession, registered_user: dict, register_second_user
):
    """Le retrieval d'un user ne renvoie jamais les chunks d'un autre user."""
    my_doc = await _make_document(db_session, registered_user["id"], name="Mon doc")
    await _make_chunk(db_session, my_doc.id, "mes donnees a moi", CLOSE_VECTOR)

    other = await register_second_user()
    # register_second_user ne retourne pas l'id DB, on le recupere autrement :
    # via l'email pour requeter directement le user cree.
    from sqlalchemy import select

    from app.db.models.user import User

    other_user_row = (
        await db_session.execute(select(User).where(User.email == other["email"]))
    ).scalar_one()
    other_doc = await _make_document(db_session, other_user_row.id, name="Doc de B")
    await _make_chunk(db_session, other_doc.id, "donnees privees de B", CLOSE_VECTOR)

    results = await search_in_user_documents(
        db_session, registered_user["id"], QUERY_VECTOR, top_k=10
    )
    contents = [r.chunk.content for r in results]
    assert "mes donnees a moi" in contents
    assert "donnees privees de B" not in contents


@pytest.mark.asyncio
async def test_corpus_retrieval_short_chunks_filtered(
    db_session: AsyncSession, registered_user: dict
):
    """Un chunk sous MIN_CHUNK_TOKENS n'apparait jamais, meme s'il est le
    plus proche par similarite (titre de slide isole, etc.)."""
    doc = await _make_document(db_session, registered_user["id"])
    corpus = Corpus(user_id=registered_user["id"], name="Corpus test")
    db_session.add(corpus)
    await db_session.commit()
    await db_session.refresh(corpus)
    db_session.add(CorpusDocument(corpus_id=corpus.id, document_id=doc.id))
    await db_session.commit()

    await _make_chunk(
        db_session, doc.id, "titre isole", CLOSE_VECTOR,
        chunk_index=0, token_count=MIN_CHUNK_TOKENS - 5,
    )
    await _make_chunk(
        db_session, doc.id, "paragraphe complet et pertinent", CLOSE_VECTOR,
        chunk_index=1, token_count=MIN_CHUNK_TOKENS + 20,
    )

    results = await retrieve_from_corpus(
        db_session, corpus.id, registered_user["id"], QUERY_VECTOR, top_k=5
    )
    contents = [r.chunk.content for r in results]
    assert "titre isole" not in contents
    assert "paragraphe complet et pertinent" in contents


@pytest.mark.asyncio
async def test_corpus_retrieval_diversity_guarantees_weaker_document(
    db_session: AsyncSession, registered_user: dict
):
    """Meme si un document a des scores nettement plus faibles, le plancher
    de diversite garantit qu'il apparait quand meme (pas 100% domine par
    l'autre document du corpus)."""
    strong_doc = await _make_document(db_session, registered_user["id"], name="Fort")
    weak_doc = await _make_document(db_session, registered_user["id"], name="Faible")
    corpus = Corpus(user_id=registered_user["id"], name="Corpus diversite")
    db_session.add(corpus)
    await db_session.commit()
    await db_session.refresh(corpus)
    db_session.add(CorpusDocument(corpus_id=corpus.id, document_id=strong_doc.id))
    db_session.add(CorpusDocument(corpus_id=corpus.id, document_id=weak_doc.id))
    await db_session.commit()

    # Le document "fort" a 5 chunks tres proches -> domine largement en score brut
    for i in range(5):
        await _make_chunk(
            db_session, strong_doc.id, f"chunk fort {i}", CLOSE_VECTOR, chunk_index=i
        )
    # Le document "faible" n'a qu'un chunk loin du sujet
    await _make_chunk(db_session, weak_doc.id, "chunk faible", FAR_VECTOR, chunk_index=0)

    results = await retrieve_from_corpus(
        db_session, corpus.id, registered_user["id"], QUERY_VECTOR, top_k=3
    )
    document_names = {r.document_name for r in results}
    assert "Fort" in document_names
    assert "Faible" in document_names  # garanti par le plancher de diversite


@pytest.mark.asyncio
async def test_corpus_retrieval_ownership_returns_empty(
    db_session: AsyncSession, registered_user: dict, register_second_user
):
    """Un corpus n'appartenant pas a l'user ne renvoie jamais de chunk, meme
    avec le bon corpus_id (isolation stricte par Corpus.user_id)."""
    from sqlalchemy import select

    from app.db.models.user import User

    other = await register_second_user()
    other_user_row = (
        await db_session.execute(select(User).where(User.email == other["email"]))
    ).scalar_one()

    other_doc = await _make_document(db_session, other_user_row.id)
    other_corpus = Corpus(user_id=other_user_row.id, name="Corpus de B")
    db_session.add(other_corpus)
    await db_session.commit()
    await db_session.refresh(other_corpus)
    db_session.add(CorpusDocument(corpus_id=other_corpus.id, document_id=other_doc.id))
    await db_session.commit()
    await _make_chunk(db_session, other_doc.id, "secret de B", CLOSE_VECTOR)

    results = await retrieve_from_corpus(
        db_session, other_corpus.id, registered_user["id"], QUERY_VECTOR, top_k=5
    )
    assert results == []
