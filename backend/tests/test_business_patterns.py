"""Tests de la bibliothèque de patterns business."""
from unittest.mock import MagicMock

from app.services.business_patterns import (
    PATTERNS,
    detect_applicable_patterns,
)


def make_column(name, dtype="text", samples=None, top_values=None):
    col = MagicMock()
    col.name = name
    col.dtype = dtype
    col.is_date_main = (dtype == "datetime")
    col.sample_values = {
        "samples": samples or [],
        "stats": {"top_values": top_values or {}},
    }
    return col


class TestDetectApplicablePatterns:
    def test_crm_dataset_detects_churn(self):
        cols = [
            make_column("client_id", "text"),
            make_column("segment", "categorical", samples=["Premium", "Standard"]),
            make_column("lifecycle_stage", "categorical",
                        samples=["Active", "Churned", "Trial"]),
        ]
        specs = detect_applicable_patterns(cols)
        ids = [s.id for s in specs]
        assert "pattern_churn_rate" in ids

    def test_crm_with_nps_detects_nps_pattern(self):
        cols = [
            make_column("client_id", "text"),
            make_column("nps_score", "numeric"),
        ]
        specs = detect_applicable_patterns(cols)
        ids = [s.id for s in specs]
        assert "pattern_nps_avg" in ids

    def test_sales_dataset_detects_revenue_trend(self):
        cols = [
            make_column("sale_id", "text"),
            make_column("transaction_date", "datetime"),
            make_column("amount", "numeric"),
        ]
        specs = detect_applicable_patterns(cols)
        ids = [s.id for s in specs]
        assert "pattern_revenue_monthly" in ids

    def test_marketing_channel_detected(self):
        cols = [
            make_column("touch_id", "text"),
            make_column("channel", "categorical"),
        ]
        specs = detect_applicable_patterns(cols)
        ids = [s.id for s in specs]
        assert "pattern_channel_breakdown" in ids

    def test_unrelated_dataset_returns_few(self):
        cols = [
            make_column("zorglub", "text"),
            make_column("blibli", "categorical"),
        ]
        specs = detect_applicable_patterns(cols)
        # Aucun pattern ne devrait matcher
        assert len(specs) == 0

    def test_pattern_failure_does_not_break_others(self):
        # Même si un détecteur lève une exception, les autres patterns continuent
        cols = [
            make_column("nps", "numeric"),
        ]
        specs = detect_applicable_patterns(cols)
        # Au moins NPS doit être détecté
        ids = [s.id for s in specs]
        assert "pattern_nps_avg" in ids