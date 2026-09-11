"""
Registry des outils Vector + handlers + dispatcher.

J16 : 3 outils de base (list_user_datasets, get_dataset_summary, generate_dashboard)
J18 : 4 outils spécialisés (marketing/sales/customers/trends) + matching d'actions
"""
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.providers.openai import OpenAIProvider
from app.db.models.dataset import Dataset
from app.db.models.user import User
from app.services.dashboards import DashboardService
from app.services.dataset_tools import execute_compute_from_dataset
from app.services.datasets import DatasetService
from app.services.kpi_translator import translate_all_suggestions
from app.services.storage import get_storage

# ============================================================
# TOOLS_SCHEMA — Déclaration OpenAI des outils
# ============================================================

TOOLS_SCHEMA = [
    # -------- J16 : outils de base --------
    {
        "type": "function",
        "function": {
            "name": "list_user_datasets",
            "description": (
                "Liste tous les datasets de l'utilisateur, avec leur nom, "
                "domaine business détecté, nombre de lignes, et date de création. "
                "Depuis J18, chaque dataset expose aussi 'matches_for_action' qui "
                "liste les actions rapides auxquelles il correspond "
                "(general, marketing, sales, customers, trends). "
                "Utiliser quand l'utilisateur demande quels fichiers sont disponibles, "
                "ou quand on a besoin de sélectionner un dataset pour une analyse."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_dashboard",
            "description": (
                "Génère un dashboard de KPIs ÉQUILIBRÉ et GÉNÉRAL pour un dataset. "
                "Couvre les indicateurs principaux (totaux, moyennes, breakdowns) sans "
                "spécialisation métier. Utiliser pour l'action 'Dashboard KPI général' "
                "ou quand l'utilisateur ne précise pas un focus métier."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "UUID du dataset à analyser",
                    },
                },
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dataset_summary",
            "description": (
                "Retourne un résumé détaillé d'un dataset : nom, nombre de lignes/colonnes, "
                "score de qualité, domaine business, description IA, et liste des colonnes. "
                "Utiliser quand l'utilisateur demande des infos sur un fichier précis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "UUID du dataset",
                    },
                },
                "required": ["dataset_id"],
            },
        },
    },
    # -------- J18 : outils spécialisés (formulaires conversationnels) --------
    {
        "type": "function",
        "function": {
            "name": "generate_marketing_dashboard",
            "description": (
                "Génère un dashboard SPÉCIALISÉ MARKETING : canaux d'acquisition, "
                "taux de conversion, performance par campagne, CAC, ROAS. "
                "À utiliser pour l'action rapide 'Performances marketing' "
                "ou quand l'utilisateur mentionne canaux, campagnes, conversion."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "UUID du dataset à analyser",
                    },
                    "period": {
                        "type": "string",
                        "enum": ["7d", "30d", "90d", "all"],
                        "description": "Période d'analyse (défaut: 30d)",
                    },
                    "channel_focus": {
                        "type": "string",
                        "description": "Canal prioritaire optionnel (ex: SEO, paid, social)",
                    },
                },
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_sales_dashboard",
            "description": (
                "Génère un dashboard SPÉCIALISÉ VENTES : chiffre d'affaires, "
                "panier moyen, top produits, performance par vendeur, taux de conversion. "
                "À utiliser pour l'action rapide 'Performances commerciales'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "UUID du dataset à analyser",
                    },
                    "priority_metric": {
                        "type": "string",
                        "enum": ["revenue", "basket", "volume", "conversion"],
                        "description": "Métrique prioritaire (défaut: revenue)",
                    },
                    "granularity": {
                        "type": "string",
                        "enum": ["day", "week", "month", "quarter"],
                        "description": "Granularité temporelle (défaut: month)",
                    },
                },
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_customers_dashboard",
            "description": (
                "Génère un dashboard SPÉCIALISÉ CLIENTS : segmentation RFM, "
                "top clients par CA, distribution par segment, valeur client. "
                "À utiliser pour l'action rapide 'Clients et segments rentables'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "UUID du dataset à analyser",
                    },
                    "segmentation": {
                        "type": "string",
                        "enum": ["rfm", "revenue_only", "frequency_only"],
                        "description": "Méthode de segmentation (défaut: rfm)",
                    },
                    "top_n": {
                        "type": "integer",
                        "enum": [10, 20, 50],
                        "description": "Top N clients à mettre en avant (défaut: 20)",
                    },
                },
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_trends_dashboard",
            "description": (
                "Génère un dashboard SPÉCIALISÉ TENDANCES ET ANOMALIES : "
                "comparaison période actuelle vs précédente, détection d'évolutions "
                "significatives, valeurs aberrantes. "
                "À utiliser pour l'action rapide 'Tendances et anomalies'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {
                        "type": "string",
                        "description": "UUID du dataset à analyser",
                    },
                    "comparison_period": {
                        "type": "string",
                        "enum": ["previous_month", "previous_quarter", "previous_year"],
                        "description": "Période A de comparaison (défaut: previous_month)",
                    },
                    "sensitivity": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Sensibilité aux anomalies (défaut: medium)",
                    },
                },
                "required": ["dataset_id"],
            },
        },
    },
]


