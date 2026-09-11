"""Tests du moteur de calcul des KPIs."""
import pandas as pd
import pytest

from app.services.kpi_calculator import (
    KPISpec,
    calculate_kpi,
    calculate_count,
    calculate_count_distinct,
    calculate_sum,
    calculate_mean,
    calculate_median,
    calculate_min,
    calculate_max,
    calculate_nonnull_rate,
    calculate_true_rate,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def df_basic():
    """DataFrame de test : 5 lignes, mix de types."""
    return pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "name": ["A", "B", "C", "D", "E"],
        "category": ["X", "Y", "X", "Y", "Z"],
        "score": [10.0, 20.0, 30.0, 40.0, 50.0],
        "is_active": [True, False, True, True, False],
        "with_nulls": [1, None, 3, None, 5],
    })


@pytest.fixture
def df_empty():
    return pd.DataFrame({"a": [], "b": []})


# ============================================================
# count
# ============================================================

class TestCount:
    def test_basic(self, df_basic):
        spec = KPISpec(id="x", title="t", description="d", type="count")
        result = calculate_count(df_basic, spec)
        assert result.raw_value == 5
        assert result.value == 5

    def test_empty(self, df_empty):
        spec = KPISpec(id="x", title="t", description="d", type="count")
        result = calculate_count(df_empty, spec)
        assert result.raw_value == 0


# ============================================================
# count_distinct
# ============================================================

class TestCountDistinct:
    def test_basic(self, df_basic):
        spec = KPISpec(id="x", title="t", description="d", type="count_distinct", column="category")
        result = calculate_count_distinct(df_basic, spec)
        assert result.raw_value == 3  # X, Y, Z

    def test_with_nulls(self, df_basic):
        spec = KPISpec(id="x", title="t", description="d", type="count_distinct", column="with_nulls")
        result = calculate_count_distinct(df_basic, spec)
        assert result.raw_value == 3  # 1, 3, 5 (nulls exclus)

    def test_missing_column_raises(self, df_basic):
        spec = KPISpec(id="x", title="t", description="d", type="count_distinct", column="nonexistent")
        with pytest.raises(ValueError, match="Colonne introuvable"):
            calculate_count_distinct(df_basic, spec)

    def test_no_column_raises(self, df_basic):
        spec = KPISpec(id="x", title="t", description="d", type="count_distinct")
        with pytest.raises(ValueError, match="nécessite un nom de colonne"):
            calculate_count_distinct(df_basic, spec)


# ============================================================
# sum / mean / median / min / max
# ============================================================

class TestAggregations:
    def test_sum(self, df_basic):
        spec = KPISpec(id="x", title="t", description="d", type="sum", column="score")
        result = calculate_sum(df_basic, spec)
        assert result.raw_value == 150.0

    def test_mean(self, df_basic):
        spec = KPISpec(id="x", title="t", description="d", type="mean", column="score")
        result = calculate_mean(df_basic, spec)
        assert result.raw_value == 30.0

    def test_median(self, df_basic):
        spec = KPISpec(id="x", title="t", description="d", type="median", column="score")
        result = calculate_median(df_basic, spec)
        assert result.raw_value == 30.0

    def test_min(self, df_basic):
        spec = KPISpec(id="x", title="t", description="d", type="min", column="score")
        result = calculate_min(df_basic, spec)
        assert result.raw_value == 10.0

    def test_max(self, df_basic):
        spec = KPISpec(id="x", title="t", description="d", type="max", column="score")
        result = calculate_max(df_basic, spec)
        assert result.raw_value == 50.0

    def test_mean_with_nulls_skips_them(self, df_basic):
        # with_nulls = [1, None, 3, None, 5] → moyenne = (1+3+5)/3 = 3.0
        spec = KPISpec(id="x", title="t", description="d", type="mean", column="with_nulls")
        result = calculate_mean(df_basic, spec)
        assert result.raw_value == 3.0

    def test_mean_non_numeric_column_raises(self, df_basic):
        spec = KPISpec(id="x", title="t", description="d", type="mean", column="name")
        with pytest.raises(ValueError, match="pas numérique"):
            calculate_mean(df_basic, spec)

    def test_mean_all_null_returns_none(self):
        df = pd.DataFrame({"x": [None, None, None]})
        spec = KPISpec(id="x", title="t", description="d", type="mean", column="x")
        result = calculate_mean(df, spec)
        assert result.raw_value is None
        assert result.formatted == "—"


# ============================================================
# nonnull_rate
# ============================================================

class TestNonnullRate:
    def test_full_column(self, df_basic):
        spec = KPISpec(id="x", title="t", description="d", type="nonnull_rate", column="id")
        result = calculate_nonnull_rate(df_basic, spec)
        assert result.raw_value == 100.0
        assert result.unit == "%"

    def test_with_nulls(self, df_basic):
        # with_nulls a 2 nulls sur 5 → 60% complet
        spec = KPISpec(id="x", title="t", description="d", type="nonnull_rate", column="with_nulls")
        result = calculate_nonnull_rate(df_basic, spec)
        assert result.raw_value == 60.0


# ============================================================
# true_rate
# ============================================================

class TestTrueRate:
    def test_boolean_column(self, df_basic):
        # is_active = [T, F, T, T, F] → 3/5 = 60%
        spec = KPISpec(id="x", title="t", description="d", type="true_rate", column="is_active")
        result = calculate_true_rate(df_basic, spec)
        assert result.raw_value == 60.0

    def test_string_yes_no(self):
        df = pd.DataFrame({"answer": ["yes", "no", "yes", "yes"]})
        spec = KPISpec(id="x", title="t", description="d", type="true_rate", column="answer")
        result = calculate_true_rate(df, spec)
        assert result.raw_value == 75.0


# ============================================================
# Dispatcher principal
# ============================================================

class TestCalculateKPI:
    def test_dispatch_count(self, df_basic):
        spec = KPISpec(id="x", title="t", description="d", type="count")
        result = calculate_kpi(df_basic, spec)
        assert result.raw_value == 5

    def test_dispatch_unknown_type_raises(self, df_basic):
        spec = KPISpec(id="x", title="t", description="d", type="something_unknown")
        with pytest.raises(ValueError, match="non supporté"):
            calculate_kpi(df_basic, spec)


# ============================================================
# Formatage
# ============================================================

class TestFormatting:
    def test_format_thousands(self, df_basic):
        # Génère 1234 lignes
        df = pd.DataFrame({"x": range(1234)})
        spec = KPISpec(id="x", title="t", description="d", type="count")
        result = calculate_count(df, spec)
        # Doit contenir un espace de séparation
        assert " " in result.formatted

    def test_format_percentage(self, df_basic):
        spec = KPISpec(id="x", title="t", description="d", type="nonnull_rate", column="id")
        result = calculate_nonnull_rate(df_basic, spec)
        assert "%" in result.formatted