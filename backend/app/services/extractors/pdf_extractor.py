"""Extraction de texte depuis un fichier .pdf via pymupdf (S5 J36).

Remplace pypdf (page.extract_text()) qui casse parfois les mots lors de la
reconstruction du flux de texte (positionnement caractere par caractere
selon l'encodage du PDF source). pymupdf (import "fitz", nom historique)
reconstruit les mots de facon beaucoup plus fiable via page.get_text("text").
"""
from __future__ import annotations

import re
from pathlib import Path

import fitz  # pymupdf


def clean_extracted_text(text: str) -> str:
    """Corrige les artefacts residuels d'extraction PDF.

    Ne recolle PAS les mots casses par un espace au milieu (heuristique
    trop risquee, peut casser des expressions legitimes) -- pymupdf ne
    devrait de toute facon plus produire ce genre de coupure.
    """
    # Espace avant apostrophe : "l 'un" -> "l'un"
    text = re.sub(r"\s+'", "'", text)

    # Espace avant ponctuation : "mot ." -> "mot."
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)

    # Espaces multiples -> un seul
    text = re.sub(r" {2,}", " ", text)

    return text.strip()


def extract_pdf_text(file_path: str) -> list[dict]:
    """Extrait le texte d'un PDF, page par page.

    Retourne une liste de dicts :
        [{ "section_number": 1, "section_title": None, "content": "..." }, ...]
    Meme structure que les autres extractors (docx, pptx) pour rester
    compatible avec le dispatcher extract_document_content.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF introuvable : {file_path}")

    doc = fitz.open(str(path))
    sections: list[dict] = []

    try:
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text("text")
            text = clean_extracted_text(text)
            if text:
                sections.append({
                    "section_number": page_num,
                    "section_title": None,
                    "content": text,
                })
    finally:
        doc.close()

    if not sections:
        raise ValueError(
            "Aucun texte extractible. Le PDF est peut-être scanné "
            "(image-based) et nécessite un OCR — non supporté."
        )

    return sections
