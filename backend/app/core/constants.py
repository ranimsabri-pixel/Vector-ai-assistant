"""Tarifs des modeles LLM (S5 J41+ Feature 2) — USD pour 1M tokens.

Source : pricing officiel OpenAI. A mettre a jour si les tarifs changent.
"""

MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"prompt": 2.50, "completion": 10.00},
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
}

# Fallback si le modele n'est pas dans la table (evite un crash, cout approximatif)
_DEFAULT_PRICING = {"prompt": 2.50, "completion": 10.00}


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Cout en USD pour un appel LLM donne.

    L'API OpenAI renvoie le nom de modele "date-e" (ex: "gpt-4o-2024-08-06"),
    jamais le nom nu ("gpt-4o") utilise dans MODEL_PRICING — d'ou un match
    par prefixe. Trie par longueur decroissante pour que "gpt-4o-mini"
    matche avant "gpt-4o" (qui est aussi un prefixe de "gpt-4o-mini").
    """
    pricing = _DEFAULT_PRICING
    for key in sorted(MODEL_PRICING, key=len, reverse=True):
        if model.startswith(key):
            pricing = MODEL_PRICING[key]
            break
    cost = (
        prompt_tokens * pricing["prompt"] + completion_tokens * pricing["completion"]
    ) / 1_000_000
    return round(cost, 6)