# ============================================================
# Heuristique matching action ↔ dataset (J18)
# Pour chaque dataset, on détecte à quelles actions rapides il correspond,
# selon les mots-clés présents dans les noms de colonnes (profilées J7).
# ============================================================

ACTION_KEYWORDS: dict[str, set[str]] = {
    "marketing": {
        "channel", "canal", "campaign", "campagne", "source", "click",
        "clic", "impression", "ctr", "ad", "utm", "lead", "conversion",
        "funnel", "cac", "roas",
    },
    "sales": {
        "amount", "montant", "revenue", "ca", "price", "prix", "product",
        "produit", "salesperson", "vendeur", "seller", "order", "commande",
        "invoice", "facture", "panier", "quantity", "quantite",
    },
    "customers": {
        "client", "customer", "user_id", "email", "buyer", "segment",
        "loyalty", "membership", "subscriber", "rfm", "recency",
        "frequency", "monetary",
    },
    "trends": {
        "date", "time", "created_at", "timestamp", "day", "week",
        "month", "year", "jour", "mois",
    },
}


def _detect_matching_actions(column_names: list[str]) -> list[str]:
    """
    Pour une liste de noms de colonnes, retourne les action_ids qui matchent.
    'general' est toujours présent (un dataset 'ready' marche pour le général).
    """
    matches = {"general"}
    cols_lower = [c.lower() for c in column_names]

    for action_id, keywords in ACTION_KEYWORDS.items():
        for col in cols_lower:
            if any(kw in col for kw in keywords):
                matches.add(action_id)
                break

    return sorted(matches)


# ============================================================
# Handlers : J16 — outils de base
# ============================================================

async def handle_list_user_datasets(
    db: AsyncSession,
    user: User,
    **kwargs: Any,
) -> dict[str, Any]:
    """Liste les datasets de l'utilisateur, enrichis du matching d'actions (J18)."""
    # Eager load des colonnes (évite N+1) — pattern SQLAlchemy 2.0
    result = await db.execute(
        select(Dataset)
        .where(Dataset.user_id == user.id)
        .options(selectinload(Dataset.columns))
        .order_by(Dataset.created_at.desc())
    )
    datasets = result.scalars().all()

    return {
        "count": len(datasets),
        "datasets": [
            {
                "id": str(d.id),
                "name": d.name,
                "domain": (d.semantic_analysis or {})
                    .get("llm_analysis", {})
                    .get("domain_label", "Inconnu"),
                "rows": d.row_count,
                "columns": d.column_count,
                "quality": int((d.quality_score or 0) * 100),
                "status": d.status,
                "created_at": d.created_at.isoformat(),
                # NEW J18 : actions rapides auxquelles ce dataset correspond
                "matches_for_action": _detect_matching_actions(
                    [c.name for c in d.columns] if d.columns else []
                ),
            }
            for d in datasets
        ],
    }


