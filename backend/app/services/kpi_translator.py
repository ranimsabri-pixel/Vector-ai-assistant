"""
Traducteur de KPIs : transforme les suggestions LLM en langage naturel (J9)
en specs exécutables (KPISpec).

Architecture :
1. Reçoit un `suggested_kpi` de J9 + la liste des colonnes profilées
2. Construit un prompt structuré avec contexte (colonnes + dtypes + sample values)
3. Appelle GPT-4o via structured_output avec un JSON schema strict
4. Retourne un KPISpec exécutable
"""
import asyncio
import logging
from typing import Any

from app.ai.providers.base import LLMProvider, Message
from app.db.models.dataset import DatasetColumn
from app.services.kpi_calculator import KPISpec

logger = logging.getLogger(__name__)

LLM_TIMEOUT = 20.0

SYSTEM_PROMPT = """Tu es Vector, un expert en data analysis qui traduit des
descriptions de KPIs en spécifications de calcul exécutables.

Tu reçois :
1. Un KPI décrit en langage naturel (nom, description, colonnes pertinentes)
2. La liste des colonnes disponibles dans le dataset (avec leur type)

Tu dois produire une spec de calcul exécutable au format JSON conforme au schéma.

RÈGLES STRICTES :
- Ne réponds qu'avec le JSON, conforme au schema fourni
- Utilise UNIQUEMENT les colonnes du dataset (pas d'invention)
- Choisis le type de calcul approprié :
  * 'ratio' pour les pourcentages avec filtre
  * 'breakdown' pour décomposer par catégorie (group by)
  * 'trend' pour les évolutions temporelles
  * 'mean'/'sum'/'count_distinct'/'max'/'min' pour les agrégations simples
- Pour 'ratio', définis 'filter' avec column + value
- Pour 'breakdown', définis 'group_by' + (column + aggregation) si calcul agrégé
- Pour 'trend', définis 'time_column' + (column + aggregation) + 'granularity' (month par défaut)
"""


KPI_TRANSLATION_SCHEMA = {
    "name": "kpi_translation",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["count", "count_distinct", "sum", "mean", "median",
                         "min", "max", "ratio", "breakdown", "trend"],
            },
            "column": {
                "type": ["string", "null"],
                "description": "Colonne ciblée (null pour count global)",
            },
            "filter_column": {
                "type": ["string", "null"],
                "description": "Pour ratio : colonne à filtrer (null sinon)",
            },
            "filter_value": {
                "type": ["string", "null"],
                "description": "Pour ratio : valeur à filtrer (null sinon)",
            },
            "group_by": {
                "type": ["string", "null"],
                "description": "Pour breakdown : colonne de groupement",
            },
            "time_column": {
                "type": ["string", "null"],
                "description": "Pour trend : colonne datetime",
            },
            "granularity": {
                "type": ["string", "null"],
                "enum": ["day", "week", "month", "quarter", "year", None],
                "description": "Pour trend : granularité (month par défaut)",
            },
            "aggregation": {
                "type": ["string", "null"],
                "enum": ["count", "count_distinct", "sum", "mean", "median",
                         "min", "max", None],
                "description": "Pour breakdown/trend : agrégation à appliquer",
            },
            "unit": {
                "type": ["string", "null"],
                "description": "Unité d'affichage : %, €, lignes...",
            },
            "rationale": {
                "type": "string",
                "description": "Une phrase courte expliquant pourquoi ce calcul",
            },
        },
        "required": [
            "type", "column", "filter_column", "filter_value", "group_by",
            "time_column", "granularity", "aggregation", "unit", "rationale",
        ],
        "additionalProperties": False,
    },
}


def _build_translation_prompt(
    suggestion: dict[str, Any],
    columns: list[DatasetColumn],
) -> str:
    """Construit le prompt utilisateur pour traduire un KPI suggéré."""
    lines = [
        "KPI à traduire :",
        f"- Nom : {suggestion.get('name', '')}",
        f"- Description : {suggestion.get('description', '')}",
        f"- Colonnes mentionnées : {suggestion.get('columns_used', [])}",
        "",
        "Colonnes disponibles dans le dataset :",
    ]
    for col in columns:
        line = f"- {col.name} ({col.dtype})"
        if col.sample_values:
            samples = col.sample_values.get("samples", [])[:3]
            if samples:
                line += f" — exemples : {samples}"
            top = (col.sample_values.get("stats") or {}).get("top_values", {})
            if top:
                line += f" — top : {list(top.keys())[:3]}"
        lines.append(line)
    lines.append("")
    lines.append(
        "Produis la spec de calcul JSON conforme au schéma. "
        "Choisis le type de calcul le plus naturel pour ce KPI."
    )
    return "\n".join(lines)


async def translate_kpi(
    suggestion: dict[str, Any],
    columns: list[DatasetColumn],
    provider: LLMProvider,
    kpi_index: int = 0,
) -> KPISpec | None:
    """
    Traduit une suggestion (langage naturel) en KPISpec exécutable.
    Retourne None en cas d'échec (LLM indisponible, JSON invalide, etc.).
    """
    user_prompt = _build_translation_prompt(suggestion, columns)
    messages = [
        Message("system", SYSTEM_PROMPT),
        Message("user", user_prompt),
    ]

    try:
        result = await asyncio.wait_for(
            provider.structured_output(
                messages=messages,
                json_schema=KPI_TRANSLATION_SCHEMA,
                temperature=0.1,  # très déterministe pour la traduction
            ),
            timeout=LLM_TIMEOUT,
        )
    except TimeoutError:
        logger.warning("KPI translation timeout for: %s", suggestion.get("name"))
        return None
    except Exception as e:
        logger.error("KPI translation failed: %s", type(e).__name__)
        return None

    # Construction du KPISpec à partir du résultat
    spec_id = f"translated_{kpi_index}_" + "".join(
        c if c.isalnum() else "_" for c in suggestion.get("name", "kpi").lower()
    )[:60]

    spec_filter = None
    if result.get("filter_column") and result.get("filter_value") is not None:
        spec_filter = {
            "column": result["filter_column"],
            "value": result["filter_value"],
        }

    return KPISpec(
        id=spec_id,
        title=suggestion.get("name", "KPI"),
        description=suggestion.get("description", "")
        or result.get("rationale", ""),
        type=result["type"],
        column=result.get("column"),
        filter=spec_filter,
        group_by=result.get("group_by"),
        time_column=result.get("time_column"),
        granularity=result.get("granularity"),
        aggregation=result.get("aggregation"),
        unit=result.get("unit"),
        category="translated",
        icon="Sparkles",
    )


async def translate_all_suggestions(
    suggestions: list[dict[str, Any]],
    columns: list[DatasetColumn],
    provider: LLMProvider,
) -> list[KPISpec]:
    """
    Traduit toutes les suggestions de J9 en parallèle (gain de temps).
    Filtre les échecs (retournés à None).
    """
    tasks = [
        translate_kpi(sug, columns, provider, kpi_index=i)
        for i, sug in enumerate(suggestions)
    ]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]
