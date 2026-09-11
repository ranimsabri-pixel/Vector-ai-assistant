"""
Moteur de calcul des KPIs.

Conception : fonctions pures (df + spec → résultat) pour faciliter les tests,
la composition et la mise en cache. Chaque type de calcul est isolé dans sa
propre fonction.

Types supportés en J11 (agrégations simples) :
- count : nombre de lignes
- count_distinct : nombre de valeurs uniques d'une colonne
- sum : somme d'une colonne numérique
- mean : moyenne
- median : médiane
- min : minimum
- max : maximum
- nonnull_rate : taux de complétude d'une colonne (% non-nulls)
- true_rate : taux de "vrai" sur une colonne booléenne

"""
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

# ============================================================
# Types : la "spec" décrit un calcul, le "result" porte la réponse
# ============================================================

@dataclass
class KPISpec:
    """Définition structurée d'un KPI calculable."""

    id: str
    """Identifiant unique pour référencer le spec."""

    title: str
    """Titre court lisible (ex: 'Taux de churn par segment')."""

    description: str
    """Phrase courte expliquant le KPI."""

    type: str
    """Type de calcul :
    Simples (J11) : count, count_distinct, sum, mean, median, min, max,
                    nonnull_rate, true_rate
    Complexes (J12) : ratio, breakdown, trend, top_n
    """

    column: str | None = None
    """Colonne ciblée (None pour count global)."""

    # === Champs spécifiques aux types complexes (J12) ===

    filter: dict[str, Any] | None = None
    """Filtre à appliquer avant calcul. Ex: {"column": "lifecycle", "value": "Churned"}
    ou {"column": "amount", "op": "gt", "value": 1000}.
    Opérateurs supportés: eq (default), ne, gt, gte, lt, lte, in."""

    group_by: str | None = None
    """Colonne pour group by (breakdowns)."""

    aggregation: str | None = None
    """Agrégation utilisée en breakdown/trend : sum, mean, count, count_distinct.
    Par défaut : count (cardinalité du groupe)."""

    time_column: str | None = None
    """Colonne datetime pour les tendances."""

    granularity: str | None = None
    """Granularité temporelle pour trend : day, week, month, quarter, year.
    Par défaut : month."""

    top_n: int | None = None
    """Nombre d'éléments à garder dans un top_n ou breakdown."""

    # === Métadonnées d'affichage ===

    unit: str | None = None
    """Unité d'affichage (ex: '%', '€', 'lignes')."""

    icon: str | None = None
    """Nom d'icône lucide-react pour la UI."""

    category: str = "general"
    """Catégorie pour le grouping UI : volume, average, range, quality,
    distribution, ratio, trend, breakdown."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KPIResult:
    """Résultat d'un calcul de KPI."""

    spec_id: str
    """L'id du spec utilisé pour ce calcul."""

    value: float | int | str
    """La valeur principale (formatée selon le type)."""

    raw_value: float | int | None
    """La valeur brute, sans formatage (utile pour comparaisons et charts en J13)."""

    formatted: str
    """Affichage prêt-à-afficher (ex: '1 234 €', '95,3 %')."""

    unit: str | None
    """Unité (héritée du spec)."""

    chart_type: str = "number"
    """Type de visualisation suggéré (number pour J11, bar/line en J12)."""

    metadata: dict[str, Any] | None = None
    """Infos additionnelles (ex: row_count utilisé, count_nulls, etc.)."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================
# Helpers de formatage
# ============================================================

def _format_number(value: float | int, unit: str | None = None) -> str:
    """Format un nombre proprement pour affichage français."""
    if value is None:
        return "—"

    if unit == "%":
        return f"{value:.1f} %".replace(".", ",")

    if isinstance(value, float):
        if abs(value) >= 1_000_000:
            return f"{value / 1_000_000:.2f} M".replace(".", ",")
        if abs(value) >= 1_000:
            # Séparateur de milliers : espace
            return f"{value:,.2f}".replace(",", " ").replace(".", ",")
        return f"{value:.2f}".replace(".", ",")

    # int
    if abs(value) >= 1_000:
        return f"{value:,}".replace(",", " ")
    return str(value)


def _ensure_column(df: pd.DataFrame, column: str) -> pd.Series:
    """Vérifie que la colonne existe, retourne la série, sinon lève."""
    if column not in df.columns:
        raise ValueError(f"Colonne introuvable : '{column}'")
    return df[column]


def _ensure_numeric(series: pd.Series, column: str) -> pd.Series:
    """Vérifie qu'une série est numérique (ou convertible)."""

    if pd.api.types.is_numeric_dtype(series):
        return series

    try:
        converted = pd.to_numeric(series, errors="coerce")

        # Cas normal : au moins une valeur numérique
        if converted.notna().any():
            return converted

        # Cas particulier : colonne entièrement vide
        if series.isna().all():
            return converted

    except Exception:
        pass

    raise ValueError(f"Colonne '{column}' n'est pas numérique")


