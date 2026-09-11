"""Pipeline d'ingestion RAG : extract → chunk → embed (S5 J22, DOCX en J32, PPTX en J35, PDF/pymupdf en J36, TXT/MD en J51).

Architecture :
- extract_document_content : dispatcher PDF/DOCX/PPTX/TXT/MD -> format unifie
                              {section_number, section_title, content}
- chunk_sections         : decoupe via RecursiveCharacterTextSplitter
- count_tokens           : comptage via tiktoken (cl100k_base)
- embed_chunks           : embed par batch via OpenAIProvider (avec retry built-in)
- ingest_document        : orchestre tout + met a jour Document.status

Cette fonction est appelée en BackgroundTask depuis l'endpoint upload.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.openai import OpenAIProvider
from app.db.models.document import Chunk, Document
from app.services.extractors.docx_extractor import extract_docx_text
from app.services.extractors.pdf_extractor import extract_pdf_text
from app.services.extractors.pptx_extractor import extract_pptx_text
from app.services.extractors.text_extractor import extract_text_file

logger = logging.getLogger(__name__)

# ============================================================
# Constantes de configuration
# ============================================================

CHUNK_SIZE_TOKENS = 500       # taille cible d'un chunk
CHUNK_OVERLAP_TOKENS = 50     # overlap entre chunks (continuité sémantique)
EMBED_BATCH_SIZE = 50         # nombre de chunks par requête OpenAI
TIKTOKEN_ENCODING = "cl100k_base"  # encodeur des embeddings modernes OpenAI


# ============================================================
# Types internes
# ============================================================

@dataclass
class ChunkData:
    """Chunk prêt à être inséré en BDD (pas encore d'embedding)."""
    chunk_index: int
    page_number: int | None
    content: str
    token_count: int


# ============================================================
# Étape 1 — Dispatcher d'extraction (S5 J32 : PDF/DOCX, J35 : PPTX)
# ============================================================

def extract_document_content(file_path: str, file_type: str) -> list[dict]:
    """Route vers le bon parser selon file_type et unifie le format de sortie.

    Retourne : [{"section_number": int, "section_title": str | None, "content": str}, ...]
    Pour le PDF, section_number = numéro de page, section_title = None.
    Pour le DOCX, section_number = index du chapitre, section_title = titre du chapitre.
    Pour le PPTX, section_number = numéro de slide, section_title = titre de la slide.
    """
    if file_type == "pdf":
        return extract_pdf_text(file_path)
    elif file_type == "docx":
        return extract_docx_text(file_path)
    elif file_type == "pptx":
        return extract_pptx_text(file_path)
    elif file_type in ("txt", "md"):
        return extract_text_file(file_path)
    else:
        raise ValueError(f"Format non supporté : {file_type}")


# ============================================================
# Étape 2 — Chunking récursif par section (page PDF ou chapitre DOCX)
# ============================================================

# Encoder tiktoken initialisé une fois (chargement lent)
_encoder = tiktoken.get_encoding(TIKTOKEN_ENCODING)


def count_tokens(text: str) -> int:
    """Compte les tokens via tiktoken (cl100k_base = embeddings OpenAI)."""
    return len(_encoder.encode(text))


def _make_splitter() -> RecursiveCharacterTextSplitter:
    """Crée le splitter avec comptage en tokens (pas en caractères)."""
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE_TOKENS,
        chunk_overlap=CHUNK_OVERLAP_TOKENS,
        length_function=count_tokens,
        separators=["\n\n", "\n", ". ", " ", ""],  # priorité paragraphes > phrases
    )


def chunk_sections(sections: list[dict]) -> list[ChunkData]:
    """Découpe les sections (pages PDF ou chapitres DOCX) en chunks.

    Stratégie : on chunkifie section par section (un chunk reste sur une
    seule section), ce qui simplifie énormément la citation. L'overlap se
    fait intra-section uniquement. Identique au comportement J22 pour le
    PDF (une "section" y est simplement une page, sans titre).

    Le titre de section (DOCX uniquement) est préfixé au premier chunk de
    chaque section pour lui donner du contexte, sans dupliquer le titre
    dans tous les chunks d'une longue section.
    """
    splitter = _make_splitter()
    chunks: list[ChunkData] = []
    global_idx = 0

    for section in sections:
        section_title = section.get("section_title")
        section_chunks = splitter.split_text(section["content"])
        for i, content in enumerate(section_chunks):
            content = content.strip()
            if not content:
                continue
            if section_title and i == 0:
                content = f"{section_title}\n\n{content}"
            chunks.append(
                ChunkData(
                    chunk_index=global_idx,
                    page_number=section["section_number"],
                    content=content,
                    token_count=count_tokens(content),
                )
            )
            global_idx += 1

    return chunks


