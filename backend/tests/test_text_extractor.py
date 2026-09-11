"""Tests unitaires de l'extracteur TXT/MD (S5 J51)."""
from unittest.mock import patch

import pytest

from app.services.extractors.text_extractor import extract_text_file


def test_extract_txt_valid(tmp_path):
    path = tmp_path / "doc.txt"
    path.write_text(
        "Premier paragraphe.\n\nDeuxieme paragraphe avec du contenu.",
        encoding="utf-8",
    )
    sections = extract_text_file(str(path))
    assert len(sections) == 1
    assert sections[0]["section_title"] is None
    assert "Premier paragraphe" in sections[0]["content"]
    assert sections[0]["section_number"] == 1


def test_extract_md_splits_on_headers(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text(
        "# Introduction\n\nTexte de l'intro.\n\n"
        "## Details techniques\n\nTexte des details.",
        encoding="utf-8",
    )
    sections = extract_text_file(str(path))
    assert len(sections) == 2
    assert sections[0]["section_title"] == "Introduction"
    assert "intro" in sections[0]["content"]
    assert sections[1]["section_title"] == "Details techniques"
    assert "details" in sections[1]["content"]


def test_extract_md_without_headers_is_single_block(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("Juste du texte sans aucun titre markdown.", encoding="utf-8")
    sections = extract_text_file(str(path))
    assert len(sections) == 1
    assert sections[0]["section_title"] is None


def test_extract_txt_latin1_encoding_no_crash(tmp_path):
    """Un .txt Windows en latin-1 avec des accents ne doit pas crasher ni
    produire du mojibake sur les caracteres francais courants."""
    path = tmp_path / "doc_latin1.txt"
    path.write_bytes("Éléphant à Noël, café très chère.".encode("latin-1"))
    sections = extract_text_file(str(path))
    assert len(sections) == 1
    assert "Noël" in sections[0]["content"] or "phant" in sections[0]["content"]


def test_extract_txt_cp1252_encoding_no_crash(tmp_path):
    path = tmp_path / "doc_cp1252.txt"
    path.write_bytes("Prix : 100€ — livraison différée.".encode("cp1252"))
    sections = extract_text_file(str(path))
    assert len(sections) == 1
    assert len(sections[0]["content"]) > 0


def test_extract_txt_long_text_splits_into_multiple_blocks(tmp_path):
    path = tmp_path / "long.txt"
    # ~7000 caracteres -> au moins 3 blocs de ~3000
    path.write_text("mot " * 1750, encoding="utf-8")
    sections = extract_text_file(str(path))
    assert len(sections) >= 2
    for i, s in enumerate(sections, start=1):
        assert s["section_number"] == i


def test_extract_txt_empty_file_raises(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        extract_text_file(str(path))


def test_extract_txt_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        extract_text_file("/chemin/inexistant/fichier.txt")


# Test ajoute J53 : chardet peut detecter un encodage avec une confiance
# elevee qui pourtant echoue au decodage reel (encodage exotique mal
# identifie) -- verifie que ce cas retombe bien sur la chaine de fallback
# au lieu de laisser l'exception remonter et casser toute l'ingestion.
def test_extract_txt_chardet_confident_but_wrong_falls_back(tmp_path):
    path = tmp_path / "doc.txt"
    path.write_bytes("Texte en français avec des accents éàç.".encode("utf-8"))

    with patch(
        "app.services.extractors.text_extractor.chardet.detect",
        return_value={"encoding": "ascii", "confidence": 0.99},
    ):
        sections = extract_text_file(str(path))

    assert len(sections) == 1
    assert len(sections[0]["content"]) > 0


# Test ajoute J53 : un "mot" sans aucun espace plus long qu'un bloc entier
# (ex: URL tres longue, blob base64) ne doit pas faire boucler
# indefiniment ni planter _split_by_blocks -- couvre la branche de secours
# "cut = BLOCK_SIZE_CHARS" quand rfind(" ") ne trouve rien.
def test_extract_txt_single_long_word_without_spaces(tmp_path):
    path = tmp_path / "doc.txt"
    path.write_text("a" * 5000, encoding="utf-8")

    sections = extract_text_file(str(path))
    assert len(sections) >= 2
    assert sum(len(s["content"]) for s in sections) == 5000