# ============================================================
# Calculs individuels
# ============================================================

def calculate_count(df: pd.DataFrame, spec: KPISpec) -> KPIResult:
    """Nombre total de lignes du DataFrame."""
    value = int(len(df))
    return KPIResult(
        spec_id=spec.id,
        value=value,
        raw_value=value,
        formatted=_format_number(value, spec.unit),
        unit=spec.unit,
        metadata={"row_count": value},
    )


def calculate_count_distinct(df: pd.DataFrame, spec: KPISpec) -> KPIResult:
    """Nombre de valeurs distinctes (non-nulles) d'une colonne."""
    if spec.column is None:
        raise ValueError("count_distinct nécessite un nom de colonne")
    series = _ensure_column(df, spec.column)
    value = int(series.nunique(dropna=True))
    return KPIResult(
        spec_id=spec.id,
        value=value,
        raw_value=value,
        formatted=_format_number(value, spec.unit),
        unit=spec.unit,
        metadata={"null_count": int(series.isna().sum())},
    )


def calculate_sum(df: pd.DataFrame, spec: KPISpec) -> KPIResult:
    """Somme d'une colonne numérique."""
    if spec.column is None:
        raise ValueError("sum nécessite un nom de colonne")
    series = _ensure_numeric(_ensure_column(df, spec.column), spec.column)
    raw = float(series.sum(skipna=True))
    return KPIResult(
        spec_id=spec.id,
        value=raw,
        raw_value=raw,
        formatted=_format_number(raw, spec.unit),
        unit=spec.unit,
        metadata={"used_rows": int(series.notna().sum())},
    )


def calculate_mean(df: pd.DataFrame, spec: KPISpec) -> KPIResult:
    """Moyenne d'une colonne numérique."""
    if spec.column is None:
        raise ValueError("mean nécessite un nom de colonne")
    series = _ensure_numeric(_ensure_column(df, spec.column), spec.column)
    if series.notna().sum() == 0:
        raw = None
    else:
        raw = round(float(series.mean(skipna=True)), 2)
    return KPIResult(
        spec_id=spec.id,
        value=raw if raw is not None else "—",
        raw_value=raw,
        formatted=_format_number(raw, spec.unit) if raw is not None else "—",
        unit=spec.unit,
    )


def calculate_median(df: pd.DataFrame, spec: KPISpec) -> KPIResult:
    """Médiane d'une colonne numérique."""
    if spec.column is None:
        raise ValueError("median nécessite un nom de colonne")
    series = _ensure_numeric(_ensure_column(df, spec.column), spec.column)
    if series.notna().sum() == 0:
        raw = None
    else:
        raw = round(float(series.median(skipna=True)), 2)
    return KPIResult(
        spec_id=spec.id,
        value=raw if raw is not None else "—",
        raw_value=raw,
        formatted=_format_number(raw, spec.unit) if raw is not None else "—",
        unit=spec.unit,
    )


def calculate_min(df: pd.DataFrame, spec: KPISpec) -> KPIResult:
    """Valeur minimale d'une colonne numérique."""
    if spec.column is None:
        raise ValueError("min nécessite un nom de colonne")
    series = _ensure_numeric(_ensure_column(df, spec.column), spec.column)
    if series.notna().sum() == 0:
        raw = None
    else:
        raw = float(series.min(skipna=True))
    return KPIResult(
        spec_id=spec.id,
        value=raw if raw is not None else "—",
        raw_value=raw,
        formatted=_format_number(raw, spec.unit) if raw is not None else "—",
        unit=spec.unit,
    )


