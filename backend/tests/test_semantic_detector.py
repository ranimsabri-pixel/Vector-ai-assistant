"""Tests de la détection sémantique (étage règles uniquement)."""
from unittest.mock import MagicMock

import pytest

from app.services.semantic_detector import (
    DOMAIN_KEYWORDS,
    detect_domain_by_rules,
    build_user_prompt,
)


def make_column(name: str, dtype: str = "text") -> MagicMock:
    """Helper pour créer un faux DatasetColumn."""
    col = MagicMock()
    col.name = name
    col.dtype = dtype
    col.unique_count = 100
    col.null_count = 0
    col.sample_values = None
    return col


class TestDetectDomainByRules:
    """Détection du domaine par mots-clés sur les noms de colonnes."""

    def test_crm_detected(self):
        cols = [
            make_column("client_id"),
            make_column("contact_email"),
            make_column("segment"),
            make_column("lifecycle_stage"),
            make_column("nps_score"),
        ]
        result = detect_domain_by_rules(cols)
        assert result["primary_domain"] == "crm"
        assert result["confidence"] > 0

    def test_finance_detected(self):
        cols = [
            make_column("transaction_id"),
            make_column("amount"),
            make_column("payment_date"),
            make_column("invoice_number"),
        ]
        result = detect_domain_by_rules(cols)
        assert result["primary_domain"] == "finance"

    def test_marketing_detected(self):
        cols = [
            make_column("campaign_id"),
            make_column("channel"),
            make_column("click_count"),
            make_column("conversion_rate"),
        ]
        result = detect_domain_by_rules(cols)
        assert result["primary_domain"] == "marketing"

    def test_sales_detected(self):
        cols = [
            make_column("order_id"),
            make_column("product_name"),
            make_column("sale_amount"),
            make_column("sales_rep"),
        ]
        result = detect_domain_by_rules(cols)
        assert result["primary_domain"] == "sales"

    def test_unknown_domain_returns_other(self):
        cols = [
            make_column("zorglub"),
            make_column("blibli"),
            make_column("xyz"),
        ]
        result = detect_domain_by_rules(cols)
        assert result["primary_domain"] == "other"
        assert result["confidence"] == 0

    def test_confidence_capped_at_one(self):
        # Beaucoup de matches CRM => confiance plafonnée à 1
        cols = [
            make_column("client_id"),
            make_column("customer_segment"),
            make_column("contact_name"),
            make_column("lead_status"),
            make_column("nps_score"),
            make_column("lifecycle_stage"),
            make_column("churn_date"),
        ]
        result = detect_domain_by_rules(cols)
        assert result["confidence"] == 1.0

    def test_rule_scores_present_for_all_domains(self):
        cols = [make_column("client_id")]
        result = detect_domain_by_rules(cols)
        # Tous les domaines doivent avoir un score (même 0)
        for domain in DOMAIN_KEYWORDS:
            assert domain in result["rule_scores"]


class TestBuildUserPrompt:
    """Construction du prompt utilisateur pour le LLM."""

    def test_prompt_contains_dataset_name(self):
        dataset = MagicMock()
        dataset.name = "Mon Dataset"
        dataset.description = None
        dataset.row_count = 100
        dataset.column_count = 3
        cols = [make_column("col_a")]

        prompt = build_user_prompt(dataset, cols, "crm")
        assert "Mon Dataset" in prompt
        assert "100" in prompt
        assert "col_a" in prompt

    def test_prompt_contains_description_if_present(self):
        dataset = MagicMock()
        dataset.name = "Dataset"
        dataset.description = "Description du dataset"
        dataset.row_count = 10
        dataset.column_count = 1
        cols = [make_column("col_a")]

        prompt = build_user_prompt(dataset, cols, "other")
        assert "Description du dataset" in prompt

    def test_prompt_includes_rule_hint(self):
        dataset = MagicMock()
        dataset.name = "Dataset"
        dataset.description = None
        dataset.row_count = 10
        dataset.column_count = 1
        cols = [make_column("col_a")]

        prompt = build_user_prompt(dataset, cols, "marketing")
        assert "marketing" in prompt.lower()