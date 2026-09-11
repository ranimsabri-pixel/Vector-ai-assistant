"""Recherche vectorielle (S5 J23) — coeur du RAG.

Logique :
1. Embed la question avec le même modèle que les chunks (text-embedding-3-small)
2. Recherche cosine top-K dans Postgres via pgvector
3. Filtre par document_id (scope=1 doc) ou par user_id (scope=tous docs)

Performance :
- Avec ~1000 chunks et l'index ivfflat, la recherche prend ~10-50ms
- L'embed de la question prend ~100-300ms (appel OpenAI)
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.openai import OpenAIProvider
from app.db.models.corpus import Corpus, CorpusDocument
from app.db.models.document import Chunk, Document

logger = logging.getLogger(__name__)

# ============================================================
# Configuration
# ============================================================

DEFAULT_TOP_K = 5
MAX_TOP_K = 20  # ceinture de sécurité pour ne pas exploser le coût LLM

# S5 J37 — diversite des sources pour le retrieval corpus (multi-docs)
CORPUS_DIVERSITY_FLOOR_PER_DOC = 2  # chunks garantis par document, hors score global
CORPUS_FILL_MULTIPLIER = 2          # marge de la requete de complement (top_k*2 candidats)
MIN_CHUNK_TOKENS = 30                # ignore les chunks trop courts (titres de slides isoles, etc.)

# ivfflat.probes : l'index chunks.embedding a ete cree avec lists=100.
# Le defaut probes=1 de pgvector ne scanne qu'1 cluster sur 100 -- combine
# a un JOIN restrictif (filtre user/corpus), ca peut faire tomber la
# recherche a 0 resultat meme quand des chunks pertinents existent
# (confirme empiriquement : search_in_user_documents et retrieve_from_corpus
# renvoyaient 0 chunk de facon repetable). sqrt(lists) = 10 est la valeur
# recommandee par pgvector pour un bon compromis recall/vitesse.
IVFFLAT_PROBES = 10


async def _set_ivfflat_probes(db: AsyncSession) -> None:
    """A appeler avant toute recherche vectorielle combinee a un JOIN.

    SET LOCAL : la valeur ne vit que pour la transaction courante, pas
    besoin de la reinitialiser apres coup.
    """
    await db.execute(text(f"SET LOCAL ivfflat.probes = {IVFFLAT_PROBES}"))


# ============================================================
# Types
# ============================================================

@dataclass
class RetrievedChunk:
    """Un chunk récupéré avec son score de similarité."""
    chunk: Chunk
    distance: float  # cosine distance (0 = identique, 2 = opposé)
    document_file_type: str = "pdf"  # "pdf" | "docx" | "pptx" | "txt" | "md"
    document_name: str | None = None  # NEW J34 : rempli pour le retrieval corpus (multi-doc)

    @property
    def similarity(self) -> float:
        """Score de similarité [0, 1] (inverse de la distance cosine)."""
        return max(0.0, 1.0 - self.distance / 2.0)


# ============================================================
# Embed de la question
# ============================================================

async def embed_query(
    question: str,
    provider: OpenAIProvider,
) -> list[float]:
    """Embed la question avec le modèle utilisé pour les chunks.

    text-embedding-3-small est symétrique : pas de préfixe spécial requis
    pour les queries (contrairement à BGE ou Instructor).
    """
    embeddings = await provider.embed([question.strip()])
    if not embeddings or len(embeddings) != 1:
        raise RuntimeError("Échec embed de la question")
    return embeddings[0]


# ============================================================
# Recherche dans UN document
# ============================================================

async def search_in_document(
    db: AsyncSession,
    document_id: UUID,
    query_vector: list[float],
    top_k: int = DEFAULT_TOP_K,
) -> list[RetrievedChunk]:
    """Recherche les top-K chunks les plus proches dans UN document.

    Utilise l'opérateur cosine de pgvector (`<=>` en SQL).
    """
    top_k = min(top_k, MAX_TOP_K)
    await _set_ivfflat_probes(db)

    distance_expr = Chunk.embedding.cosine_distance(query_vector)
    stmt = (
        select(Chunk, Document.file_type, distance_expr.label("distance"))
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.document_id == document_id)
        .where(Chunk.embedding.is_not(None))
        .order_by(distance_expr)
        .limit(top_k)
    )

    result = await db.execute(stmt)
    rows = result.all()

    logger.info(
        "Retrieval doc=%s top_k=%d → %d chunks (distances: %s)",
        document_id, top_k, len(rows),
        [f"{r[2]:.3f}" for r in rows[:3]],
    )

    return [
        RetrievedChunk(chunk=row[0], document_file_type=row[1], distance=row[2])
        for row in rows
    ]


# ============================================================
# Recherche dans TOUS les documents d'un user
# ============================================================

async def search_in_user_documents(
    db: AsyncSession,
    user_id: UUID,
    query_vector: list[float],
    top_k: int = DEFAULT_TOP_K,
) -> list[RetrievedChunk]:
    """Recherche les top-K chunks dans TOUS les documents d'un user.

    Join chunks → documents pour filtrer par user_id (ownership check).
    Seuls les documents en status='ready' sont considérés.
    """
    top_k = min(top_k, MAX_TOP_K)
    await _set_ivfflat_probes(db)

    distance_expr = Chunk.embedding.cosine_distance(query_vector)
    stmt = (
        select(Chunk, Document.file_type, distance_expr.label("distance"))
        .join(Document, Chunk.document_id == Document.id)
        .where(Document.user_id == user_id)
        .where(Document.status == "ready")
        .where(Chunk.embedding.is_not(None))
        .order_by(distance_expr)
        .limit(top_k)
    )

    result = await db.execute(stmt)
    rows = result.all()

    logger.info(
        "Retrieval user=%s top_k=%d → %d chunks (distances: %s)",
        user_id, top_k, len(rows),
        [f"{r[2]:.3f}" for r in rows[:3]],
    )

    return [
        RetrievedChunk(chunk=row[0], document_file_type=row[1], distance=row[2])
        for row in rows
    ]


# ============================================================
# Recherche dans un ENSEMBLE explicite de documents (S5 J49 — personas)
# ============================================================

async def search_in_document_set(
    db: AsyncSession,
    document_ids: list[UUID],
    query_vector: list[float],
    top_k: int = DEFAULT_TOP_K,
) -> list[RetrievedChunk]:
    """Recherche les top-K chunks parmi un ensemble explicite de documents.

    Utilise par le RAG des personas : l'appelant a deja resolu et
    verifie l'ownership de l'ensemble (documents directs + documents des
    corpus associes) avant d'appeler cette fonction.
    """
    if not document_ids:
        return []
    top_k = min(top_k, MAX_TOP_K)
    await _set_ivfflat_probes(db)

    distance_expr = Chunk.embedding.cosine_distance(query_vector)
    stmt = (
        select(Chunk, Document.file_type, Document.name, distance_expr.label("distance"))
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.document_id.in_(document_ids))
        .where(Document.status == "ready")
        .where(Chunk.embedding.is_not(None))
        .order_by(distance_expr)
        .limit(top_k)
    )
    result = await db.execute(stmt)
    rows = result.all()

    logger.info(
        "Retrieval document_set=%d docs top_k=%d → %d chunks",
        len(document_ids), top_k, len(rows),
    )

    return [_row_to_chunk(row) for row in rows]


# ============================================================
# Diversite des sources (S5 J37)
# ============================================================

async def _get_corpus_ready_document_ids(
    db: AsyncSession, corpus_id: UUID, user_id: UUID
) -> list[UUID]:
    """Liste les documents 'ready' d'un corpus, avec ownership check.

    Meme garantie de securite que retrieve_from_corpus : le filtre
    Corpus.user_id fait partie de la requete elle-meme.
    """
    result = await db.execute(
        select(Document.id)
        .join(CorpusDocument, CorpusDocument.document_id == Document.id)
        .join(Corpus, Corpus.id == CorpusDocument.corpus_id)
        .where(Corpus.id == corpus_id)
        .where(Corpus.user_id == user_id)
        .where(Document.status == "ready")
    )
    return [row[0] for row in result.all()]


def _row_to_chunk(row) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=row[0],
        document_file_type=row[1],
        document_name=row[2],
        distance=row[3],
    )


# ============================================================
# Recherche dans TOUS les documents d'un CORPUS (S5 J34)
# ============================================================

async def retrieve_from_corpus(
    db: AsyncSession,
    corpus_id: UUID,
    user_id: UUID,
    query_vector: list[float],
    top_k: int = DEFAULT_TOP_K,
) -> list[RetrievedChunk]:
    """Recherche les top-K chunks les plus proches dans TOUS les documents d'un corpus.

    Sécurité : chaque requete filtre par Corpus.user_id == user_id. Impossible
    de retourner des chunks d'un corpus n'appartenant pas a l'user.

    Diversite (S5 J37) — plancher garanti par document :
    1. Pour CHAQUE document du corpus, recupere ses CORPUS_DIVERSITY_FLOOR_PER_DOC
       meilleurs chunks INDEPENDAMMENT du score global. Garantit que tout
       document ayant du contenu pertinent apparait, meme si ses scores sont
       nettement plus faibles que ceux des autres documents (constate en
       pratique : un document peut n'apparaitre qu'au rang ~25 en similarite
       globale, bien au-dela d'une simple fenetre top_k*N).
    2. Complete les slots restants jusqu'a top_k avec les meilleurs candidats
       globaux restants (tous documents confondus, pas de plafond ici).
    3. Si le plancher a lui seul depasse top_k (corpus avec beaucoup de
       documents), on garde les meilleurs parmi les chunks-plancher.

    Les chunks < MIN_CHUNK_TOKENS (titres de slides isoles, etc.) sont
    ignores partout pour ne pas polluer le classement.
    """
    top_k = min(top_k, MAX_TOP_K)
    await _set_ivfflat_probes(db)

    doc_ids = await _get_corpus_ready_document_ids(db, corpus_id, user_id)
    if not doc_ids:
        return []

    distance_expr = Chunk.embedding.cosine_distance(query_vector)

    # ===== Etape 1 — plancher garanti par document =====
    guaranteed: dict[UUID, RetrievedChunk] = {}
    for doc_id in doc_ids:
        stmt = (
            select(Chunk, Document.file_type, Document.name, distance_expr.label("distance"))
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.document_id == doc_id)
            .where(Chunk.embedding.is_not(None))
            .where(Chunk.token_count >= MIN_CHUNK_TOKENS)
            .order_by(distance_expr)
            .limit(CORPUS_DIVERSITY_FLOOR_PER_DOC)
        )
        rows = (await db.execute(stmt)).all()
        for row in rows:
            guaranteed[row[0].id] = _row_to_chunk(row)

    guaranteed_list = sorted(guaranteed.values(), key=lambda c: c.distance)

    # Corpus avec beaucoup de documents : le plancher seul peut deja depasser
    # top_k. On garde alors les meilleurs parmi le plancher, pas de complement.
    if len(guaranteed_list) >= top_k:
        selected = guaranteed_list[:top_k]
    else:
        # ===== Etape 2 — complement par les meilleurs candidats globaux =====
        remaining_slots = top_k - len(guaranteed_list)
        stmt = (
            select(Chunk, Document.file_type, Document.name, distance_expr.label("distance"))
            .join(Document, Chunk.document_id == Document.id)
            .join(CorpusDocument, CorpusDocument.document_id == Document.id)
            .where(CorpusDocument.corpus_id == corpus_id)
            .where(Document.status == "ready")
            .where(Chunk.embedding.is_not(None))
            .where(Chunk.token_count >= MIN_CHUNK_TOKENS)
            .order_by(distance_expr)
            .limit(top_k * CORPUS_FILL_MULTIPLIER + len(guaranteed_list))
        )
        rows = (await db.execute(stmt)).all()

        extra: list[RetrievedChunk] = []
        for row in rows:
            if row[0].id in guaranteed:
                continue  # deja retenu par le plancher garanti
            extra.append(_row_to_chunk(row))
            if len(extra) >= remaining_slots:
                break

        selected = sorted(guaranteed_list + extra, key=lambda c: c.distance)[:top_k]

    counts_by_doc = Counter(c.document_name for c in selected)
    logger.info(
        "Retrieval corpus=%s top_k=%d → %d docs, plancher=%d, %d retenus au final (distances: %s)",
        corpus_id, top_k, len(doc_ids), len(guaranteed_list), len(selected),
        [f"{c.distance:.3f}" for c in selected[:3]],
    )
    logger.info("[RAG_CORPUS] Sources retenues: %s", dict(counts_by_doc))

    return selected