def calculate_max(df: pd.DataFrame, spec: KPISpec) -> KPIResult:
    """Valeur maximale d'une colonne numérique."""
    if spec.column is None:
        raise ValueError("max nécessite un nom de colonne")
    series = _ensure_numeric(_ensure_column(df, spec.column), spec.column)
    if series.notna().sum() == 0:
        raw = None
    else:
        raw = float(series.max(skipna=True))
    return KPIResult(
        spec_id=spec.id,
        value=raw if raw is not None else "—",
        raw_value=raw,
        formatted=_format_number(raw, spec.unit) if raw is not None else "—",
        unit=spec.unit,
    )


def calculate_nonnull_rate(df: pd.DataFrame, spec: KPISpec) -> KPIResult:
    """Taux de complétude (% de valeurs non-nulles) d'une colonne."""
    if spec.column is None:
        raise ValueError("nonnull_rate nécessite un nom de colonne")
    series = _ensure_column(df, spec.column)
    if len(series) == 0:
        raw = 0.0
    else:
        raw = round(float(series.notna().sum() / len(series)) * 100, 1)
    return KPIResult(
        spec_id=spec.id,
        value=raw,
        raw_value=raw,
        formatted=_format_number(raw, "%"),
        unit="%",
        metadata={
            "total": int(len(series)),
            "non_null": int(series.notna().sum()),
        },
    )


def calculate_true_rate(df: pd.DataFrame, spec: KPISpec) -> KPIResult:
    """Taux de 'true' sur une colonne booléenne (ou booléen-like)."""
    if spec.column is None:
        raise ValueError("true_rate nécessite un nom de colonne")
    series = _ensure_column(df, spec.column).dropna()
    if len(series) == 0:
        raw = 0.0
    else:
        # Normalise les valeurs vrai/faux
        true_set = {True, "1", "true", "True", "yes", "oui", "Y", "O"}
        true_count = sum(1 for v in series if v in true_set)
        raw = round(true_count / len(series) * 100, 1)
    return KPIResult(
        spec_id=spec.id,
        value=raw,
        raw_value=raw,
        formatted=_format_number(raw, "%"),
        unit="%",
        metadata={"sample_size": int(len(series))},
    )

# ============================================================
# Helpers pour les calculs complexes (J12)
# ============================================================

def _apply_filter(df: pd.DataFrame, filter_spec: dict[str, Any]) -> pd.DataFrame:
    """
    Applique un filtre au DataFrame.

    Format du filter_spec :
        {"column": "name", "op": "eq", "value": "X"}
        {"column": "amount", "op": "gt", "value": 100}
        {"column": "status", "op": "in", "value": ["paid", "pending"]}
        {"column": "produit", "op": "startswith", "value": "C"}

    Opérateurs supportés : eq (default), ne, gt, gte, lt, lte, in,
    startswith, contains (ces 2 derniers insensibles à la casse, sur
    colonnes texte — NEW J46, pour compute_from_dataset).
    """
    column = filter_spec.get("column")
    if not column:
        raise ValueError("filter sans 'column'")
    if column not in df.columns:
        raise ValueError(f"Colonne du filtre introuvable : '{column}'")

    op = filter_spec.get("op", "eq")
    value = filter_spec.get("value")

    series = df[column]
    if op == "eq":
        mask = series == value
    elif op == "ne":
        mask = series != value
    elif op == "gt":
        mask = series > value
    elif op == "gte":
        mask = series >= value
    elif op == "lt":
        mask = series < value
    elif op == "lte":
        mask = series <= value
    elif op == "in":
        if not isinstance(value, list):
            raise ValueError("'in' attend une liste pour 'value'")
        mask = series.isin(value)
    elif op == "startswith":
        mask = series.astype(str).str.lower().str.startswith(str(value).lower())
    elif op == "contains":
        mask = series.astype(str).str.lower().str.contains(str(value).lower(), regex=False)
    else:
        raise ValueError(f"Opérateur de filtre non supporté : '{op}'")

    return df[mask]