# ============================================================
# Étape 3 — Embeddings par batch
# ============================================================

async def embed_chunks(
    chunks: list[ChunkData],
    provider: OpenAIProvider,
) -> list[list[float]]:
    """Embed tous les chunks par batchs de EMBED_BATCH_SIZE.

    Le retry sur RateLimitError est déjà géré dans OpenAIProvider.embed
    via @_retry_decorator. Si OpenAI tombe en panne, on lève après 3 essais.
    """
    all_embeddings: list[list[float]] = []
    total = len(chunks)

    for i in range(0, total, EMBED_BATCH_SIZE):
        batch = chunks[i : i + EMBED_BATCH_SIZE]
        texts = [c.content for c in batch]

        logger.info(
            "Embedding batch %d-%d / %d",
            i, min(i + EMBED_BATCH_SIZE, total), total,
        )

        embeddings = await provider.embed(texts)
        all_embeddings.extend(embeddings)

    return all_embeddings


# ============================================================
# Étape 4 — Orchestration complète (pour BackgroundTask)
# ============================================================

async def ingest_document(
    document_id: UUID,
    absolute_file_path: str,
    db: AsyncSession,
) -> None:
    """Pipeline complet d'ingestion d'un document.

    Met à jour Document.status à chaque étape pour permettre le polling
    côté frontend : parsing → chunking → embedding → ready.

    En cas d'erreur, status=error + error_message rempli.
    """
    # Récupère le document
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        logger.error("Document %s introuvable, ingestion annulée", document_id)
        return

    try:
        # ===== ÉTAPE 1 — PARSE =====
        document.status = "parsing"
        await db.commit()
        logger.info("[%s] Extraction (%s)…", document_id, document.file_type)

        sections = extract_document_content(absolute_file_path, document.file_type)
        document.page_count = len(sections)

        # ===== ÉTAPE 2 — CHUNK =====
        document.status = "chunking"
        await db.commit()
        logger.info("[%s] Chunking %d sections…", document_id, len(sections))

        chunk_datas = chunk_sections(sections)
        if not chunk_datas:
            raise ValueError("Aucun chunk généré (document vide après extraction)")

        # ===== ÉTAPE 3 — EMBED =====
        document.status = "embedding"
        await db.commit()
        logger.info("[%s] Embedding %d chunks…", document_id, len(chunk_datas))

        provider = OpenAIProvider()
        embeddings = await embed_chunks(chunk_datas, provider)

        if len(embeddings) != len(chunk_datas):
            raise RuntimeError(
                f"Mismatch chunks/embeddings : "
                f"{len(chunk_datas)} chunks ≠ {len(embeddings)} embeddings"
            )

        # ===== ÉTAPE 4 — INSERT EN BDD =====
        for chunk_data, embedding in zip(chunk_datas, embeddings, strict=True):
            chunk = Chunk(
                document_id=document_id,
                chunk_index=chunk_data.chunk_index,
                page_number=chunk_data.page_number,
                content=chunk_data.content,
                token_count=chunk_data.token_count,
                embedding=embedding,
            )
            db.add(chunk)

        # ===== ÉTAPE 5 — FINALISATION =====
        document.chunk_count = len(chunk_datas)
        document.status = "ready"
        await db.commit()
        logger.info(
            "[%s] ✓ Ingestion terminée : %d chunks sur %d sections",
            document_id, len(chunk_datas), len(sections),
        )

    except Exception as e:
        # Capture l'erreur dans le document pour que le frontend la voie
        logger.exception("[%s] Échec ingestion : %s", document_id, e)
        document.status = "error"
        document.error_message = f"{type(e).__name__}: {str(e)[:500]}"
        await db.commit()
