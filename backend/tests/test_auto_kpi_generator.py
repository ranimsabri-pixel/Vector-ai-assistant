"""Tests du générateur automatique de KPIs."""
from unittest.mock import MagicMock

import pytest

from app.services.auto_kpi_generator import (
    MAX_KPIS,
    _slugify,
    generate_kpis,
)


def make_column(name: str, dtype: str = "text", null_count: int = 0) -> MagicMock:
    """Helper pour créer un faux DatasetColumn."""
    col = MagicMock()
    col.name = name
    col.dtype = dtype
    col.null_count = null_count
    col.unique_count = 10
    return col


class TestSlugify:
    def test_simple(self):
        assert _slugify("nps_score") == "nps_score"

    def test_with_spaces(self):
        assert _slugify("Customer Name") == "customer_name"

    def test_with_special_chars(self):
        assert _slugify("price ($)") == "price"

    def test_strips_underscores(self):
        assert _slugify("__test__") == "test"


class TestGenerateKpis:
    def test_global_count_always_present(self):
        cols = []
        specs = generate_kpis(cols, 100)
        assert any(s.id == "global_count" for s in specs)

    def test_numeric_generates_three_kpis(self):
        cols = [make_column("score", "numeric")]
        specs = generate_kpis(cols, 100)
        # 1 global + 3 numeric = 4
        assert len(specs) == 4
        types = [s.type for s in specs]
        assert "mean" in types
        assert "min" in types
        assert "max" in types

    def test_categorical_generates_one_kpi(self):
        cols = [make_column("segment", "categorical")]
        specs = generate_kpis(cols, 100)
        assert len(specs) == 2  # 1 global + 1 categorical
        assert any(s.type == "count_distinct" for s in specs)

    def test_boolean_generates_true_rate(self):
        cols = [make_column("is_active", "boolean")]
        specs = generate_kpis(cols, 100)
        assert any(s.type == "true_rate" for s in specs)

    def test_datetime_generates_min_max(self):
        cols = [make_column("created_at", "datetime")]
        specs = generate_kpis(cols, 100)
        types = [s.type for s in specs if s.column == "created_at"]
        assert "min" in types
        assert "max" in types

    def test_high_null_column_generates_quality_kpi(self):
        # 30 nulls sur 100 → 30% nulls → KPI qualité
        cols = [make_column("optional_col", "numeric", null_count=30)]
        specs = generate_kpis(cols, 100)
        assert any(s.type == "nonnull_rate" for s in specs)

    def test_low_null_column_no_quality_kpi(self):
        # 1 null sur 100 → 1% → pas de KPI qualité
        cols = [make_column("col", "categorical", null_count=1)]
        specs = generate_kpis(cols, 100)
        assert not any(s.type == "nonnull_rate" for s in specs)

    def test_caps_at_max_kpis(self):
        # 10 colonnes numériques → 1 + 30 specs sans cap
        cols = [make_column(f"col_{i}", "numeric") for i in range(10)]
        specs = generate_kpis(cols, 100)
        assert len(specs) <= MAX_KPIS

    def test_text_column_generates_no_kpis(self):
        cols = [make_column("description", "text")]
        specs = generate_kpis(cols, 100)
        # Seulement le KPI global
        assert len(specs) == 1
        assert specs[0].id == "global_count"