# ============================================================
# Calcul : ratio (% avec filtre)
# ============================================================

def calculate_ratio(df: pd.DataFrame, spec: KPISpec) -> KPIResult:
    """
    Calcule un ratio : nombre de lignes respectant le filtre / nombre total de lignes.
    Retourne un pourcentage entre 0 et 100.

    Exemple : spec.filter = {"column": "lifecycle_stage", "value": "Churned"}
              → retourne le % de clients churned.
    """
    if spec.filter is None:
        raise ValueError("ratio nécessite un 'filter'")

    total = len(df)
    if total == 0:
        return KPIResult(
            spec_id=spec.id,
            value=0.0,
            raw_value=0.0,
            formatted="—",
            unit="%",
            chart_type="number",
            metadata={"total": 0, "matched": 0},
        )

    filtered = _apply_filter(df, spec.filter)
    matched = len(filtered)
    raw = round(matched / total * 100, 1)

    return KPIResult(
        spec_id=spec.id,
        value=raw,
        raw_value=raw,
        formatted=_format_number(raw, "%"),
        unit="%",
        chart_type="number",
        metadata={
            "total": int(total),
            "matched": int(matched),
            "filter": spec.filter,
        },
    )
    # ============================================================
# Calcul : breakdown (group by)
# ============================================================

def calculate_breakdown(df: pd.DataFrame, spec: KPISpec) -> KPIResult:
    """
    Décompose une métrique par catégorie (group by).

    Exemples :
        spec.group_by="region", spec.aggregation="count"
            → nombre de lignes par région

        spec.group_by="segment", spec.column="amount", spec.aggregation="sum"
            → somme des amounts par segment

        spec.group_by="industry", spec.column="nps", spec.aggregation="mean"
            → moyenne du NPS par industrie

    Le résultat est trié décroissant et plafonné à top_n si défini (par défaut 10).
    """
    if not spec.group_by:
        raise ValueError("breakdown nécessite 'group_by'")
    if spec.group_by not in df.columns:
        raise ValueError(f"Colonne group_by introuvable : '{spec.group_by}'")

    agg = spec.aggregation or "count"
    limit = spec.top_n or 10

    grouped = df.groupby(spec.group_by, dropna=True)

    if agg == "count":
        series = grouped.size()
    elif agg == "count_distinct":
        if not spec.column:
            raise ValueError("count_distinct nécessite 'column'")
        series = grouped[spec.column].nunique()
    elif agg in ("sum", "mean", "median", "min", "max"):
        if not spec.column:
            raise ValueError(f"{agg} nécessite 'column'")
        if spec.column not in df.columns:
            raise ValueError(f"Colonne introuvable : '{spec.column}'")
        numeric_series = _ensure_numeric(df[spec.column], spec.column)
        # On regroupe sur la colonne numérique convertie
        series = df.assign(_v=numeric_series).groupby(spec.group_by)["_v"].agg(agg)
    else:
        raise ValueError(f"Agrégation non supportée pour breakdown : '{agg}'")

    # Trier décroissant, prendre top_n
    series = series.sort_values(ascending=False).head(limit)

    # Conversion en dict JSON-safe (clés en string, valeurs en float)
    breakdown_data = {
        str(k): float(v) if pd.notna(v) else 0.0
        for k, v in series.items()
    }
    total = float(series.sum())

    return KPIResult(
        spec_id=spec.id,
        value=total,
        raw_value=total,
        formatted=_format_number(total, spec.unit),
        unit=spec.unit,
        chart_type="bar",  # ← prêt pour un bar chart en J13
        metadata={
            "group_by": spec.group_by,
            "aggregation": agg,
            "breakdown": breakdown_data,
            "categories_count": len(series),
        },
    )
    # ============================================================
# Calcul : trend (séries temporelles)
# ============================================================

# Mapping de la granularité vers les fréquences pandas
_GRANULARITY_MAP = {
    "day": "D",
    "week": "W",
    "month": "ME",       # Month End (recommandé en pandas récent)
    "quarter": "QE",     # Quarter End
    "year": "YE",        # Year End
}


