"""Reponses deterministes pour OpenAIProvider/WebSearchService en mode
USE_MOCK_LLM=true (S5 J52) -- exclusivement pour les specs Playwright
offline, jamais en dev normal ni en prod.

Pattern simple par mots-cles dans le prompt, pas de vraie comprehension :
suffisant pour verifier qu'un flux UI complet fonctionne (upload -> chat ->
sources -> affichage), pas pour verifier la pertinence semantique.
"""
from __future__ import annotations

import hashlib
from typing import Any

EMBED_DIMENSIONS = 1536  # text-embedding-3-small


def extract_text(content: Any) -> str:
    """Extrait le texte d'un content OpenAI, string simple ou liste de blocs
    multimodaux (texte + image_url, cf vision)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return " ".join(parts)
    return ""


def has_image(content: Any) -> bool:
    if not isinstance(content, list):
        return False
    return any(isinstance(b, dict) and b.get("type") == "image_url" for b in content)


def mock_chat_answer(messages: list[dict[str, Any]] | list[Any]) -> str:
    """Genere une reponse deterministe a partir du dernier message utilisateur.

    Regles (dans l'ordre) :
    - image jointe -> decrit une couleur fixe (spec vision mockee)
    - "ibm" dans le prompt -> reponse avec mention de sources fictives
    - "bonjour"/"salut" -> salutation
    - fallback -> reponse generique stable
    """
    last_user_text = ""
    saw_image = False
    for m in messages:
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", None)
        role = m.get("role") if isinstance(m, dict) else getattr(m, "role", None)
        if role == "user":
            last_user_text = extract_text(content)
            saw_image = saw_image or has_image(content)

    text_lower = last_user_text.lower()

    if saw_image:
        return "Cette image est dominée par la couleur bleue."
    if "ibm" in text_lower:
        return (
            "D'après les documents fournis, IBM watsonx s'appuie sur une "
            "architecture modulaire présentée dans le rapport [1] et détaillée "
            "dans le livre blanc [2]."
        )
    if "bonjour" in text_lower or "salut" in text_lower:
        return "Bonjour ! Je suis Vector, comment puis-je t'aider ?"
    if not last_user_text.strip():
        return "Réponse de test pour Vector."
    return f"Réponse de test pour Vector (mock). Question reçue : {last_user_text[:80]}"


def mock_usage(answer: str, model: str) -> dict[str, Any]:
    """Usage tokens factice mais coherent (approx 1 token = 4 caracteres),
    pour que le calcul de cout en aval (calculate_cost) ne plante pas."""
    completion_tokens = max(1, len(answer) // 4)
    prompt_tokens = 20
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "model": model,
    }


def mock_structured_output(json_schema: dict[str, Any]) -> dict[str, Any]:
    """Remplit un JSON schema OpenAI ({name, schema, strict}) avec des
    valeurs factices plausibles selon le type declare. Aucune spec Playwright
    J52 n'exerce ce chemin (analyse dataset / suggestions KPI) -- ce filler
    generique evite juste un crash si jamais il l'etait."""
    schema = json_schema.get("schema", {})
    return _fill_schema(schema)


def _fill_schema(schema: dict[str, Any]) -> Any:
    schema_type = schema.get("type")
    if schema_type == "object":
        props = schema.get("properties", {})
        return {key: _fill_schema(sub) for key, sub in props.items()}
    if schema_type == "array":
        return []
    if schema_type == "string":
        return "mock"
    if schema_type == "number":
        return 0.0
    if schema_type == "integer":
        return 0
    if schema_type == "boolean":
        return False
    return None


def mock_embedding_for(text: str) -> list[float]:
    """Vecteur pseudo-aleatoire deterministe : le meme texte produit toujours
    le meme vecteur (hash SHA-256 utilise comme graine)."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    # Etend le digest (32 octets) a EMBED_DIMENSIONS valeurs flottantes
    # normalisees dans [-1, 1] en repetant/derivant les octets.
    values: list[float] = []
    for i in range(EMBED_DIMENSIONS):
        byte = digest[i % len(digest)]
        # Melange leger avec l'index pour eviter un motif trop repetitif
        values.append(((byte + i) % 256) / 127.5 - 1.0)
    return values
