"""
Service de profilage automatique des colonnes d'un dataset.
Inspecte un DataFrame pandas et retourne pour chaque colonne :
- Le type inféré (numeric, categorical, datetime, text, boolean)
- Statistiques (null_count, unique_count, min/max/mean...)
- Échantillons représentatifs
Plus une analyse globale de qualité du dataset.
"""
from typing import Any

import numpy as np
import pandas as pd

# Seuils heuristiques pour distinguer catégoriel et texte libre
CATEGORICAL_MAX_UNIQUE = 50         # si plus de 50 valeurs uniques, c'est probablement du texte
CATEGORICAL_MAX_RATIO = 0.5          # si plus de 50% de valeurs uniques, c'est du texte
SAMPLE_SIZE = 5                      # nombre de valeurs représentatives à garder
DATE_PARSE_THRESHOLD = 0.8           # 80% d'un échantillon doit parser en date pour qualifier
HIGH_NULL_THRESHOLD = 0.3            # une colonne avec >30% de NULL est signalée


# ============================================================
# Inférence de type
# ============================================================

def infer_dtype(series: pd.Series) -> str:
    """
    Infère le type sémantique d'une série (sur les valeurs non-null).
    Retourne : "numeric" | "categorical" | "datetime" | "text" | "boolean"
    """
    if len(series) == 0:
        return "text"

    # 1. Booléen natif
    if pd.api.types.is_bool_dtype(series):
        return "boolean"

    # 2. Booléen déguisé (True/False, 0/1, yes/no en string)
    unique_str = set(series.astype(str).str.lower().unique())
    if len(unique_str) <= 2 and unique_str.issubset(
        {"true", "false", "0", "1", "yes", "no", "oui", "non"}
    ):
        return "boolean"

    # 3. Numérique
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"

    # 4. Datetime (heuristique : on essaie de parser un échantillon)
    if _looks_like_date(series):
        return "datetime"

    # 5. Catégoriel vs texte
    n = len(series)
    nunique = series.nunique()
    if (
        nunique <= CATEGORICAL_MAX_UNIQUE
        and (nunique / n) < CATEGORICAL_MAX_RATIO
    ):
        return "categorical"

    return "text"


def _looks_like_date(series: pd.Series) -> bool:
    """Teste si une série ressemble à des dates en parsant un échantillon."""
    sample = series.head(50).astype(str)
    try:
        parsed = pd.to_datetime(sample, errors="coerce")
        valid_ratio = parsed.notna().sum() / max(len(sample), 1)
        return valid_ratio > DATE_PARSE_THRESHOLD
    except Exception:
        return False


# ============================================================
# Stats par type
# ============================================================

def _get_samples(series: pd.Series, dtype: str) -> list[Any]:
    """Échantillons représentatifs, JSON-serializable."""
    if dtype == "categorical":
        # Pour catégoriel : top valeurs par fréquence
        return series.value_counts().head(SAMPLE_SIZE).index.astype(str).tolist()
    # Sinon premières valeurs distinctes
    samples = series.drop_duplicates().head(SAMPLE_SIZE).tolist()
    return [_to_json_safe(s) for s in samples]


def _get_stats(series: pd.Series, dtype: str) -> dict[str, Any]:
    """Statistiques spécifiques au type détecté."""
    try:
        if dtype == "numeric":
            return {
                "min": _to_json_safe(series.min()),
                "max": _to_json_safe(series.max()),
                "mean": round(float(series.mean()), 2),
                "median": _to_json_safe(series.median()),
                "std": round(float(series.std()), 2) if len(series) > 1 else 0,
            }
        if dtype == "datetime":
            parsed = pd.to_datetime(series, errors="coerce")
            valid = parsed.dropna()
            if len(valid) == 0:
                return {}
            return {
                "min": str(valid.min().date()),
                "max": str(valid.max().date()),
                "span_days": int((valid.max() - valid.min()).days),
            }
        if dtype == "categorical":
            top = series.value_counts().head(5)
            return {
                "top_values": {str(k): int(v) for k, v in top.items()},
            }
        if dtype == "boolean":
            counts = series.astype(str).str.lower().value_counts()
            return {
                "true_count": int(counts.get("true", 0) + counts.get("1", 0) + counts.get("yes", 0) + counts.get("oui", 0)),
                "false_count": int(counts.get("false", 0) + counts.get("0", 0) + counts.get("no", 0) + counts.get("non", 0)),
            }
    except Exception:
        return {}
    return {}


def compute_histogram_bins(series: pd.Series, n_bins: int = 15) -> list[dict[str, Any]]:
    """Histogramme d'une colonne numérique. Gère le cas variance nulle
    (toutes les valeurs identiques) et les valeurs mal formatées."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 2:
        return []
    if s.min() == s.max():
        return [{"bin_start": float(s.min()), "bin_end": float(s.max()), "count": int(len(s))}]
    counts, edges = np.histogram(s, bins=n_bins)
    return [
        {"bin_start": float(edges[i]), "bin_end": float(edges[i + 1]), "count": int(counts[i])}
        for i in range(len(counts))
    ]


def compute_numeric_stats(series: pd.Series) -> dict[str, Any] | None:
    """Statistiques enrichies pour une colonne numérique (S5 J39)."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) == 0:
        return None
    return {
        "min": float(s.min()),
        "max": float(s.max()),
        "mean": float(s.mean()),
        "median": float(s.median()),
        "std_dev": float(s.std()) if s.count() > 1 else 0.0,
        "p25": float(s.quantile(0.25)),
        "p75": float(s.quantile(0.75)),
        "histogram_bins": compute_histogram_bins(s, n_bins=15),
    }


