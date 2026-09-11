"""Calcul des donnees de widgets de dashboard personnalise (S5 J36).

Charge le CSV/Excel d'un dataset via pandas et calcule, pour un widget donne
(type + config), les donnees pretes a afficher cote frontend. Ne leve jamais
d'exception : toute erreur (colonne manquante, dataset illisible, etc.)
retourne {"error": "..."} pour que le frontend affiche un message propre
au lieu de planter tout le dashboard.
"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pandas as pd

from app.db.models.dataset import Dataset
from app.db.models.saved_dashboard import DashboardWidget
from app.services.storage import FileStorage

# Aggregat cote config (sum/avg/count/min/max) -> methode pandas groupby
AGG_FUNCS = {"sum": "sum", "avg": "mean", "count": "count", "min": "min", "max": "max"}


# ============================================================
# Chargement dataset (meme convention que DatasetService)
# ============================================================

def _load_dataset(dataset: Dataset, storage: FileStorage) -> pd.DataFrame:
    full_path = storage.get_full_path(dataset.file_path)
    ext = Path(dataset.original_filename).suffix.lower()
    if ext == ".csv":
        return pd.read_csv(full_path)
    return pd.read_excel(full_path)


# ============================================================
# Filtres (S5 J37)
# ============================================================

def _coerce_for_range(series: pd.Series) -> pd.Series:
    """Convertit une colonne pour comparaison gt/gte/lt/lte/between.

    Essaie numerique d'abord (cas le plus courant : slider min/max), puis
    date (cas date range picker). Si aucune conversion ne marche, renvoie
    la serie telle quelle (comparaison directe, ex: strings).
    """
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().any():
        return numeric
    dates = pd.to_datetime(series, errors="coerce")
    if dates.notna().any():
        return dates
    return series


def apply_filters(df: pd.DataFrame, filters: list[dict] | None) -> pd.DataFrame:
    """Applique les filtres au DataFrame avant computation du widget.

    Chaque filtre : {"column": str, "op": "eq"|"neq"|"gt"|"gte"|"lt"|"lte"|"in"|"between", "value": Any}.
    Un filtre sur une colonne absente ou avec une valeur invalide est ignore
    silencieusement (ne doit jamais faire planter le calcul du widget).
    """
    if not filters:
        return df

    for f in filters:
        col = f.get("column")
        op = f.get("op")
        value = f.get("value")

        if col not in df.columns:
            continue

        try:
            if op == "eq":
                df = df[df[col] == value]
            elif op == "neq":
                df = df[df[col] != value]
            elif op == "in":
                df = df[df[col].isin(value)]
            elif op in ("gt", "gte", "lt", "lte"):
                series = _coerce_for_range(df[col])
                bound = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
                if pd.isna(bound):
                    bound = pd.to_datetime(value, errors="coerce")
                comparator = {
                    "gt": series.gt, "gte": series.ge,
                    "lt": series.lt, "lte": series.le,
                }[op]
                df = df[comparator(bound).fillna(False)]
            elif op == "between":
                lo, hi = value[0], value[1]
                series = _coerce_for_range(df[col])
                lo_bound = pd.to_numeric(pd.Series([lo]), errors="coerce").iloc[0]
                hi_bound = pd.to_numeric(pd.Series([hi]), errors="coerce").iloc[0]
                if pd.isna(lo_bound):
                    lo_bound = pd.to_datetime(lo, errors="coerce")
                if pd.isna(hi_bound):
                    hi_bound = pd.to_datetime(hi, errors="coerce")
                df = df[series.between(lo_bound, hi_bound).fillna(False)]
        except Exception:
            continue

    return df


# ============================================================
# Helpers de serialisation JSON-safe
# ============================================================

def _label(v: Any) -> str:
    """Convertit une cle d'index (categorie, date...) en string affichable."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "N/A"
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    return str(v)


def _num(v: Any) -> float:
    """Convertit une valeur pandas/numpy en float Python JSON-safe (NaN -> 0.0)."""
    try:
        f = float(v)
        return 0.0 if pd.isna(f) else f
    except (TypeError, ValueError):
        return 0.0