def calculate_trend(df: pd.DataFrame, spec: KPISpec) -> KPIResult:
    """
    Calcule une évolution temporelle.

    Exemples :
        spec.time_column="acquisition_date", spec.granularity="month",
        spec.aggregation="count"
            → nombre de lignes par mois

        spec.time_column="transaction_date", spec.column="amount",
        spec.aggregation="sum", spec.granularity="quarter"
            → somme des amounts par trimestre
    """
    if not spec.time_column:
        raise ValueError("trend nécessite 'time_column'")
    if spec.time_column not in df.columns:
        raise ValueError(f"Colonne temporelle introuvable : '{spec.time_column}'")

    granularity = spec.granularity or "month"
    if granularity not in _GRANULARITY_MAP:
        raise ValueError(
            f"Granularité non supportée : '{granularity}'. "
            f"Valeurs : {list(_GRANULARITY_MAP.keys())}"
        )
    freq = _GRANULARITY_MAP[granularity]

    # Parser la colonne temporelle
    try:
        df = df.copy()
        df[spec.time_column] = pd.to_datetime(df[spec.time_column], errors="coerce")
    except Exception as e:
        raise ValueError(f"Impossible de parser '{spec.time_column}' en date : {e}") from e

    df = df.dropna(subset=[spec.time_column])
    if df.empty:
        return KPIResult(
            spec_id=spec.id,
            value=0,
            raw_value=0,
            formatted="—",
            unit=spec.unit,
            chart_type="line",
            metadata={"points": []},
        )

    agg = spec.aggregation or "count"

    # Resample selon la granularité choisie
    resampled = df.set_index(spec.time_column).resample(freq)

    if agg == "count":
        series = resampled.size()
    elif agg == "count_distinct":
        if not spec.column:
            raise ValueError("count_distinct nécessite 'column'")
        series = resampled[spec.column].nunique()
    elif agg in ("sum", "mean", "median", "min", "max"):
        if not spec.column:
            raise ValueError(f"{agg} nécessite 'column'")
        if spec.column not in df.columns:
            raise ValueError(f"Colonne introuvable : '{spec.column}'")
        numeric = _ensure_numeric(df[spec.column], spec.column)
        df2 = df.assign(_v=numeric)
        series = df2.set_index(spec.time_column).resample(freq)["_v"].agg(agg)
    else:
        raise ValueError(f"Agrégation non supportée pour trend : '{agg}'")

    # Conversion en liste de points (label, value) JSON-safe
    points = [
        {
            "label": ts.strftime("%Y-%m-%d"),
            "value": float(v) if pd.notna(v) else 0.0,
        }
        for ts, v in series.items()
    ]

    total = float(series.sum(skipna=True))

    return KPIResult(
        spec_id=spec.id,
        value=total,
        raw_value=total,
        formatted=_format_number(total, spec.unit),
        unit=spec.unit,
        chart_type="line",
        metadata={
            "time_column": spec.time_column,
            "granularity": granularity,
            "aggregation": agg,
            "points": points,
            "points_count": len(points),
        },
    )
# ============================================================
# Dispatcher : choisit la bonne fonction selon le type du spec
# ============================================================

CALCULATORS = {
    "count": calculate_count,
    "count_distinct": calculate_count_distinct,
    "sum": calculate_sum,
    "mean": calculate_mean,
    "median": calculate_median,
    "min": calculate_min,
    "max": calculate_max,
    "nonnull_rate": calculate_nonnull_rate,
    "true_rate": calculate_true_rate,
    "ratio": calculate_ratio,
    "breakdown": calculate_breakdown,
    "trend": calculate_trend,
}


def calculate_kpi(df: pd.DataFrame, spec: KPISpec) -> KPIResult:
    """
    Point d'entrée unique : calcule le KPI décrit par le spec sur le DataFrame.
    Lève ValueError si le type est inconnu ou si les arguments sont invalides.
    """
    calculator = CALCULATORS.get(spec.type)
    if calculator is None:
        raise ValueError(
            f"Type de KPI non supporté en J11 : '{spec.type}'. "
            f"Types disponibles : {sorted(CALCULATORS.keys())}"
        )
    return calculator(df, spec)
