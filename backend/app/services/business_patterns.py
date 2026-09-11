"""
Bibliothèque de patterns business classiques.

Chaque pattern décrit un KPI métier réutilisable : un nom, une description,
une heuristique pour détecter s'il est applicable à un dataset donné, et
une fonction qui produit le KPISpec correspondant.

Ce module rend Vector "expert" en métriques business : il reconnaît
automatiquement les colonnes pertinentes et propose les KPIs classiques
du domaine identifié (CRM, marketing, sales, finance...).
"""
from collections.abc import Callable
from dataclasses import dataclass

from app.db.models.dataset import DatasetColumn
from app.services.kpi_calculator import KPISpec


# Helper : trouve la première colonne dont le nom contient un des mots-clés,
# et dont le dtype matche optionnellement.
def _find_column(
    columns: list[DatasetColumn],
    keywords: list[str],
    dtype: str | None = None,
) -> DatasetColumn | None:
    """Retourne la première colonne dont le nom (lower) contient un des keywords."""
    for col in columns:
        if dtype and col.dtype != dtype:
            continue
        col_name_lower = col.name.lower()
        for kw in keywords:
            if kw in col_name_lower:
                return col
    return None


def _find_value_in_column(
    columns: list[DatasetColumn],
    col_name: str,
    candidates: list[str],
) -> str | None:
    """Cherche une des valeurs candidates dans les sample_values d'une colonne."""
    target_col = next((c for c in columns if c.name == col_name), None)
    if not target_col or not target_col.sample_values:
        return None

    samples = target_col.sample_values.get("samples", [])
    top_values = (target_col.sample_values.get("stats") or {}).get("top_values", {})
    all_observed = {str(s).lower() for s in samples} | {
        str(k).lower() for k in top_values.keys()
    }

    for candidate in candidates:
        if candidate.lower() in all_observed:
            # On retourne la valeur d'origine, pas la version lower
            for s in samples:
                if str(s).lower() == candidate.lower():
                    return s
            for k in top_values.keys():
                if str(k).lower() == candidate.lower():
                    return k
    return None


@dataclass
class BusinessPattern:
    """Définition d'un pattern business réutilisable."""

    code: str
    name: str
    description: str
    domain: str  # crm | marketing | sales | finance | hr | ecommerce | generic
    detector: Callable[[list[DatasetColumn]], bool]
    builder: Callable[[list[DatasetColumn]], KPISpec | None]


# ============================================================
# Patterns CRM
# ============================================================

def _detect_churn_rate(columns: list[DatasetColumn]) -> bool:
    lifecycle = _find_column(columns, ["lifecycle", "status", "stage"], "categorical")
    if not lifecycle:
        return False
    return _find_value_in_column(columns, lifecycle.name, ["churned", "lost", "perdu", "inactif"]) is not None


def _build_churn_rate(columns: list[DatasetColumn]) -> KPISpec | None:
    lifecycle = _find_column(columns, ["lifecycle", "status", "stage"], "categorical")
    if not lifecycle:
        return None
    churned_value = _find_value_in_column(columns, lifecycle.name, ["churned", "lost", "perdu", "inactif"])
    if not churned_value:
        return None
    return KPISpec(
        id="pattern_churn_rate",
        title="Taux de churn",
        description=f"Pourcentage de clients avec un statut '{churned_value}'",
        type="ratio",
        filter={"column": lifecycle.name, "value": churned_value},
        unit="%",
        icon="TrendingDown",
        category="ratio",
    )


def _detect_nps(columns: list[DatasetColumn]) -> bool:
    return _find_column(columns, ["nps", "satisfaction", "score_satisfaction"], "numeric") is not None


def _build_nps(columns: list[DatasetColumn]) -> KPISpec | None:
    nps_col = _find_column(columns, ["nps", "satisfaction"], "numeric")
    if not nps_col:
        return None
    return KPISpec(
        id="pattern_nps_avg",
        title="NPS moyen",
        description=f"Score de satisfaction moyen ({nps_col.name})",
        type="mean",
        column=nps_col.name,
        icon="Star",
        category="average",
    )


def _detect_segment_breakdown(columns: list[DatasetColumn]) -> bool:
    return _find_column(columns, ["segment", "tier"], "categorical") is not None


def _build_segment_breakdown(columns: list[DatasetColumn]) -> KPISpec | None:
    segment = _find_column(columns, ["segment", "tier"], "categorical")
    if not segment:
        return None
    return KPISpec(
        id="pattern_clients_by_segment",
        title=f"Clients par {segment.name}",
        description=f"Répartition du nombre de clients selon {segment.name}",
        type="breakdown",
        group_by=segment.name,
        aggregation="count",
        icon="PieChart",
        category="breakdown",
    )


# ============================================================
# Patterns Sales / Finance
# ============================================================