def _jsonable(v: Any):
    """Convertit une cellule de data_table en valeur JSON-safe (nombre ou string)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, int | float):
        return _num(v)
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    return str(v)


def _require_columns(df: pd.DataFrame, cols: list[str]) -> str | None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        return f"Colonne(s) introuvable(s) : {', '.join(missing)}"
    return None


# ============================================================
# Dispatcher principal
# ============================================================

def compute_widget_data(
    widget: DashboardWidget,
    dataset: Dataset,
    storage: FileStorage,
    filters: list[dict] | None = None,
) -> dict[str, Any]:
    """Calcule les donnees a afficher pour un widget.

    Retourne un dict dont la forme depend du widget_type (voir les fonctions
    _compute_* ci-dessous), ou {"error": "..."} en cas de probleme.
    """
    try:
        df = _load_dataset(dataset, storage)
    except Exception as e:
        return {"error": f"Impossible de charger le dataset : {e}"}

    df = apply_filters(df, filters)

    dispatch = {
        "kpi": _compute_kpi,
        "bar_chart": _compute_bar_chart,
        "line_chart": _compute_line_chart,
        "pie_chart": _compute_pie_chart,
        "donut_chart": _compute_pie_chart,
        "data_table": _compute_data_table,
        "radar_chart": _compute_radar_chart,
        "scatter_plot": _compute_scatter_plot,
        "heatmap": _compute_heatmap,
        "correlation_matrix": _compute_correlation_matrix,
        "histogram": _compute_histogram,
    }

    fn = dispatch.get(widget.widget_type)
    if fn is None:
        return {"error": f"Type de widget non supporté : {widget.widget_type}"}

    try:
        return fn(df, widget.config)
    except Exception as e:
        return {"error": f"Erreur de calcul : {e}"}


# ============================================================
# KPI
# ============================================================

def _compute_kpi(df: pd.DataFrame, cfg: dict) -> dict:
    col = cfg.get("column")
    agg = cfg.get("aggregate", "sum")
    if col not in df.columns:
        return {"error": f"Colonne '{col}' introuvable"}

    s = pd.to_numeric(df[col], errors="coerce").dropna()
    if s.empty:
        return {"error": f"Aucune valeur numérique dans '{col}'"}

    value = {
        "sum": s.sum,
        "avg": s.mean,
        "count": lambda: len(s),
        "min": s.min,
        "max": s.max,
    }.get(agg, s.sum)()

    return {"value": float(value), "trend": None}


# ============================================================
# Bar / Line chart
# ============================================================

# Noms de mois (FR/EN, abreges et complets) -> numero, pour trier
# chronologiquement un axe X qui contient des noms de mois en texte plutot
# qu'une vraie date (ex: colonne "month" avec des valeurs "Jan"/"Feb"/"Mar").
_MONTH_ORDER = {
    "jan": 1, "january": 1, "janv": 1, "janvier": 1,
    "feb": 2, "february": 2, "fev": 2, "fevr": 2, "février": 2,
    "mar": 3, "march": 3, "mars": 3,
    "apr": 4, "april": 4, "avr": 4, "avril": 4,
    "may": 5, "mai": 5,
    "jun": 6, "june": 6, "juin": 6,
    "jul": 7, "july": 7, "juil": 7, "juillet": 7,
    "aug": 8, "august": 8, "aout": 8, "août": 8,
    "sep": 9, "sept": 9, "september": 9, "septembre": 9,
    "oct": 10, "october": 10, "octobre": 10,
    "nov": 11, "november": 11, "novembre": 11,
    "dec": 12, "december": 12, "decembre": 12, "décembre": 12,
}


def _chronological_order(df: pd.DataFrame, x_column: str) -> list | None:
    """Determine l'ordre chronologique des valeurs d'une colonne X pour un
    line_chart, quand ce n'est pas une vraie colonne date.

    Essaie d'abord un parsing datetime (colonne deja au format date), puis
    un mapping de noms de mois (FR/EN). Retourne None si aucune des deux
    heuristiques ne s'applique a au moins 80% des valeurs -> l'appelant
    garde alors l'ordre alphabetique par defaut de groupby.
    """
    series = df[x_column]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        dates = pd.to_datetime(series, errors="coerce")
    if dates.notna().mean() > 0.8:
        sort_key = dates
    else:
        normalized = series.astype(str).str.strip().str.lower()
        month_keys = normalized.map(_MONTH_ORDER)
        if month_keys.notna().mean() > 0.8:
            sort_key = month_keys
        else:
            return None

    ordered = (
        df.assign(__sort_key__=sort_key)
        .dropna(subset=["__sort_key__"])
        .drop_duplicates(subset=[x_column])
        .sort_values("__sort_key__")[x_column]
    )
    return ordered.tolist()


def _compute_bar_chart(df: pd.DataFrame, cfg: dict, order: list | None = None) -> dict:
    x = cfg.get("x_column")
    y = cfg.get("y_column")
    gb = cfg.get("groupby")
    agg = cfg.get("aggregate", "sum")

    err = _require_columns(df, [c for c in [x, y, gb] if c])
    if err:
        return {"error": err}

    agg_func = AGG_FUNCS.get(agg, "sum")

    if gb:
        grouped = df.groupby([x, gb])[y].agg(agg_func).unstack(fill_value=0)
        if order:
            grouped = grouped.reindex([v for v in order if v in grouped.index])
        return {
            "labels": [_label(v) for v in grouped.index],
            "series": [
                {"name": _label(col), "data": [_num(v) for v in grouped[col]]}
                for col in grouped.columns
            ],
        }

    grouped = df.groupby(x)[y].agg(agg_func)
    if order:
        grouped = grouped.reindex([v for v in order if v in grouped.index])
    return {
        "labels": [_label(v) for v in grouped.index],
        "values": [_num(v) for v in grouped.values],
    }


def _compute_line_chart(df: pd.DataFrame, cfg: dict) -> dict:
    x = cfg.get("x_column")
    order = _chronological_order(df, x) if x in df.columns else None
    return _compute_bar_chart(df, cfg, order=order)


# ============================================================
# Pie / Donut chart
# ============================================================

def _compute_pie_chart(df: pd.DataFrame, cfg: dict) -> dict:
    cat = cfg.get("category_column")
    val = cfg.get("value_column")
    agg = cfg.get("aggregate", "sum")

    err = _require_columns(df, [cat, val])
    if err:
        return {"error": err}

    agg_func = AGG_FUNCS.get(agg, "sum")
    grouped = df.groupby(cat)[val].agg(agg_func).sort_values(ascending=False)
    total = float(grouped.sum()) if len(grouped) else 0.0

    return {
        "labels": [_label(v) for v in grouped.index],
        "values": [_num(v) for v in grouped.values],
        "total": total,
        "percentages": [
            round(_num(v) / total * 100, 1) if total else 0.0
            for v in grouped.values
        ],
    }


# ============================================================
# Data table
# ============================================================

def _compute_data_table(df: pd.DataFrame, cfg: dict) -> dict:
    cols = cfg.get("columns", [])
    limit = cfg.get("limit", 20)
    sort_by = cfg.get("sort_by")
    sort_order = cfg.get("sort_order", "asc")

    cols_ok = [c for c in cols if c in df.columns]
    if not cols_ok:
        return {"error": "Aucune colonne valide"}

    subset = df[cols_ok]
    if sort_by and sort_by in subset.columns:
        subset = subset.sort_values(sort_by, ascending=(sort_order == "asc"))
    subset = subset.head(limit)

    rows = [[_jsonable(v) for v in row] for row in subset.itertuples(index=False)]

    return {"columns": cols_ok, "rows": rows}


# ============================================================
# Radar chart
# ============================================================

def _compute_radar_chart(df: pd.DataFrame, cfg: dict) -> dict:
    cat = cfg.get("category_column")
    metrics = cfg.get("metric_columns", [])
    agg = cfg.get("aggregate", "avg")

    if cat not in df.columns:
        return {"error": f"Colonne '{cat}' introuvable"}
    metrics_ok = [m for m in metrics if m in df.columns]
    if not metrics_ok:
        return {"error": "Aucune colonne métrique valide"}

    agg_func = AGG_FUNCS.get(agg, "mean")
    numeric_df = df[metrics_ok].apply(pd.to_numeric, errors="coerce")
    grouped = numeric_df.groupby(df[cat]).agg(agg_func)

    # Normalise chaque metrique sur 0-100 pour homogeneite visuelle.
    # rng.replace(0, 1) evite une division par zero quand une metrique
    # est constante (max == min) sur toutes les categories.
    rng = (grouped.max() - grouped.min()).replace(0, 1)
    normalized = ((grouped - grouped.min()) / rng * 100).fillna(0)

    return {
        "axes": metrics_ok,
        "series": [
            {"name": _label(idx), "values": [_num(v) for v in normalized.loc[idx]]}
            for idx in normalized.index
        ],
    }


# ============================================================
# Scatter plot
# ============================================================

def _compute_scatter_plot(df: pd.DataFrame, cfg: dict) -> dict:
    x = cfg.get("x_column")
    y = cfg.get("y_column")
    size = cfg.get("size_column")
    color = cfg.get("color_column")

    err = _require_columns(df, [x, y])
    if err:
        return {"error": err}

    df_work = df.copy()
    df_work[x] = pd.to_numeric(df_work[x], errors="coerce")
    df_work[y] = pd.to_numeric(df_work[y], errors="coerce")
    df_clean = df_work.dropna(subset=[x, y])

    if len(df_clean) > 500:
        df_clean = df_clean.sample(n=500, random_state=42)

    has_size = bool(size and size in df.columns)
    has_color = bool(color and color in df.columns)

    points = []
    for idx, row in df_clean.iterrows():
        point: dict[str, Any] = {"x": _num(row[x]), "y": _num(row[y])}
        if has_size:
            s_val = pd.to_numeric(df.loc[idx, size], errors="coerce")
            if pd.notna(s_val):
                point["size"] = float(s_val)
        if has_color:
            point["color"] = _label(df.loc[idx, color])
        points.append(point)

    return {
        "points": points,
        "x_label": x,
        "y_label": y,
        "has_size": has_size,
        "has_color": has_color,
    }


# ============================================================
# Heatmap
# ============================================================

def _compute_heatmap(df: pd.DataFrame, cfg: dict) -> dict:
    row_col = cfg.get("row_column")
    col_col = cfg.get("col_column")
    val_col = cfg.get("value_column")
    agg = cfg.get("aggregate", "sum")

    err = _require_columns(df, [row_col, col_col, val_col])
    if err:
        return {"error": err}

    agg_func = AGG_FUNCS.get(agg, "sum")
    pivot = df.groupby([row_col, col_col])[val_col].agg(agg_func).unstack(fill_value=0)

    if pivot.empty:
        return {"error": "Aucune donnée après regroupement"}

    values = [[_num(v) for v in row] for row in pivot.values]
    flat = [v for row in values for v in row]

    return {
        "rows": [_label(v) for v in pivot.index],
        "cols": [_label(v) for v in pivot.columns],
        "values": values,
        "min": min(flat) if flat else 0.0,
        "max": max(flat) if flat else 0.0,
        "color_scale": cfg.get("color_scale", "emerald"),
    }


# ============================================================
# Correlation matrix (S5 J37, integre des maintenant)
# ============================================================

def _compute_correlation_matrix(df: pd.DataFrame, cfg: dict) -> dict:
    cols = cfg.get("columns", [])
    method = cfg.get("method", "pearson")

    numeric_cols = []
    for c in cols:
        if c in df.columns:
            coerced = pd.to_numeric(df[c], errors="coerce")
            if coerced.notna().any():
                numeric_cols.append(c)

    if len(numeric_cols) < 2:
        return {"error": "Au moins 2 colonnes numériques nécessaires"}

    numeric_df = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    corr = numeric_df.corr(method=method).round(2)
    matrix = [[_num(v) for v in row] for row in corr.values]

    return {"columns": numeric_cols, "matrix": matrix, "method": method}


# ============================================================
# Histogram (S5 J37, integre des maintenant)
# ============================================================

def _compute_histogram(df: pd.DataFrame, cfg: dict) -> dict:
    col = cfg.get("column")
    bin_count = cfg.get("bin_count") or 20

    if col not in df.columns:
        return {"error": f"Colonne '{col}' introuvable"}

    s = pd.to_numeric(df[col], errors="coerce").dropna()
    if s.empty:
        return {"error": f"Aucune valeur numérique dans '{col}'"}

    binned, bin_edges = pd.cut(s, bins=bin_count, retbins=True, duplicates="drop")
    counts = binned.value_counts().sort_index()

    bin_labels = [
        f"{bin_edges[i]:.1f}-{bin_edges[i + 1]:.1f}"
        for i in range(len(bin_edges) - 1)
    ]

    return {
        "bins": bin_labels,
        "counts": [int(c) for c in counts.values],
        "mean": float(s.mean()) if cfg.get("show_mean") else None,
        "median": float(s.median()) if cfg.get("show_median") else None,
    }
