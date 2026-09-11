"""
Service de détection sémantique business d'un dataset.

Architecture en 2 étages :
1. Étage règles : analyse des noms de colonnes + types pour faire un premier diagnostic
2. Étage LLM : envoie le profile au LLM pour générer description + KPIs en JSON structuré

Résilience :
- Timeout explicite sur l'appel LLM (30 sec)
- Fallback gracieux si le LLM est indisponible : analyse minimale basée sur les règles
"""
import asyncio
import logging
from typing import Any

from app.ai.providers.base import LLMProvider, Message
from app.db.models.dataset import Dataset, DatasetColumn

logger = logging.getLogger(__name__)

# Timeout en secondes pour l'appel LLM
LLM_TIMEOUT = 30.0


# ============================================================
# Étage 1 — Détection par règles (rapide, déterministe)
# ============================================================

# Mots-clés par domaine (en français ET en anglais)
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "crm": [
        "client", "customer", "contact", "lead", "prospect", "account",
        "segment", "lifecycle", "nps", "churn", "satisfaction", "tier",
    ],
    "marketing": [
        "campaign", "campagne", "channel", "canal", "touch", "click",
        "impression", "conversion", "ctr", "cpc", "cpm", "audience",
        "ad", "publicite", "publicité", "newsletter", "email_open",
    ],
    "sales": [
        "sale", "vente", "order", "commande", "deal", "pipeline",
        "opportunity", "opportunite", "quote", "devis", "won", "lost",
        "rep", "commercial", "vendor", "product", "produit", "sku",
    ],
    "finance": [
        "transaction", "invoice", "facture", "payment", "paiement",
        "amount", "montant", "revenue", "revenu", "expense", "depense",
        "dépense", "tax", "tva", "balance", "credit", "debit", "iban",
        "refund", "remboursement", "currency", "devise",
    ],
    "hr": [
        "employee", "employe", "employé", "salary", "salaire", "department",
        "departement", "département", "role", "poste", "hire", "embauche",
        "termination", "manager", "team", "equipe", "équipe",
    ],
    "ecommerce": [
        "cart", "panier", "checkout", "order_item", "sku", "stock",
        "inventory", "inventaire", "shipping", "livraison", "review",
        "avis", "rating", "category", "categorie", "catégorie",
    ],
}


def detect_domain_by_rules(columns: list[DatasetColumn]) -> dict[str, Any]:
    """
    Détecte le domaine probable d'un dataset en comptant les matches de mots-clés.
    Retourne un dict avec le domaine principal + scores de tous les domaines.
    """
    column_names = [c.name.lower() for c in columns]

    scores: dict[str, int] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = 0
        for col_name in column_names:
            for kw in keywords:
                if kw in col_name:
                    score += 1
                    break  # un mot-clé suffit par colonne
        scores[domain] = score

    max_score = max(scores.values())
    if max_score == 0:
        primary = "other"
    else:
        primary = max(scores, key=scores.get)

    return {
        "primary_domain": primary,
        "rule_scores": scores,
        "confidence": min(max_score / 3, 1.0),
    }


# ============================================================
# Étage 2 — Analyse LLM (riche, contextuelle)
# ============================================================

SYSTEM_PROMPT = """Tu es Vector, un analyste data senior spécialisé dans l'analyse de datasets business.
Tu reçois la structure d'un dataset (colonnes profilées) et tu dois retourner une analyse sémantique business.

RÈGLES STRICTES :
- Réponds UNIQUEMENT en JSON valide conforme au schéma fourni
- Sois CONCRET : pas de généralités vagues, des recommandations utiles
- Les KPIs proposés doivent être CALCULABLES depuis les colonnes disponibles
- Réponds en FRANÇAIS
"""


ANALYSIS_SCHEMA = {
    "name": "dataset_analysis",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "enum": ["crm", "marketing", "sales", "finance", "hr", "ecommerce", "operations", "other"],
                "description": "Le domaine business principal du dataset",
            },
            "domain_label": {
                "type": "string",
                "description": "Label lisible en français (ex: 'CRM B2B', 'Transactions financières')",
            },
            "description": {
                "type": "string",
                "description": "Description en 2 phrases du contenu et de l'usage métier",
            },
            "key_columns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3-5 colonnes les plus importantes pour l'analyse",
            },
            "suggested_kpis": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "columns_used": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                    },
                    "required": ["name", "description", "columns_used", "priority"],
                    "additionalProperties": False,
                },
                "description": "3 à 5 KPIs recommandés, classés par priorité",
            },
            "warnings": {
                "type": "array",
                "items": {"type": "string"},
                "description": "0 à 3 points d'attention",
            },
        },
        "required": ["domain", "domain_label", "description", "key_columns", "suggested_kpis", "warnings"],
        "additionalProperties": False,
    },
}


