"""
Outil de calcul exact (pandas) sur les datasets — compute_from_dataset.

S5 J46 — Option A (tool calling force) en remplacement de l'Option C (prompt
engineering) pour les questions chiffrees sur un dataset attache au chat :
le LLM ne calcule plus jamais mentalement, il delegue systematiquement le
calcul a ce tool, qui l'execute via kpi_calculator.py (deja utilise pour les
KPIs de dashboard — memes fonctions, memes garanties de type JSON-safe).

Contrat : ne leve jamais d'exception vers l'appelant. Toute erreur (dataset
introuvable, colonne inexistante, operation inconnue, ownership...) retourne
{"success": False, "error": "..."} — jamais un crash qui remonterait au LLM
sous forme de tool_call en echec silencieux.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.services.datasets import DatasetService
from app.services.kpi_calculator import (
    KPISpec,
    _apply_filter,
    _ensure_numeric,
    calculate_breakdown,
    calculate_kpi,
)
from app.services.storage import FileStorage

SIMPLE_OPERATIONS = {"sum", "mean", "median", "min", "max", "count", "count_distinct"}
GROUP_OPERATIONS = {"top_n", "group_by_agg"}
ALL_OPERATIONS = SIMPLE_OPERATIONS | GROUP_OPERATIONS | {"correlation"}

_OP_LABELS = {
    "sum": "Somme",
    "mean": "Moyenne",
    "median": "Médiane",
    "min": "Minimum",
    "max": "Maximum",
    "count": "Comptage",
    "count_distinct": "Nombre de valeurs distinctes",
}


def _json_safe(value: Any) -> Any:
    """Filet de sécurité : force tout résidu numpy/pandas en types JSON natifs.

    kpi_calculator.py caste déjà explicitement (float/int/str) partout, mais
    ce passage garantit qu'aucune régression future ne laisse fuiter un
    numpy.int64/Timestamp non sérialisable vers le LLM."""
    return json.loads(json.dumps(value, default=str))


async def execute_compute_from_dataset(
    db: AsyncSession,
    user: User,
    dataset_id: str,
    operation: str,
    column: str | None = None,
    column2: str | None = None,
    group_by: str | None = None,
    aggregation: str | None = None,
    filters: list[dict[str, Any]] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Point d'entrée du tool compute_from_dataset — charge, filtre, calcule."""
    if operation not in ALL_OPERATIONS:
        return {
            "success": False,
            "error": (
                f"Opération inconnue : '{operation}'. Opérations disponibles : "
                f"{sorted(ALL_OPERATIONS)}"
            ),
        }

    try:
        ds_uuid = UUID(dataset_id)
    except (ValueError, AttributeError, TypeError):
        return {"success": False, "error": "dataset_id invalide (UUID attendu)"}

    service = DatasetService(db, FileStorage())
    try:
        dataset = await service.get_dataset(user, ds_uuid)
    except Exception:
        # get_dataset lève HTTPException 404 si absent ou pas owned — jamais
        # exposer ce détail HTTP au LLM, juste un message clair.
        return {"success": False, "error": "Dataset introuvable"}

    if dataset.status != "ready":
        return {
            "success": False,
            "error": f"Le dataset n'est pas encore prêt (status={dataset.status})",
        }

    full_path = service.storage.get_full_path(dataset.file_path)
    ext = Path(dataset.original_filename).suffix.lower()
    try:
        df = pd.read_csv(full_path) if ext == ".csv" else pd.read_excel(full_path)
    except Exception as e:
        return {"success": False, "error": f"Impossible de charger le fichier : {e}"}

    if filters:
        for f in filters:
            try:
                df = _apply_filter(df, f)
            except ValueError as e:
                return {"success": False, "error": str(e)}

    if df.empty:
        return {
            "success": True,
            "result": {"row_count": 0},
            "summary": "Aucune ligne ne correspond aux filtres appliqués.",
        }

    try:
        if operation in SIMPLE_OPERATIONS:
            result, summary = _run_simple(df, operation, column)
        elif operation in GROUP_OPERATIONS:
            result, summary = _run_group(df, operation, column, group_by, aggregation, limit)
        else:
            result, summary = _run_correlation(df, column, column2)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    return {
        "success": True,
        "result": _json_safe(result),
        "summary": summary,
    }


def _run_simple(
    df: pd.DataFrame, operation: str, column: str | None
) -> tuple[dict[str, Any], str]:
    """sum/mean/median/min/max/count/count_distinct — délègue à calculate_kpi."""
    spec = KPISpec(id="tool_call", title=operation, description="", type=operation, column=column)
    result = calculate_kpi(df, spec)
    label = column or "lignes"
    summary = f"{_OP_LABELS.get(operation, operation)} de « {label} » : {result.formatted}"
    return result.to_dict(), summary


