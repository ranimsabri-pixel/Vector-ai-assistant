"""Tests unitaires purs des fonctions internes de DatasetService (S5 J44
Bloc C) — pas de DB, pas de HTTP. Cible les methodes @staticmethod (deja
pures) qui ne sont exercees qu'indirectement par test_datasets.py."""
import pandas as pd
import pytest

from app.services.datasets import DatasetService


class TestCoerceBoolean:
    def test_recognizes_true_values(self):
        s = pd.Series(["true", "1", "yes", "oui", "OUI", "  Oui  "])
        result = DatasetService._coerce_boolean(s)
        assert result.tolist() == [True, True, True, True, True, True]

    def test_recognizes_false_values(self):
        s = pd.Series(["false", "0", "no", "non"])
        result = DatasetService._coerce_boolean(s)
        assert result.tolist() == [False, False, False, False]

    def test_unrecognized_value_returns_none(self):
        s = pd.Series(["peut-etre", "maybe"])
        result = DatasetService._coerce_boolean(s)
        assert result.tolist() == [None, None]


class TestApplyColumnOverrides:
    def test_delete_marks_column_dropped(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        result = DatasetService._apply_column_overrides(
            df, [{"original_name": "b", "deleted": True}]
        )
        assert list(result.columns) == ["a"]

    def test_rename_column(self):
        df = pd.DataFrame({"cp": ["75001"]})
        result = DatasetService._apply_column_overrides(
            df, [{"original_name": "cp", "new_name": "code_postal"}]
        )
        assert list(result.columns) == ["code_postal"]

    def test_force_numeric_type(self):
        df = pd.DataFrame({"value": ["10", "20", "abc"]})
        result = DatasetService._apply_column_overrides(
            df, [{"original_name": "value", "type": "numeric"}]
        )
        assert result["value"].tolist()[:2] == [10.0, 20.0]
        assert pd.isna(result["value"].iloc[2])

    def test_force_text_prevents_numeric_reinterpretation(self):
        """Cas d'usage reel (J38) : code postal force en texte pour ne pas
        etre re-detecte comme numerique par infer_dtype."""
        df = pd.DataFrame({"cp": [75001, 75002]})
        result = DatasetService._apply_column_overrides(
            df, [{"original_name": "cp", "type": "text"}]
        )
        assert result["cp"].tolist() == ["75001", "75002"]

    def test_force_boolean_type(self):
        df = pd.DataFrame({"actif": ["oui", "non"]})
        result = DatasetService._apply_column_overrides(
            df, [{"original_name": "actif", "type": "boolean"}]
        )
        assert result["actif"].tolist() == [True, False]

    def test_rename_then_force_type_uses_final_name(self):
        """Le type force doit s'appliquer sur le NOUVEAU nom, pas l'ancien."""
        df = pd.DataFrame({"val": ["10", "20"]})
        result = DatasetService._apply_column_overrides(
            df,
            [{"original_name": "val", "new_name": "valeur", "type": "numeric"}],
        )
        assert list(result.columns) == ["valeur"]
        assert result["valeur"].tolist() == [10.0, 20.0]

    def test_override_on_missing_column_ignored_silently(self):
        df = pd.DataFrame({"a": [1]})
        result = DatasetService._apply_column_overrides(
            df, [{"original_name": "inexistante", "deleted": True}]
        )
        assert list(result.columns) == ["a"]


class TestForcedTypesByFinalName:
    def test_maps_type_to_final_renamed_name(self):
        overrides = [
            {"original_name": "cp", "new_name": "code_postal", "type": "text"},
        ]
        result = DatasetService._forced_types_by_final_name(overrides)
        assert result == {"code_postal": "text"}

    def test_deleted_columns_excluded(self):
        overrides = [
            {"original_name": "a", "type": "numeric"},
            {"original_name": "b", "type": "numeric", "deleted": True},
        ]
        result = DatasetService._forced_types_by_final_name(overrides)
        assert result == {"a": "numeric"}

    def test_no_type_specified_excluded(self):
        overrides = [{"original_name": "a", "new_name": "renamed"}]
        result = DatasetService._forced_types_by_final_name(overrides)
        assert result == {}


class TestParseSummary:
    def test_parses_csv_rows_columns_and_sample(self, tmp_path):
        csv_path = tmp_path / "test.csv"
        csv_path.write_text("name,value\nA,1\nB,2\nC,3\n")

        service = DatasetService(db=None, storage=None)
        row_count, column_count, sample = service._parse_summary(csv_path, ".csv")

        assert row_count == 3
        assert column_count == 2
        assert sample["columns"] == ["name", "value"]
        assert len(sample["rows"]) == 3

    def test_sample_capped_at_sample_rows(self, tmp_path):
        csv_path = tmp_path / "big.csv"
        lines = ["id"] + [str(i) for i in range(50)]
        csv_path.write_text("\n".join(lines) + "\n")

        service = DatasetService(db=None, storage=None)
        row_count, _, sample = service._parse_summary(csv_path, ".csv")

        assert row_count == 50
        assert len(sample["rows"]) == 5  # SAMPLE_ROWS
