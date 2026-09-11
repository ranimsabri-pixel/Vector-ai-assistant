"""Tests des calculs avancés (J12) : ratio, breakdown, trend."""
import pandas as pd
import pytest

from app.services.kpi_calculator import (
    KPISpec,
    calculate_ratio,
    calculate_breakdown,
    calculate_trend,
    _apply_filter,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def df_crm():
    """DataFrame style CRM."""
    return pd.DataFrame({
        "client_id": list(range(1, 21)),
        "segment": ["Premium"] * 5 + ["Standard"] * 10 + ["Starter"] * 5,
        "status": ["Active"] * 15 + ["Churned"] * 5,
        "amount": [1000, 1200, 800, 950, 1100, 500, 600, 550, 700, 480,
                   620, 750, 530, 680, 720, 200, 250, 180, 220, 240],
    })


@pytest.fixture
def df_trend():
    """DataFrame avec une colonne datetime pour les trends."""
    dates = pd.date_range("2024-01-01", periods=12, freq="ME")
    return pd.DataFrame({
        "transaction_date": list(dates) + list(dates),
        "amount": [100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650,
                   120, 170, 220, 270, 320, 370, 420, 470, 520, 570, 620, 670],
    })


# ============================================================
# Apply filter
# ============================================================

class TestApplyFilter:
    def test_eq(self, df_crm):
        result = _apply_filter(df_crm, {"column": "status", "value": "Churned"})
        assert len(result) == 5

    def test_ne(self, df_crm):
        result = _apply_filter(df_crm, {"column": "status", "op": "ne", "value": "Churned"})
        assert len(result) == 15

    def test_gt(self, df_crm):
        result = _apply_filter(df_crm, {"column": "amount", "op": "gt", "value": 500})
        assert len(result) == 13  # 5 Premium + 8 Standard (les 4 < 500 et 480 exclus)
        assert all(result["amount"] > 500)

    def test_in(self, df_crm):
        result = _apply_filter(df_crm, {"column": "segment", "op": "in", "value": ["Premium", "Starter"]})
        assert len(result) == 10

    def test_missing_column_raises(self, df_crm):
        with pytest.raises(ValueError, match="introuvable"):
            _apply_filter(df_crm, {"column": "nope", "value": "x"})


# ============================================================
# Ratio
# ============================================================

class TestRatio:
    def test_churn_rate(self, df_crm):
        spec = KPISpec(
            id="churn", title="Churn", description="",
            type="ratio",
            filter={"column": "status", "value": "Churned"},
        )
        result = calculate_ratio(df_crm, spec)
        assert result.raw_value == 25.0  # 5/20
        assert result.unit == "%"

    def test_zero_total(self):
        df = pd.DataFrame({"x": []})
        spec = KPISpec(
            id="r", title="", description="",
            type="ratio",
            filter={"column": "x", "value": 1},
        )
        result = calculate_ratio(df, spec)
        assert result.raw_value == 0.0

    def test_missing_filter_raises(self, df_crm):
        spec = KPISpec(id="r", title="", description="", type="ratio")
        with pytest.raises(ValueError, match="filter"):
            calculate_ratio(df_crm, spec)


# ============================================================
# Breakdown
# ============================================================

class TestBreakdown:
    def test_count_by_segment(self, df_crm):
        spec = KPISpec(
            id="b", title="", description="",
            type="breakdown",
            group_by="segment",
            aggregation="count",
        )
        result = calculate_breakdown(df_crm, spec)
        breakdown = result.metadata["breakdown"]
        assert breakdown["Standard"] == 10
        assert breakdown["Premium"] == 5
        assert breakdown["Starter"] == 5

    def test_sum_by_segment(self, df_crm):
        spec = KPISpec(
            id="b", title="", description="",
            type="breakdown",
            group_by="segment",
            column="amount",
            aggregation="sum",
        )
        result = calculate_breakdown(df_crm, spec)
        breakdown = result.metadata["breakdown"]
        # Premium : 1000+1200+800+950+1100 = 5050
        assert breakdown["Premium"] == 5050.0

    def test_mean_by_segment(self, df_crm):
        spec = KPISpec(
            id="b", title="", description="",
            type="breakdown",
            group_by="segment",
            column="amount",
            aggregation="mean",
        )
        result = calculate_breakdown(df_crm, spec)
        breakdown = result.metadata["breakdown"]
        assert breakdown["Premium"] == 1010.0  # 5050/5

    def test_top_n_limits(self, df_crm):
        spec = KPISpec(
            id="b", title="", description="",
            type="breakdown",
            group_by="segment",
            aggregation="count",
            top_n=2,
        )
        result = calculate_breakdown(df_crm, spec)
        assert len(result.metadata["breakdown"]) == 2

    def test_sorted_desc(self, df_crm):
        spec = KPISpec(
            id="b", title="", description="",
            type="breakdown",
            group_by="segment",
            aggregation="count",
        )
        result = calculate_breakdown(df_crm, spec)
        # Premier item = la plus grande catégorie
        first_key = list(result.metadata["breakdown"].keys())[0]
        assert first_key == "Standard"  # 10 clients

    def test_missing_group_by_raises(self, df_crm):
        spec = KPISpec(id="b", title="", description="", type="breakdown")
        with pytest.raises(ValueError, match="group_by"):
            calculate_breakdown(df_crm, spec)


# ============================================================
# Trend
# ============================================================

class TestTrend:
    def test_count_monthly(self, df_trend):
        spec = KPISpec(
            id="t", title="", description="",
            type="trend",
            time_column="transaction_date",
            aggregation="count",
            granularity="month",
        )
        result = calculate_trend(df_trend, spec)
        # 12 mois avec 2 lignes chacun → 12 points de valeur 2
        points = result.metadata["points"]
        assert len(points) == 12
        assert all(p["value"] == 2 for p in points)

    def test_sum_monthly(self, df_trend):
        spec = KPISpec(
            id="t", title="", description="",
            type="trend",
            time_column="transaction_date",
            column="amount",
            aggregation="sum",
            granularity="month",
        )
        result = calculate_trend(df_trend, spec)
        points = result.metadata["points"]
        # Premier mois : 100 + 120 = 220
        assert points[0]["value"] == 220.0

    def test_chart_type_is_line(self, df_trend):
        spec = KPISpec(
            id="t", title="", description="",
            type="trend",
            time_column="transaction_date",
            aggregation="count",
        )
        result = calculate_trend(df_trend, spec)
        assert result.chart_type == "line"

    def test_missing_time_column_raises(self, df_trend):
        spec = KPISpec(id="t", title="", description="", type="trend")
        with pytest.raises(ValueError, match="time_column"):
            calculate_trend(df_trend, spec)

    def test_invalid_granularity_raises(self, df_trend):
        spec = KPISpec(
            id="t", title="", description="",
            type="trend",
            time_column="transaction_date",
            granularity="fortnight",
        )
        with pytest.raises(ValueError, match="Granularité"):
            calculate_trend(df_trend, spec)