def compute_categorical_stats(series: pd.Series) -> dict[str, Any] | None:
    """Top-10 valeurs + cardinalité totale pour une colonne catégorielle/texte (S5 J39)."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return None
    vc = non_null.astype(str).value_counts().head(10)
    return {
        "top_values": [{"value": str(v), "count": int(c)} for v, c in vc.items()],
        "total_unique": int(non_null.nunique()),
    }


def compute_date_distribution(dates: pd.Series) -> list[dict[str, Any]]:
    """Distribution temporelle par mois (ou année si la plage dépasse 3 ans)."""
    span_days = (dates.max() - dates.min()).days
    freq = "M" if span_days < 3 * 365 else "Y"
    buckets = dates.dt.to_period(freq).value_counts().sort_index()
    return [{"period": str(p), "count": int(c)} for p, c in buckets.items()]


def compute_date_stats(series: pd.Series) -> dict[str, Any] | None:
    """Statistiques enrichies pour une colonne date (S5 J39)."""
    dates = pd.to_datetime(series, errors="coerce").dropna()
    if len(dates) == 0:
        return None
    return {
        "min_date": dates.min().isoformat(),
        "max_date": dates.max().isoformat(),
        "date_distribution": compute_date_distribution(dates),
    }


def _to_json_safe(value: Any) -> Any:
    """Convertit les types numpy/pandas en types Python pour JSON."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return str(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


# ============================================================
# Profile d'une colonne
# ============================================================

def profile_column(series: pd.Series, name: str) -> dict[str, Any]:
    """Profile complet d'une colonne unique."""
    null_count = int(series.isna().sum())
    non_null = series.dropna()
    unique_count = int(non_null.nunique())

    dtype = infer_dtype(non_null)
    samples = _get_samples(non_null, dtype)
    stats = _get_stats(non_null, dtype)

    # On stocke samples + stats dans le JSONB sample_values
    sample_values = {"samples": samples, "stats": stats}

    # Statistiques enrichies par colonne (S5 J39), stockées dans des champs
    # JSONB dédiés et calculées selon le dtype détecté.
    numeric_stats = compute_numeric_stats(non_null) if dtype == "numeric" else None
    categorical_stats = (
        compute_categorical_stats(non_null) if dtype in ("categorical", "text") else None
    )
    date_stats = compute_date_stats(non_null) if dtype == "datetime" else None

    return {
        "name": name,
        "dtype": dtype,
        "is_nullable": null_count > 0,
        "null_count": null_count,
        "unique_count": unique_count,
        "sample_values": sample_values,
        "is_date_main": False,  # sera défini plus bas
        "numeric_stats": numeric_stats,
        "categorical_stats": categorical_stats,
        "date_stats": date_stats,
    }


# ============================================================
# Profile du DataFrame entier
# ============================================================

def profile_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    """
    Profile complet d'un DataFrame.

    Retourne :
    - columns: liste de profils colonne (à insérer dans dataset_columns)
    - quality_score: float entre 0 et 1
    - quality_issues: dict des anomalies détectées
    """
    columns = [profile_column(df[col], str(col)) for col in df.columns]

    # Désigner la colonne date principale = première datetime trouvée
    for col in columns:
        if col["dtype"] == "datetime":
            col["is_date_main"] = True
            break

    quality_score, quality_issues = _compute_quality(df, columns)

    return {
        "columns": columns,
        "quality_score": quality_score,
        "quality_issues": quality_issues,
    }


def _compute_quality(
    df: pd.DataFrame, columns: list[dict[str, Any]]
) -> tuple[float, dict[str, Any]]:
    """Calcule un score de qualité global et liste les anomalies."""
    total_cells = df.size
    total_nulls = int(df.isna().sum().sum())
    completeness = 1.0 - (total_nulls / total_cells) if total_cells > 0 else 1.0

    issues: dict[str, Any] = {
        "high_null_columns": [
            c["name"]
            for c in columns
            if c["null_count"] / max(len(df), 1) > HIGH_NULL_THRESHOLD
        ],
        "constant_columns": [
            c["name"] for c in columns if c["unique_count"] <= 1
        ],
        "duplicate_rows": int(df.duplicated().sum()),
        "total_nulls": total_nulls,
        "completeness_pct": round(completeness * 100, 1),
    }

    # Pénalités sur le score
    penalty = 0.0
    n_cols = max(len(columns), 1)
    if issues["high_null_columns"]:
        penalty += 0.1 * len(issues["high_null_columns"]) / n_cols
    if issues["constant_columns"]:
        penalty += 0.05 * len(issues["constant_columns"]) / n_cols

    quality_score = max(0.0, min(1.0, completeness - penalty))
    return round(quality_score, 3), issues