def build_user_prompt(
    dataset: Dataset, columns: list[DatasetColumn], rule_hint: str
) -> str:
    """Construit le prompt utilisateur pour le LLM."""
    lines = [f"Dataset : {dataset.name}"]
    if dataset.description:
        lines.append(f"Description utilisateur : {dataset.description}")
    lines.append(f"Nombre de lignes : {dataset.row_count}")
    lines.append(f"Nombre de colonnes : {dataset.column_count}")
    lines.append(f"Hint domaine (basé sur les noms de colonnes) : {rule_hint}")
    lines.append("")
    lines.append("Colonnes profilées :")

    for col in columns:
        samples = []
        stats = {}
        if col.sample_values:
            samples = col.sample_values.get("samples", [])[:3]
            stats = col.sample_values.get("stats", {})

        line = f"- {col.name} ({col.dtype})"
        if col.unique_count is not None:
            line += f", {col.unique_count} valeurs uniques"
        if col.null_count and col.null_count > 0:
            line += f", {col.null_count} nulls"
        if samples:
            line += f" — exemples : {samples}"
        if stats:
            if "min" in stats and "max" in stats:
                line += f" [{stats['min']} → {stats['max']}]"
            if "top_values" in stats:
                top = list(stats["top_values"].keys())[:3]
                line += f" — top : {top}"
        lines.append(line)

    lines.append("")
    lines.append(
        "Analyse ce dataset et retourne le JSON conforme au schéma. "
        "Sois précis et actionnable."
    )

    return "\n".join(lines)


async def analyze_with_llm(
    dataset: Dataset,
    columns: list[DatasetColumn],
    rule_result: dict[str, Any],
    provider: LLMProvider,
) -> dict[str, Any]:
    """
    Appelle le LLM pour générer l'analyse sémantique structurée.
    Retourne le JSON parsé.

    En cas d'erreur (timeout, rate limit, JSON invalide), retourne un fallback
    basé sur les règles uniquement, pour ne pas faire échouer toute l'analyse.
    """
    rule_hint = (
        f"{rule_result['primary_domain']} "
        f"(confiance basée sur règles : {int(rule_result['confidence'] * 100)}%)"
    )

    user_prompt = build_user_prompt(dataset, columns, rule_hint)

    messages = [
        Message("system", SYSTEM_PROMPT),
        Message("user", user_prompt),
    ]

    try:
        result = await asyncio.wait_for(
            provider.structured_output(
                messages=messages,
                json_schema=ANALYSIS_SCHEMA,
                temperature=0.3,
            ),
            timeout=LLM_TIMEOUT,
        )
        return result

    except TimeoutError:
        logger.warning(
            "LLM analysis timeout after %s seconds for dataset %s",
            LLM_TIMEOUT, dataset.id,
        )
        return _fallback_analysis(rule_result, columns, reason="timeout")

    except Exception as e:
        logger.error(
            "LLM analysis failed for dataset %s: %s",
            dataset.id, type(e).__name__,
        )
        return _fallback_analysis(rule_result, columns, reason=type(e).__name__)


def _fallback_analysis(
    rule_result: dict[str, Any],
    columns: list[DatasetColumn],
    reason: str,
) -> dict[str, Any]:
    """
    Fallback minimal si le LLM est indisponible : on utilise les règles
    pour produire une analyse basique mais utilisable.
    """
    domain = rule_result["primary_domain"]

    domain_labels = {
        "crm": "Données clients (CRM)",
        "marketing": "Données marketing",
        "sales": "Données commerciales",
        "finance": "Données financières",
        "hr": "Données ressources humaines",
        "ecommerce": "Données e-commerce",
        "other": "Données non catégorisées",
    }

    key_columns = [c.name for c in columns[:5]]

    return {
        "domain": domain,
        "domain_label": domain_labels.get(domain, "Données"),
        "description": (
            "Analyse automatique par règles (analyse IA temporairement "
            "indisponible). Le dataset semble correspondre au domaine : "
            f"{domain_labels.get(domain, 'inconnu')}."
        ),
        "key_columns": key_columns,
        "suggested_kpis": [],
        "warnings": [
            f"Analyse IA indisponible ({reason}). Relancez l'analyse pour "
            "obtenir des KPIs personnalisés."
        ],
    }


# ============================================================
# Fonction principale combinée
# ============================================================

async def analyze_dataset(
    dataset: Dataset,
    columns: list[DatasetColumn],
    provider: LLMProvider,
) -> dict[str, Any]:
    """
    Pipeline complet : règles d'abord (gratuit/rapide), puis LLM (riche).
    Retourne le résultat enrichi (règles + LLM) à stocker dans semantic_analysis.
    """
    rule_result = detect_domain_by_rules(columns)
    llm_result = await analyze_with_llm(dataset, columns, rule_result, provider)

    return {
        "rule_based": rule_result,
        "llm_analysis": llm_result,
        "analyzed_at": None,
    }
