"""Tests unitaires purs du moteur de calcul de widgets (S5 J36/J37).

On teste directement les fonctions _compute_* et apply_filters (pandas
pur, aucune DB/HTTP) plutot que le dispatcher compute_widget_data(), qui
exige de vrais objets ORM Dataset/DashboardWidget + un FileStorage — hors
scope pour des tests unitaires rapides (le dispatcher n'est qu'un routage
+ try/except autour de ces fonctions, deja couvert indirectement).
"""
import pandas as pd
import pytest

from app.services.widget_compute import (
    _compute_bar_chart,
    _compute_correlation_matrix,
    _compute_data_table,
    _compute_heatmap,
    _compute_histogram,
    _compute_kpi,
    _compute_pie_chart,
    apply_filters,
)


class TestComputeKpi:
    def test_sum(self):
        df = pd.DataFrame({"sales": [100, 200, 300]})
        result = _compute_kpi(df, {"column": "sales", "aggregate": "sum"})
        assert result["value"] == 600.0

    def test_avg(self):
        df = pd.DataFrame({"sales": [100, 200, 300]})
        result = _compute_kpi(df, {"column": "sales", "aggregate": "avg"})
        assert result["value"] == 200.0

    def test_missing_column_returns_error(self):
        df = pd.DataFrame({"sales": [100, 200]})
        result = _compute_kpi(df, {"column": "missing", "aggregate": "sum"})
        assert "error" in result

    def test_no_numeric_values_returns_error(self):
        df = pd.DataFrame({"sales": ["a", "b", "c"]})
        result = _compute_kpi(df, {"column": "sales", "aggregate": "sum"})
        assert "error" in result


class TestComputeBarChart:
    def test_simple_groupby_sum(self):
        df = pd.DataFrame({"region": ["Nord", "Sud", "Nord"], "ventes": [100, 200, 50]})
        result = _compute_bar_chart(
            df, {"x_column": "region", "y_column": "ventes", "aggregate": "sum"}
        )
        assert result["labels"] == ["Nord", "Sud"]
        assert result["values"] == [150.0, 200.0]

    def test_missing_column_returns_error(self):
        df = pd.DataFrame({"region": ["Nord"]})
        result = _compute_bar_chart(df, {"x_column": "region", "y_column": "missing"})
        assert "error" in result


class TestComputePieChart:
    def test_percentages_sum_to_100(self):
        df = pd.DataFrame({"cat": ["A", "A", "B"], "val": [10, 10, 20]})
        result = _compute_pie_chart(
            df, {"category_column": "cat", "value_column": "val", "aggregate": "sum"}
        )
        assert result["total"] == 40.0
        assert sum(result["percentages"]) == pytest.approx(100.0)


class TestComputeDataTable:
    def test_respects_limit_and_sort(self):
        df = pd.DataFrame({"name": ["C", "A", "B"], "value": [3, 1, 2]})
        result = _compute_data_table(
            df, {"columns": ["name", "value"], "sort_by": "value", "sort_order": "asc", "limit": 2}
        )
        assert result["columns"] == ["name", "value"]
        assert len(result["rows"]) == 2
        assert result["rows"][0][0] == "A"

    def test_no_valid_column_returns_error(self):
        df = pd.DataFrame({"name": ["A"]})
        result = _compute_data_table(df, {"columns": ["missing"]})
        assert "error" in result


class TestComputeCorrelationMatrix:
    def test_perfect_and_anti_correlation(self):
        df = pd.DataFrame({
            "a": [1, 2, 3, 4, 5],
            "b": [2, 4, 6, 8, 10],  # correle parfaitement avec a
            "c": [5, 4, 3, 2, 1],   # anti-correle avec a
        })
        result = _compute_correlation_matrix(df, {"columns": ["a", "b", "c"]})
        assert result["matrix"][0][1] == 1.0
        assert result["matrix"][0][2] == -1.0

    def test_requires_at_least_two_numeric_columns(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        result = _compute_correlation_matrix(df, {"columns": ["a", "b"]})
        assert "error" in result


class TestComputeHeatmap:
    def test_pivot_shape(self):
        df = pd.DataFrame({
            "region": ["Nord", "Nord", "Sud"],
            "produit": ["A", "B", "A"],
            "ventes": [10, 20, 30],
        })
        result = _compute_heatmap(
            df, {"row_column": "region", "col_column": "produit", "value_column": "ventes"}
        )
        assert set(result["rows"]) == {"Nord", "Sud"}
        assert set(result["cols"]) == {"A", "B"}


class TestComputeHistogram:
    def test_bin_count_respected(self):
        df = pd.DataFrame({"values": list(range(100))})
        result = _compute_histogram(df, {"column": "values", "bin_count": 10})
        assert len(result["bins"]) == 10
        assert sum(result["counts"]) == 100

    def test_missing_column_returns_error(self):
        df = pd.DataFrame({"values": [1, 2, 3]})
        result = _compute_histogram(df, {"column": "missing"})
        assert "error" in result


class TestApplyFilters:
    def test_eq(self):
        df = pd.DataFrame({"region": ["Nord", "Sud", "Nord"]})
        result = apply_filters(df, [{"column": "region", "op": "eq", "value": "Nord"}])
        assert len(result) == 2

    def test_gte(self):
        df = pd.DataFrame({"value": [10, 20, 30]})
        result = apply_filters(df, [{"column": "value", "op": "gte", "value": 20}])
        assert sorted(result["value"].tolist()) == [20, 30]

    def test_between(self):
        df = pd.DataFrame({"value": [5, 15, 25, 35]})
        result = apply_filters(df, [{"column": "value", "op": "between", "value": [10, 30]}])
        assert sorted(result["value"].tolist()) == [15, 25]

    def test_unknown_column_ignored_silently(self):
        """Un filtre sur une colonne absente ne doit jamais faire planter le calcul."""
        df = pd.DataFrame({"region": ["Nord", "Sud"]})
        result = apply_filters(df, [{"column": "inexistante", "op": "eq", "value": "x"}])
        assert len(result) == 2  # dataframe inchange

    def test_no_filters_returns_same_df(self):
        df = pd.DataFrame({"region": ["Nord"]})
        result = apply_filters(df, None)
        assert len(result) == 1
