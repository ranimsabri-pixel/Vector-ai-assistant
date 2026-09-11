"""
Générateur automatique de KPIs depuis un dataset profilé.

Stratégie : règles déterministes par type de colonne. Aucun appel LLM.
Garantit la rapidité (sub-seconde) et l'indépendance vis-à-vis de l'API IA.

Pour chaque colonne du dataset, on génère 0 à 3 KPIs "évidents" selon
le dtype détecté. On plafonne à 15 KPIs total pour ne pas
surcharger l'utilisateur.
"""

from app.db.models.dataset import DatasetColumn
from app.services.kpi_calculator import KPISpec

# Cap pour éviter de noyer l'utilisateur sous les KPIs
MAX_KPIS = 15

# Seuil au-delà duquel on génère un KPI "qualité" sur une colonne (taux de nulls)
HIGH_NULL_THRESHOLD = 0.05  # 5%


def _slugify(name: str) -> str:
    """Convertit un nom de colonne en identifiant sûr pour les URLs."""
    safe = "".join(c if c.isalnum() else "_" for c in name.lower())
    # Compacte les underscores multiples
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_")


# ============================================================
# Générateurs spécialisés par type
# ============================================================

def _global_kpis() -> list[KPISpec]:
    """KPIs qui ne dépendent pas d'une colonne particulière."""
    return [
        KPISpec(
            id="global_count",
            title="Nombre total d'enregistrements",
            description="Volume total de lignes dans le dataset",
            type="count",
            unit="lignes",
            icon="Database",
            category="volume",
        ),
    ]


def _numeric_kpis(col: DatasetColumn) -> list[KPISpec]:
    """KPIs sur une colonne numérique : moyenne, max, min."""
    slug = _slugify(col.name)
    return [
        KPISpec(
            id=f"mean_{slug}",
            title=f"Moyenne de {col.name}",
            description=f"Valeur moyenne observée sur la colonne {col.name}",
            type="mean",
            column=col.name,
            icon="TrendingUp",
            category="average",
        ),
        KPISpec(
            id=f"max_{slug}",
            title=f"Maximum de {col.name}",
            description=f"Plus grande valeur observée pour {col.name}",
            type="max",
            column=col.name,
            icon="ArrowUp",
            category="range",
        ),
        KPISpec(
            id=f"min_{slug}",
            title=f"Minimum de {col.name}",
            description=f"Plus petite valeur observée pour {col.name}",
            type="min",
            column=col.name,
            icon="ArrowDown",
            category="range",
        ),
    ]


def _categorical_kpis(col: DatasetColumn) -> list[KPISpec]:
    """KPIs sur une colonne catégorielle : nombre de valeurs distinctes."""
    slug = _slugify(col.name)
    return [
        KPISpec(
            id=f"distinct_{slug}",
            title=f"Catégories distinctes ({col.name})",
            description=f"Nombre de valeurs uniques pour {col.name}",
            type="count_distinct",
            column=col.name,
            unit="catégories",
            icon="Tags",
            category="distribution",
        ),
    ]


def _datetime_kpis(col: DatasetColumn) -> list[KPISpec]:
    """KPIs sur une colonne date : min et max."""
    slug = _slugify(col.name)
    return [
        KPISpec(
            id=f"min_date_{slug}",
            title=f"Date la plus ancienne ({col.name})",
            description=f"Plus petite date observée pour {col.name}",
            type="min",
            column=col.name,
            icon="Calendar",
            category="range",
        ),
        KPISpec(
            id=f"max_date_{slug}",
            title=f"Date la plus récente ({col.name})",
            description=f"Plus grande date observée pour {col.name}",
            type="max",
            column=col.name,
            icon="CalendarClock",
            category="range",
        ),
    ]


def _boolean_kpis(col: DatasetColumn) -> list[KPISpec]:
    """KPIs sur une colonne booléenne : taux de true."""
    slug = _slugify(col.name)
    return [
        KPISpec(
            id=f"true_rate_{slug}",
            title=f"Taux positif de {col.name}",
            description=f"Pourcentage de valeurs 'vrai' sur la colonne {col.name}",
            type="true_rate",
            column=col.name,
            unit="%",
            icon="CheckCircle",
            category="distribution",
        ),
    ]


def _quality_kpi(col: DatasetColumn, total_rows: int) -> KPISpec | None:
    """KPI qualité (taux de complétude) si la colonne a plus de 5% de nulls."""
    if total_rows == 0 or col.null_count is None:
        return None
    null_rate = col.null_count / total_rows
    if null_rate <= HIGH_NULL_THRESHOLD:
        return None
    slug = _slugify(col.name)
    return KPISpec(
        id=f"completeness_{slug}",
        title=f"Complétude de {col.name}",
        description=f"Pourcentage de valeurs renseignées (non-nulles) pour {col.name}",
        type="nonnull_rate",
        column=col.name,
        unit="%",
        icon="AlertCircle",
        category="quality",
    )


# ============================================================
# Orchestrateur principal
# ============================================================

# Routeur dtype → fonction de génération
_GENERATORS = {
    "numeric": _numeric_kpis,
    "categorical": _categorical_kpis,
    "datetime": _datetime_kpis,
    "boolean": _boolean_kpis,
}


def generate_kpis(columns: list[DatasetColumn], total_rows: int) -> list[KPISpec]:
    """
    Génère la liste des KPIs auto-calculables pour un dataset.

    Stratégie :
    1. KPI global (row_count)
    2. Pour chaque colonne, KPIs selon son dtype
    3. KPIs qualité pour les colonnes à >5% de nulls
    4. Cap à MAX_KPIS total
    """
    specs: list[KPISpec] = []

    # 1. Globaux
    specs.extend(_global_kpis())

    # 2. Par colonne, selon dtype
    for col in columns:
        if col.dtype in _GENERATORS:
            specs.extend(_GENERATORS[col.dtype](col))

    # 3. KPIs qualité (toutes colonnes avec beaucoup de nulls)
    for col in columns:
        quality = _quality_kpi(col, total_rows)
        if quality is not None:
            specs.append(quality)

    # 4. Cap à MAX_KPIS
    if len(specs) > MAX_KPIS:
        specs = _prioritize(specs)[:MAX_KPIS]

    return specs


def _prioritize(specs: list[KPISpec]) -> list[KPISpec]:
    """
    Priorise les KPIs pour le cap à MAX_KPIS.
    Ordre : volume → average → distribution → quality → range.
    """
    priority_order = {
        "volume": 0,
        "average": 1,
        "distribution": 2,
        "quality": 3,
        "range": 4,
        "general": 5,
    }
    return sorted(specs, key=lambda s: priority_order.get(s.category, 99))