def _detect_revenue_trend(columns: list[DatasetColumn]) -> bool:
    has_amount = _find_column(columns, ["amount", "montant", "revenue", "revenu", "price", "prix"], "numeric") is not None
    has_date = any(c.dtype == "datetime" for c in columns)
    return has_amount and has_date


def _build_revenue_trend(columns: list[DatasetColumn]) -> KPISpec | None:
    amount_col = _find_column(columns, ["amount", "montant", "revenue", "revenu", "price", "prix"], "numeric")
    date_col = next((c for c in columns if c.dtype == "datetime" and c.is_date_main), None)
    if not date_col:
        date_col = next((c for c in columns if c.dtype == "datetime"), None)
    if not amount_col or not date_col:
        return None
    return KPISpec(
        id="pattern_revenue_monthly",
        title="Évolution mensuelle des montants",
        description=f"Somme de {amount_col.name} par mois sur {date_col.name}",
        type="trend",
        time_column=date_col.name,
        column=amount_col.name,
        aggregation="sum",
        granularity="month",
        unit="€",
        icon="TrendingUp",
        category="trend",
    )


def _detect_top_categories(columns: list[DatasetColumn]) -> bool:
    has_amount = _find_column(columns, ["amount", "montant", "revenue", "price"], "numeric") is not None
    has_category = _find_column(columns, ["category", "categorie", "type", "product", "produit"], "categorical") is not None
    return has_amount and has_category


def _build_top_categories(columns: list[DatasetColumn]) -> KPISpec | None:
    amount_col = _find_column(columns, ["amount", "montant", "revenue", "price"], "numeric")
    cat_col = _find_column(columns, ["category", "categorie", "type", "product", "produit"], "categorical")
    if not amount_col or not cat_col:
        return None
    return KPISpec(
        id="pattern_top_categories",
        title=f"Top {cat_col.name} par {amount_col.name}",
        description=f"Catégories ({cat_col.name}) classées par somme de {amount_col.name}",
        type="breakdown",
        group_by=cat_col.name,
        column=amount_col.name,
        aggregation="sum",
        top_n=10,
        icon="BarChart",
        category="breakdown",
    )


# ============================================================
# Patterns Marketing
# ============================================================

def _detect_channel_breakdown(columns: list[DatasetColumn]) -> bool:
    return _find_column(columns, ["channel", "canal", "source"], "categorical") is not None


def _build_channel_breakdown(columns: list[DatasetColumn]) -> KPISpec | None:
    channel = _find_column(columns, ["channel", "canal", "source"], "categorical")
    if not channel:
        return None
    return KPISpec(
        id="pattern_channel_breakdown",
        title=f"Volume par {channel.name}",
        description="Répartition selon le canal d'origine",
        type="breakdown",
        group_by=channel.name,
        aggregation="count",
        icon="Radio",
        category="breakdown",
    )


# ============================================================
# Registre des patterns
# ============================================================

PATTERNS: list[BusinessPattern] = [
    # CRM
    BusinessPattern(
        code="churn_rate",
        name="Taux de churn",
        description="% de clients ayant churné",
        domain="crm",
        detector=_detect_churn_rate,
        builder=_build_churn_rate,
    ),
    BusinessPattern(
        code="nps_average",
        name="NPS moyen",
        description="Score de satisfaction moyen",
        domain="crm",
        detector=_detect_nps,
        builder=_build_nps,
    ),
    BusinessPattern(
        code="clients_by_segment",
        name="Clients par segment",
        description="Distribution des clients par segment commercial",
        domain="crm",
        detector=_detect_segment_breakdown,
        builder=_build_segment_breakdown,
    ),
    # Sales / Finance
    BusinessPattern(
        code="revenue_monthly",
        name="Évolution mensuelle du CA",
        description="Tendance du chiffre d'affaires par mois",
        domain="sales",
        detector=_detect_revenue_trend,
        builder=_build_revenue_trend,
    ),
    BusinessPattern(
        code="top_categories",
        name="Top catégories",
        description="Catégories les plus rentables",
        domain="sales",
        detector=_detect_top_categories,
        builder=_build_top_categories,
    ),
    # Marketing
    BusinessPattern(
        code="channel_breakdown",
        name="Répartition par canal",
        description="Distribution par canal d'acquisition",
        domain="marketing",
        detector=_detect_channel_breakdown,
        builder=_build_channel_breakdown,
    ),
]


def detect_applicable_patterns(
    columns: list[DatasetColumn],
) -> list[KPISpec]:
    """
    Pour chaque pattern de la bibliothèque, teste s'il est applicable
    au dataset (selon les colonnes profilées). Retourne la liste des
    KPISpecs construits par les patterns applicables.
    """
    specs: list[KPISpec] = []
    for pattern in PATTERNS:
        try:
            if pattern.detector(columns):
                spec = pattern.builder(columns)
                if spec is not None:
                    specs.append(spec)
        except Exception:
            # Robustesse : un pattern qui plante ne fait pas échouer le tout
            continue
    return specs