def _run_group(
    df: pd.DataFrame,
    operation: str,
    column: str | None,
    group_by: str | None,
    aggregation: str | None,
    limit: int | None,
) -> tuple[dict[str, Any], str]:
    """top_n/group_by_agg — délègue à calculate_breakdown (group by + tri desc)."""
    if not group_by:
        raise ValueError(f"L'opération '{operation}' nécessite le paramètre 'group_by'")

    agg = aggregation or ("sum" if column else "count")
    cap = limit or (5 if operation == "top_n" else 10)

    spec = KPISpec(
        id="tool_call",
        title=operation,
        description="",
        type="breakdown",
        column=column,
        group_by=group_by,
        aggregation=agg,
        top_n=cap,
    )
    result = calculate_breakdown(df, spec)
    breakdown: dict[str, float] = result.metadata["breakdown"] if result.metadata else {}
    top_items = list(breakdown.items())[:3]
    items_str = ", ".join(f"{k} ({v:g})" for k, v in top_items) if top_items else "aucun résultat"
    target = column or group_by
    summary = f"{_OP_LABELS.get(agg, agg)} de « {target} » par « {group_by} » — top : {items_str}"
    return result.to_dict(), summary


def _run_correlation(
    df: pd.DataFrame, column: str | None, column2: str | None
) -> tuple[dict[str, Any], str]:
    """Corrélation de Pearson entre 2 colonnes numériques."""
    if not column or not column2:
        raise ValueError("'correlation' nécessite 'column' et 'column2'")
    if column not in df.columns:
        raise ValueError(f"Colonne introuvable : '{column}'")
    if column2 not in df.columns:
        raise ValueError(f"Colonne introuvable : '{column2}'")

    s1 = _ensure_numeric(df[column], column)
    s2 = _ensure_numeric(df[column2], column2)
    corr = s1.corr(s2)
    if corr is None or pd.isna(corr):
        raise ValueError(
            f"Corrélation non calculable entre '{column}' et '{column2}' "
            "(données insuffisantes ou colonne constante)"
        )

    corr = round(float(corr), 3)
    strength = "forte" if abs(corr) >= 0.7 else "modérée" if abs(corr) >= 0.3 else "faible"
    direction = "positive" if corr > 0 else "négative" if corr < 0 else "nulle"
    summary = f"Corrélation entre « {column} » et « {column2} » : {corr} ({strength}, {direction})"
    return {"column": column, "column2": column2, "correlation": corr}, summary


def get_compute_tool_schema() -> dict[str, Any]:
    """Définition OpenAI tool-calling de compute_from_dataset."""
    return {
        "type": "function",
        "function": {
            "name": "compute_from_dataset",
            "description": (
                "Exécute un calcul EXACT (pandas) sur le dataset tabulaire actif "
                "dans la conversation. OBLIGATOIRE pour toute question chiffrée "
                "(somme, moyenne, médiane, min, max, comptage, top N, agrégation "
                "par groupe, corrélation) : ne jamais calculer mentalement à "
                "partir de l'extrait de données fourni, toujours passer par cet "
                "outil pour garantir l'exactitude du résultat."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "UUID du dataset actif (fourni dans le contexte de la conversation)",
                    },
                    "operation": {
                        "type": "string",
                        "enum": sorted(ALL_OPERATIONS),
                        "description": "Type de calcul à effectuer",
                    },
                    "column": {
                        "type": "string",
                        "description": "Colonne cible du calcul (requise sauf pour 'count')",
                    },
                    "column2": {
                        "type": "string",
                        "description": "Deuxième colonne — requise uniquement pour 'correlation'",
                    },
                    "group_by": {
                        "type": "string",
                        "description": "Colonne de regroupement — requise pour 'top_n' et 'group_by_agg'",
                    },
                    "aggregation": {
                        "type": "string",
                        "enum": ["sum", "mean", "median", "min", "max", "count", "count_distinct"],
                        "description": (
                            "Agrégation utilisée pour 'top_n'/'group_by_agg' "
                            "(défaut : sum si 'column' fourni, sinon count)"
                        ),
                    },
                    "filters": {
                        "type": "array",
                        "description": "Filtres appliqués avant le calcul (combinés en ET)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string"},
                                "op": {
                                    "type": "string",
                                    "enum": [
                                        "eq", "ne", "gt", "gte", "lt", "lte",
                                        "in", "startswith", "contains",
                                    ],
                                },
                                "value": {
                                    "description": "Valeur de comparaison (texte, nombre, ou liste pour 'in')",
                                },
                            },
                            "required": ["column", "op", "value"],
                        },
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Nombre max de groupes retournés pour 'top_n'/'group_by_agg' "
                            "(défaut : 5 pour top_n, 10 pour group_by_agg)"
                        ),
                    },
                },
                "required": ["dataset_id", "operation"],
            },
        },
    }
