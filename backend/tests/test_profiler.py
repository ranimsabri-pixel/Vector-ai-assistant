"""Tests du service de profilage des colonnes."""
import pandas as pd
import pytest

from app.services.profiler import (
    infer_dtype,
    profile_column,
    profile_dataframe,
)


class TestInferDtype:
    """Tests de l'inférence de type."""

    def test_numeric_int(self):
        s = pd.Series([1, 2, 3, 4, 5])
        assert infer_dtype(s) == "numeric"

    def test_numeric_float(self):
        s = pd.Series([1.5, 2.7, 3.14, 4.0])
        assert infer_dtype(s) == "numeric"

    def test_boolean_native(self):
        s = pd.Series([True, False, True, True])
        assert infer_dtype(s) == "boolean"

    def test_boolean_disguised_strings(self):
        s = pd.Series(["true", "false", "true", "false"])
        assert infer_dtype(s) == "boolean"

    def test_boolean_disguised_oui_non(self):
        s = pd.Series(["oui", "non", "oui", "oui"])
        assert infer_dtype(s) == "boolean"

    def test_datetime_iso(self):
        s = pd.Series(["2024-01-15", "2024-02-20", "2024-03-10"] * 20)
        assert infer_dtype(s) == "datetime"

    def test_datetime_fr_format(self):
        s = pd.Series(["15/01/2024", "20/02/2024", "10/03/2024"] * 20)
        assert infer_dtype(s) == "datetime"

    def test_categorical_low_unique(self):
        # 5 valeurs uniques sur 100 lignes => catégoriel
        s = pd.Series(["A", "B", "C", "D", "E"] * 20)
        assert infer_dtype(s) == "categorical"

    def test_text_high_unique(self):
        # 100 valeurs uniques sur 100 lignes => texte (identifiants/emails/etc)
        s = pd.Series([f"user_{i}@example.com" for i in range(100)])
        assert infer_dtype(s) == "text"

    def test_empty_series_returns_text(self):
        s = pd.Series([], dtype=object)
        assert infer_dtype(s) == "text"


class TestProfileColumn:
    """Tests du profilage d'une colonne unique."""

    def test_numeric_column_stats(self):
        s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = profile_column(s, "ages")
        assert result["name"] == "ages"
        assert result["dtype"] == "numeric"
        assert result["null_count"] == 0
        assert result["unique_count"] == 10
        stats = result["sample_values"]["stats"]
        assert stats["min"] == 1
        assert stats["max"] == 10
        assert stats["mean"] == 5.5

    def test_categorical_column_top_values(self):
        # 10 éléments, 3 uniques => ratio 0.3 (bien sous le seuil 0.5)
        s = pd.Series(["FR", "FR", "FR", "FR", "BE", "BE", "BE", "ES", "ES", "FR"])
        result = profile_column(s, "country")
        assert result["dtype"] == "categorical"
        top = result["sample_values"]["stats"]["top_values"]
        assert top["FR"] == 5
        assert top["BE"] == 3
        assert top["ES"] == 2

    def test_null_counting(self):
        s = pd.Series([1, 2, None, 4, None])
        result = profile_column(s, "values")
        assert result["null_count"] == 2
        assert result["is_nullable"] is True

    def test_no_nulls(self):
        s = pd.Series([1, 2, 3])
        result = profile_column(s, "values")
        assert result["null_count"] == 0
        assert result["is_nullable"] is False


class TestProfileDataframe:
    """Tests du profilage complet d'un DataFrame."""

    def test_full_pipeline(self):
        df = pd.DataFrame({
            "client_id": ["C001", "C002", "C003", "C004", "C005"],
            "industry": ["Tech", "Tech", "Health", "Tech", "Health"],
            "signup_date": ["2024-01-01", "2024-02-15", "2024-03-20", "2024-04-10", "2024-05-05"],
            "score": [8, 7, 9, 6, 10],
        })
        result = profile_dataframe(df)

        assert len(result["columns"]) == 4
        assert "quality_score" in result
        assert "quality_issues" in result

        # signup_date doit être marquée comme date principale
        date_cols = [c for c in result["columns"] if c["dtype"] == "datetime"]
        assert len(date_cols) == 1
        assert date_cols[0]["is_date_main"] is True

    def test_quality_score_complete_data(self):
        df = pd.DataFrame({
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z", "x", "y"],
        })
        result = profile_dataframe(df)
        # Aucun null, aucune colonne constante => score proche de 1
        assert result["quality_score"] >= 0.95

    def test_quality_score_with_nulls(self):
        df = pd.DataFrame({
            "a": [1, None, None, None, None],  # 80% nulls
            "b": ["x", "y", "z", "x", "y"],
        })
        result = profile_dataframe(df)
        # Beaucoup de nulls => score plus bas
        assert result["quality_score"] < 0.7

    def test_constant_column_detected(self):
        df = pd.DataFrame({
            "constant": ["same", "same", "same", "same"],
            "varied": [1, 2, 3, 4],
        })
        result = profile_dataframe(df)
        assert "constant" in result["quality_issues"]["constant_columns"]

    def test_duplicate_rows_detected(self):
        df = pd.DataFrame({
            "a": [1, 2, 3, 1, 2],
            "b": ["x", "y", "z", "x", "y"],
        })
        result = profile_dataframe(df)
        assert result["quality_issues"]["duplicate_rows"] == 2