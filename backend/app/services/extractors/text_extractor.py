"""Extraction de texte depuis un fichier .txt ou .md (S5 J51).

Meme structure de sortie que les autres extractors (pdf, docx, pptx),
pour rester compatible avec le dispatcher extract_document_content.

Pas d'encodage suppose : un fichier .txt Windows peut etre en UTF-8,
latin-1 (ISO-8859-1) ou cp1252 (Windows-1252) -- chardet detecte
l'encodage reel, avec un fallback progressif si la detection echoue.
"""
from __future__ import annotations

import re
from pathlib import Path

import chardet

# Taille cible d'un bloc en caracteres, pour rester dans le meme ordre de
# grandeur qu'une page PDF ou une section DOCX.
BLOCK_SIZE_CHARS = 3000

# Fallback d'encodages essayes dans l'ordre si chardet ne detecte rien
# d'exploitable (confiance trop faible).
_ENCODING_FALLBACKS = ["utf-8", "latin-1", "cp1252"]

_MD_HEADER_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)


def _decode(raw: bytes) -> str:
    detected = chardet.detect(raw)
    encoding = detected.get("encoding")
    confidence = detected.get("confidence") or 0

    if encoding and confidence >= 0.6:
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            pass

    for enc in _ENCODING_FALLBACKS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue

    # Dernier recours : latin-1 ne leve jamais UnicodeDecodeError (chaque
    # octet 0-255 y a un caractere valide), donc toujours exploitable.
    return raw.decode("latin-1")


def _split_by_blocks(text: str) -> list[str]:
    """Decoupe en blocs de ~BLOCK_SIZE_CHARS sans couper au milieu d'un mot."""
    blocks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= BLOCK_SIZE_CHARS:
            blocks.append(remaining)
            break
        cut = remaining.rfind(" ", 0, BLOCK_SIZE_CHARS)
        if cut <= 0:
            cut = BLOCK_SIZE_CHARS
        blocks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip()
    return blocks


def _split_markdown_by_headers(text: str) -> list[tuple[str | None, str]]:
    """Decoupe un markdown sur ses titres (# a ######).

    Retourne [(titre_ou_None, contenu), ...]. Si un bloc entre deux titres
    depasse BLOCK_SIZE_CHARS, il est re-decoupe (le titre est alors repete
    sur chacun de ses sous-blocs, comme le fait deja le prefixage DOCX cote
    ingestion pour le premier chunk d'une section).
    """
    matches = list(_MD_HEADER_RE.finditer(text))
    if not matches:
        return [(None, text)]

    sections: list[tuple[str | None, str]] = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append((None, preamble))

    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append((title, content))

    return sections or [(None, text)]


def extract_text_file(file_path: str) -> list[dict]:
    """Extrait le texte d'un fichier .txt ou .md, en blocs d'environ
    BLOCK_SIZE_CHARS caracteres (sur les titres pour le markdown, sinon
    par decoupe brute qui respecte les mots).

    Retourne une liste de dicts :
        [{ "section_number": 1, "section_title": "Introduction" | None, "content": "..." }, ...]
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier texte introuvable : {file_path}")

    raw = path.read_bytes()
    text = _decode(raw).strip()

    if not text:
        raise ValueError("Fichier texte vide, rien à extraire.")

    is_markdown = path.suffix.lower() == ".md"

    sections: list[dict] = []
    section_number = 0

    if is_markdown:
        for title, content in _split_markdown_by_headers(text):
            for block in _split_by_blocks(content):
                block = block.strip()
                if not block:
                    continue
                section_number += 1
                sections.append({
                    "section_number": section_number,
                    "section_title": title,
                    "content": block,
                })
    else:
        for block in _split_by_blocks(text):
            block = block.strip()
            if not block:
                continue
            section_number += 1
            sections.append({
                "section_number": section_number,
                "section_title": None,
                "content": block,
            })

    if not sections:
        raise ValueError("Aucun texte extractible dans ce fichier.")

    return sections