async def handle_generate_dashboard(
    db: AsyncSession,
    user: User,
    dataset_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Génère un dashboard général pour un dataset (J16, équilibré)."""
    try:
        ds_uuid = UUID(dataset_id)
    except ValueError:
        return {"error": "dataset_id invalide (UUID attendu)"}

    dataset = await db.get(Dataset, ds_uuid)
    if not dataset or dataset.user_id != user.id:
        return {"error": "Dataset introuvable"}

    if dataset.status != "ready":
        return {
            "error": f"Le dataset n'est pas encore profilé (status={dataset.status})"
        }

    # Génère les KPIs s'ils ne sont pas déjà là
    dataset_service = DatasetService(db, get_storage())
    if not dataset.auto_kpis or not dataset.auto_kpis.get("specs"):
        await dataset_service.generate_auto_kpis(user, ds_uuid)
        await dataset_service.generate_advanced_kpis(user, ds_uuid)
        dataset = await db.get(Dataset, ds_uuid)

    kpi_results = await dataset_service.calculate_all_auto_kpis(user, ds_uuid)
    results_as_dict = [
        r if isinstance(r, dict) else r.to_dict()
        for r in kpi_results
    ]

    dashboard_service = DashboardService(db)
    saved = await dashboard_service.save_dashboard(
        user=user,
        dataset_id=ds_uuid,
        title=dataset.name + " — Dashboard",
        kpi_specs=dataset.auto_kpis.get("specs", []) if dataset.auto_kpis else [],
        kpi_results=results_as_dict,
    )

    return {
        "success": True,
        "dashboard_id": str(saved.id),
        "dataset_id": str(ds_uuid),
        "dataset_name": dataset.name,
        "kpi_count": len(results_as_dict),
        "dashboard_url": f"/dashboard/{ds_uuid}",  # page standalone paramétrée par dataset_id (J13)
        "message": (
            f"Dashboard généré pour {dataset.name} avec {len(results_as_dict)} KPIs. "
            f"L'utilisateur peut l'ouvrir via l'URL fournie."
        ),
    }


async def handle_get_dataset_summary(
    db: AsyncSession,
    user: User,
    dataset_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Résumé d'un dataset spécifique."""
    try:
        ds_uuid = UUID(dataset_id)
    except ValueError:
        return {"error": "dataset_id invalide (UUID attendu)"}

    dataset = await db.get(Dataset, ds_uuid)
    if not dataset or dataset.user_id != user.id:
        return {"error": "Dataset introuvable"}

    semantic = dataset.semantic_analysis or {}
    llm = semantic.get("llm_analysis", {})

    return {
        "id": str(dataset.id),
        "name": dataset.name,
        "rows": dataset.row_count,
        "columns": dataset.column_count,
        "quality": int((dataset.quality_score or 0) * 100),
        "domain": llm.get("domain_label", "Inconnu"),
        "description": llm.get("description", ""),
        "key_columns": llm.get("key_columns", []),
        "suggested_kpis": [k.get("name") for k in llm.get("suggested_kpis", [])],
        "status": dataset.status,
    }


# ============================================================
# J18 — Fonction commune : fat core
# Le vrai travail des handlers spécialisés. Reçoit des suggestions de KPIs
# orientées focus, les traduit en KPISpec via le translator (J12), calcule,
# et sauvegarde le dashboard.
# ============================================================

async def _generate_dashboard_with_focus(
    db: AsyncSession,
    user: User,
    dataset_id: str,
    focus_type: str,                    # marketing | sales | customers | trends
    focus_label: str,                   # ex: "Marketing", "Ventes", ...
    focus_suggestions: list[dict[str, Any]],  # format J9 : {name, description, columns_used}
    focus_context: dict[str, Any],      # params métier (period, top_n, ...) — pour traçabilité
) -> dict[str, Any]:
    """
    Génère un dashboard spécialisé : prend des suggestions au format J9,
    les traduit en KPISpec (J12), calcule, sauve, retourne le format standard.

    Architecture : zéro modification de kpi_translator.py ni de datasets.py.
    On réutilise toute la chaîne J9 → J12 en construisant nos propres suggestions
    en entrée. C'est l'application de l'Open/Closed Principle.
    """
    # 1. Validation UUID + ownership + statut ready
    try:
        ds_uuid = UUID(dataset_id)
    except ValueError:
        return {"error": "dataset_id invalide (UUID attendu)"}

    dataset = await db.get(Dataset, ds_uuid)
    if not dataset or dataset.user_id != user.id:
        return {"error": "Dataset introuvable"}

    if dataset.status != "ready":
        return {
            "error": f"Le dataset n'est pas encore profilé (status={dataset.status})"
        }

    dataset_service = DatasetService(db, get_storage())

    # 2. Récupère les colonnes profilées (J7) pour les passer au translator
    columns = await dataset_service.get_dataset_columns(user, ds_uuid)
    if not columns:
        return {"error": "Aucune colonne profilée trouvée pour ce dataset"}

    # 3. Traduit les suggestions focus en KPISpec exécutables (J12)
    # On utilise translate_all_suggestions existant sans le modifier.
    provider = OpenAIProvider()
    focus_specs = await translate_all_suggestions(
        focus_suggestions, columns, provider
    )

    if not focus_specs:
        return {
            "error": (
                f"Aucun KPI focus '{focus_type}' n'a pu être généré. "
                f"Les colonnes du dataset ne correspondent peut-être pas à ce domaine."
            )
        }

    # 4. Fusion avec les auto_kpis existants — pattern J14 anti-doublon
    existing = dataset.auto_kpis or {"specs": []}
    existing_specs = existing.get("specs", [])
    existing_ids = {s["id"] for s in existing_specs}
    new_specs_dicts = [
        s.to_dict() for s in focus_specs if s.id not in existing_ids
    ]

    dataset.auto_kpis = {
        "specs": existing_specs + new_specs_dicts,
        "generated_count": len(existing_specs) + len(new_specs_dicts),
    }
    await db.commit()
    await db.refresh(dataset)

    # 5. Calcule TOUS les KPIs (anciens + focus) en une passe batch
    kpi_results = await dataset_service.calculate_all_auto_kpis(user, ds_uuid)
    results_as_dict = [
        r if isinstance(r, dict) else r.to_dict()
        for r in kpi_results
    ]

    # 6. Sauvegarde le dashboard avec titre enrichi
    dashboard_service = DashboardService(db)
    saved = await dashboard_service.save_dashboard(
        user=user,
        dataset_id=ds_uuid,
        title=f"{dataset.name} — Dashboard {focus_label}",
        kpi_specs=dataset.auto_kpis.get("specs", []),
        kpi_results=results_as_dict,
    )

    return {
        "success": True,
        "dashboard_id": str(saved.id),
        "dataset_id": str(ds_uuid),
        "dataset_name": dataset.name,
        "kpi_count": len(results_as_dict),
        "focus_type": focus_type,
        "focus_label": focus_label,
        "focus_context": focus_context,
        "new_kpis_added": len(new_specs_dicts),
        "dashboard_url": f"/dashboard/{ds_uuid}",
        "message": (
            f"Dashboard {focus_label} généré pour {dataset.name} : "
            f"{len(new_specs_dicts)} nouveaux KPIs focus + "
            f"{len(existing_specs)} KPIs existants = "
            f"{len(results_as_dict)} KPIs au total."
        ),
    }


# ============================================================
# J18 — Builders de suggestions focus (par domaine métier)
# Chaque builder retourne 5-8 suggestions au format J9 attendu par translator.
# ============================================================

def _build_marketing_suggestions(
    period: str = "30d", channel_focus: str | None = None
) -> list[dict[str, Any]]:
    """Suggestions de KPIs marketing — orientées canaux et conversion."""
    channel_hint = f" (focus canal : {channel_focus})" if channel_focus else ""
    period_label = {
        "7d": "7 derniers jours",
        "30d": "30 derniers jours",
        "90d": "90 derniers jours",
        "all": "période complète",
    }.get(period, period)

    return [
        {
            "name": "Volume total de conversions",
            "description": f"Nombre total de conversions sur la {period_label}{channel_hint}",
            "columns_used": ["conversion", "channel", "campaign", "source"],
        },
        {
            "name": "Taux de conversion global",
            "description": f"Ratio conversions / impressions ou clics sur la {period_label}",
            "columns_used": ["conversion", "click", "impression"],
        },
        {
            "name": "Performance par canal",
            "description": f"Nombre de conversions ou leads par canal d'acquisition{channel_hint}",
            "columns_used": ["channel", "source", "utm", "conversion"],
        },
        {
            "name": "Top campagnes",
            "description": "Top 10 campagnes par volume de conversions ou ROAS",
            "columns_used": ["campaign", "campagne", "conversion", "revenue"],
        },
        {
            "name": "Coût d'acquisition moyen",
            "description": "Coût moyen pour acquérir un lead ou une conversion (CAC)",
            "columns_used": ["cost", "spend", "cac", "conversion", "lead"],
        },
        {
            "name": "Evolution temporelle des conversions",
            "description": f"Tendance des conversions sur la {period_label}, par jour ou semaine",
            "columns_used": ["date", "conversion", "channel"],
        },
    ]


def _build_sales_suggestions(
    priority_metric: str = "revenue", granularity: str = "month"
) -> list[dict[str, Any]]:
    """Suggestions de KPIs commerciaux — orientées CA et produits."""
    granularity_label = {
        "day": "journalière",
        "week": "hebdomadaire",
        "month": "mensuelle",
        "quarter": "trimestrielle",
    }.get(granularity, granularity)

    suggestions = [
        {
            "name": "Chiffre d'affaires total",
            "description": "Somme totale des montants de vente sur la période",
            "columns_used": ["amount", "montant", "revenue", "price", "ca"],
        },
        {
            "name": "Panier moyen",
            "description": "Valeur moyenne d'une commande ou d'une transaction",
            "columns_used": ["amount", "montant", "order", "panier"],
        },
        {
            "name": "Top produits par CA",
            "description": "Top 10 produits qui génèrent le plus de chiffre d'affaires",
            "columns_used": ["product", "produit", "amount", "revenue", "quantity"],
        },
        {
            "name": "Performance par vendeur",
            "description": "CA généré par chaque vendeur ou commercial",
            "columns_used": ["salesperson", "vendeur", "seller", "amount", "revenue"],
        },
        {
            "name": "Volume de commandes",
            "description": "Nombre total de commandes ou transactions",
            "columns_used": ["order", "commande", "invoice", "facture"],
        },
        {
            "name": f"Evolution {granularity_label} du CA",
            "description": f"Tendance du chiffre d'affaires en {granularity_label}",
            "columns_used": ["date", "amount", "revenue"],
        },
    ]

    # Priorisation : place la métrique prioritaire en première position
    priority_map = {
        "revenue": "Chiffre d'affaires total",
        "basket": "Panier moyen",
        "volume": "Volume de commandes",
        "conversion": "Top produits par CA",
    }
    priority_name = priority_map.get(priority_metric)
    if priority_name:
        suggestions.sort(key=lambda s: 0 if s["name"] == priority_name else 1)

    return suggestions


def _build_customers_suggestions(
    segmentation: str = "rfm", top_n: int = 20
) -> list[dict[str, Any]]:
    """Suggestions de KPIs clients — orientées segmentation et valeur."""
    suggestions = [
        {
            "name": "Nombre total de clients uniques",
            "description": "Comptage distinct des clients dans la période",
            "columns_used": ["client", "customer", "user_id", "email"],
        },
        {
            "name": f"Top {top_n} clients par CA",
            "description": f"Top {top_n} clients qui génèrent le plus de revenus",
            "columns_used": ["client", "customer", "amount", "revenue"],
        },
        {
            "name": "Valeur client moyenne",
            "description": "Revenu moyen par client (CA / nombre de clients uniques)",
            "columns_used": ["amount", "revenue", "client", "customer"],
        },
        {
            "name": "Distribution par segment",
            "description": "Répartition des clients par segment ou catégorie",
            "columns_used": ["segment", "category", "client", "customer"],
        },
    ]

    if segmentation == "rfm":
        suggestions.append({
            "name": "Segmentation RFM",
            "description": (
                "Répartition des clients selon Recency (récence d'achat), "
                "Frequency (fréquence), Monetary (valeur monétaire)"
            ),
            "columns_used": ["client", "customer", "date", "amount", "frequency"],
        })
    elif segmentation == "revenue_only":
        suggestions.append({
            "name": "Quartiles de revenus client",
            "description": "Répartition des clients par tranches de revenus (Q1-Q4)",
            "columns_used": ["client", "customer", "amount", "revenue"],
        })
    elif segmentation == "frequency_only":
        suggestions.append({
            "name": "Fréquence d'achat",
            "description": "Nombre moyen d'achats par client sur la période",
            "columns_used": ["client", "customer", "order", "frequency"],
        })

    return suggestions


def _build_trends_suggestions(
    comparison_period: str = "previous_month", sensitivity: str = "medium"
) -> list[dict[str, Any]]:
    """Suggestions de KPIs tendances — orientées comparaison et anomalies."""
    period_label = {
        "previous_month": "mois précédent",
        "previous_quarter": "trimestre précédent",
        "previous_year": "année précédente",
    }.get(comparison_period, comparison_period)

    return [
        {
            "name": "Volume période actuelle",
            "description": "Volume d'activité sur la période en cours",
            "columns_used": ["date", "amount", "quantity", "conversion"],
        },
        {
            "name": f"Comparaison vs {period_label}",
            "description": f"Variation de l'activité par rapport au {period_label}",
            "columns_used": ["date", "amount", "quantity"],
        },
        {
            "name": "Tendance temporelle",
            "description": "Évolution chronologique des indicateurs clés",
            "columns_used": ["date", "time", "amount", "quantity"],
        },
        {
            "name": "Valeurs aberrantes détectées",
            "description": f"Anomalies statistiques (sensibilité : {sensitivity})",
            "columns_used": ["amount", "quantity", "date"],
        },
        {
            "name": "Saisonnalité",
            "description": "Patterns récurrents par mois ou jour de semaine",
            "columns_used": ["date", "month", "week", "day"],
        },
        {
            "name": "Croissance moyenne",
            "description": "Taux de croissance moyen sur la période observée",
            "columns_used": ["date", "amount", "revenue"],
        },
    ]


# ============================================================
# J18 — Handlers spécialisés (thin wrappers sur _generate_dashboard_with_focus)
# ============================================================

async def handle_generate_marketing_dashboard(
    db: AsyncSession,
    user: User,
    dataset_id: str,
    period: str = "30d",
    channel_focus: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Dashboard spécialisé marketing."""
    return await _generate_dashboard_with_focus(
        db, user, dataset_id,
        focus_type="marketing",
        focus_label="Marketing",
        focus_suggestions=_build_marketing_suggestions(period, channel_focus),
        focus_context={"period": period, "channel_focus": channel_focus},
    )


async def handle_generate_sales_dashboard(
    db: AsyncSession,
    user: User,
    dataset_id: str,
    priority_metric: str = "revenue",
    granularity: str = "month",
    **kwargs: Any,
) -> dict[str, Any]:
    """Dashboard spécialisé ventes."""
    return await _generate_dashboard_with_focus(
        db, user, dataset_id,
        focus_type="sales",
        focus_label="Ventes",
        focus_suggestions=_build_sales_suggestions(priority_metric, granularity),
        focus_context={"priority_metric": priority_metric, "granularity": granularity},
    )


async def handle_generate_customers_dashboard(
    db: AsyncSession,
    user: User,
    dataset_id: str,
    segmentation: str = "rfm",
    top_n: int = 20,
    **kwargs: Any,
) -> dict[str, Any]:
    """Dashboard spécialisé clients (RFM)."""
    return await _generate_dashboard_with_focus(
        db, user, dataset_id,
        focus_type="customers",
        focus_label="Clients & Segments",
        focus_suggestions=_build_customers_suggestions(segmentation, top_n),
        focus_context={"segmentation": segmentation, "top_n": top_n},
    )


async def handle_generate_trends_dashboard(
    db: AsyncSession,
    user: User,
    dataset_id: str,
    comparison_period: str = "previous_month",
    sensitivity: str = "medium",
    **kwargs: Any,
) -> dict[str, Any]:
    """Dashboard spécialisé tendances et anomalies."""
    return await _generate_dashboard_with_focus(
        db, user, dataset_id,
        focus_type="trends",
        focus_label="Tendances & Anomalies",
        focus_suggestions=_build_trends_suggestions(comparison_period, sensitivity),
        focus_context={
            "comparison_period": comparison_period,
            "sensitivity": sensitivity,
        },
    )


# ============================================================
# Dispatcher (map nom → handler)
# ============================================================

TOOL_HANDLERS = {
    # J16 : outils de base
    "list_user_datasets": handle_list_user_datasets,
    "generate_dashboard": handle_generate_dashboard,
    "get_dataset_summary": handle_get_dataset_summary,
    # J18 : outils spécialisés
    "generate_marketing_dashboard": handle_generate_marketing_dashboard,
    "generate_sales_dashboard": handle_generate_sales_dashboard,
    "generate_customers_dashboard": handle_generate_customers_dashboard,
    "generate_trends_dashboard": handle_generate_trends_dashboard,
    # J46 : calcul exact (pandas) sur dataset actif — Option A tool calling
    "compute_from_dataset": execute_compute_from_dataset,
}


async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    db: AsyncSession,
    user: User,
) -> dict[str, Any]:
    """
    Exécute un outil par son nom avec ses arguments.
    Retourne un dict qui sera renvoyé au LLM en tant que tool_result.
    """
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {"error": f"Outil inconnu : {tool_name}"}

    try:
        return await handler(db=db, user=user, **arguments)
    except Exception as e:
        return {"error": f"Erreur d'exécution : {type(e).__name__}: {e}"}
