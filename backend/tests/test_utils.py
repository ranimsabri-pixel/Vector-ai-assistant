"""Tests unitaires purs : calcul de cout LLM (app/core/constants.py) et
extracteurs de documents (app/services/extractors/*)."""
import pytest

from app.core.constants import calculate_cost
from app.services.extractors.docx_extractor import extract_docx_text
from app.services.extractors.pdf_extractor import clean_extracted_text, extract_pdf_text
from app.services.extractors.pptx_extractor import extract_pptx_text


class TestCalculateCost:
    def test_gpt4o_cost(self):
        cost = calculate_cost("gpt-4o", 1000, 500)
        expected = (1000 / 1_000_000) * 2.50 + (500 / 1_000_000) * 10.00
        assert abs(cost - expected) < 1e-9

    def test_gpt4o_mini_cost(self):
        cost = calculate_cost("gpt-4o-mini", 1000, 500)
        expected = (1000 / 1_000_000) * 0.15 + (500 / 1_000_000) * 0.60
        assert abs(cost - expected) < 1e-9

    def test_versioned_model_name_matches_by_prefix(self):
        """L'API OpenAI renvoie un nom date (ex: gpt-4o-2024-08-06), jamais
        le nom nu — calculate_cost doit matcher par prefixe (regression du
        bug corrige en Feature 2 : le lookup exact tombait toujours en
        fallback avant ce fix)."""
        cost_dated = calculate_cost("gpt-4o-2024-08-06", 1000, 500)
        cost_nu = calculate_cost("gpt-4o", 1000, 500)
        assert cost_dated == cost_nu

    def test_mini_prefix_not_shadowed_by_gpt4o_prefix(self):
        """gpt-4o-mini-2024-07-18 doit matcher 'gpt-4o-mini' et pas 'gpt-4o'
        (les deux sont des prefixes valides, le plus long doit gagner)."""
        cost_dated_mini = calculate_cost("gpt-4o-mini-2024-07-18", 1000, 500)
        cost_mini = calculate_cost("gpt-4o-mini", 1000, 500)
        cost_4o = calculate_cost("gpt-4o", 1000, 500)
        assert cost_dated_mini == cost_mini
        assert cost_dated_mini != cost_4o

    def test_unknown_model_falls_back_to_default_pricing(self):
        """Un modele totalement inconnu ne plante pas : il retombe sur le
        tarif par defaut (pas zero, pour ne jamais sous-estimer un cout)."""
        cost = calculate_cost("modele-du-futur-inconnu", 1000, 500)
        assert cost > 0.0

    def test_zero_tokens_returns_zero_cost(self):
        assert calculate_cost("gpt-4o", 0, 0) == 0.0


class TestDocxExtractor:
    def test_returns_sections_with_content(self, tmp_path, mini_docx_bytes: bytes):
        docx_path = tmp_path / "test.docx"
        docx_path.write_bytes(mini_docx_bytes)

        sections = extract_docx_text(str(docx_path))
        assert len(sections) >= 1
        assert all("content" in s for s in sections)
        full_text = " ".join(s["content"] for s in sections)
        assert "Premier paragraphe" in full_text

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            extract_docx_text(str(tmp_path / "nexiste_pas.docx"))


class TestPptxExtractor:
    def test_returns_one_section_per_slide(self, tmp_path, mini_pptx_bytes: bytes):
        pptx_path = tmp_path / "test.pptx"
        pptx_path.write_bytes(mini_pptx_bytes)

        sections = extract_pptx_text(str(pptx_path))
        assert len(sections) == 2
        assert sections[0]["section_title"] == "Slide 1"
        assert sections[1]["section_title"] == "Slide 2"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            extract_pptx_text(str(tmp_path / "nexiste_pas.pptx"))


class TestPdfExtractor:
    def test_returns_one_section_per_page(self, tmp_path, mini_pdf_bytes: bytes):
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(mini_pdf_bytes)

        sections = extract_pdf_text(str(pdf_path))
        assert len(sections) == 2
        assert "document PDF de test" in sections[0]["content"]
        assert "deuxieme page" in sections[1]["content"]

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            extract_pdf_text(str(tmp_path / "nexiste_pas.pdf"))

    def test_clean_extracted_text_removes_space_before_punctuation(self):
        assert clean_extracted_text("Bonjour .") == "Bonjour."
        assert clean_extracted_text("l 'un") == "l'un"

    def test_clean_extracted_text_collapses_multiple_spaces(self):
        assert clean_extracted_text("mot1    mot2") == "mot1 mot2"
