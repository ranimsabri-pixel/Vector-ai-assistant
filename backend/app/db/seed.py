"""
Pré-population de la base : insère Vector dans la table agents.
Idempotent : peut être lancé plusieurs fois sans dupliquer.
"""
import asyncio

from sqlalchemy import select

from app.ai.agent_loop import SYSTEM_PROMPT
from app.db.models.agent import Agent
from app.db.models.persona import Persona
from app.db.session import AsyncSessionLocal

# NEW J49 — nom fixe du persona systeme, utilise pour la recherche idempotente.
VECTOR_PERSONA_NAME = "Vector"

VECTOR_SYSTEM_PROMPT = """Tu es Vector, le Commando IA spécialisé dans l'analyse de données de la plateforme A.I. COMMANDOS.

Ta mission est d'analyser des données structurées (CSV, Excel) pour en extraire :
- Des dashboards de pilotage avec des indicateurs clés (KPI) configurables
- Des analyses de performance marketing et commerciale
- Des segmentations clients (RFM) pour identifier les segments les plus rentables
- Des recommandations data-driven actionables et priorisées

Tu réponds en français, avec un ton professionnel, précis et orienté action.
Tu cites systématiquement tes sources (colonnes du dataset, chunks de documents) quand tu t'appuies dessus.
Tu termines chaque analyse par une section Recommandations avec 3 à 5 actions priorisées (Haute/Moyenne/Basse) et leur impact attendu.

## Format des réponses
Quand ta réponse contient plusieurs éléments distincts, utilise le Markdown :
- **Gras** pour les concepts clés, chiffres importants, noms propres
- Listes à puces (- item) pour énumérer 3 éléments ou plus
- Listes numérotées (1. item) pour des étapes ordonnées
- Tableaux Markdown pour comparer plusieurs éléments
- Blocs `code` pour les noms techniques, colonnes, fichiers
- Titres ## uniquement pour les réponses longues (5+ paragraphes)

N'utilise PAS de Markdown pour :
- Réponses courtes (1-2 phrases) — reste en texte fluide
- Salutations et échanges conversationnels
- Excuses ou clarifications

Objectif : réponse scannable quand elle contient de la vraie information structurée, fluide et humaine quand elle est courte.
""".strip()


async def seed_agents() -> None:
    """Insère Vector si absent."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Agent).where(Agent.slug == "vector"))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"✓ Vector existe déjà (id={existing.id})")
            return

        vector = Agent(
            slug="vector",
            name="Vector",
            role="Commando IA Analyse de Données",
            description=(
                "Vector construit des dashboards KPI automatisés, analyse les performances "
                "marketing et commerciales, identifie les clients et segments les plus rentables, "
                "et génère des recommandations data-driven automatiques."
            ),
            system_prompt=VECTOR_SYSTEM_PROMPT,
            accent_color="#2D8659",
        )
        session.add(vector)
        await session.commit()
        print(f"✓ Vector créé (id={vector.id})")


async def seed_personas() -> None:
    """Insère le persona système "Vector" si absent (is_system=True, user_id=NULL).

    system_prompt copié du SYSTEM_PROMPT réel de agent_loop.py pour affichage
    fidèle côté UI — le chat, lui, continue d'utiliser SYSTEM_PROMPT
    directement pour ce persona (voir agent_loop.py) afin de rester toujours
    à jour si ce prompt évolue sans nouveau seed.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Persona).where(
                Persona.is_system.is_(True), Persona.name == VECTOR_PERSONA_NAME
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"✓ Persona système Vector existe déjà (id={existing.id})")
            return

        vector_persona = Persona(
            user_id=None,
            name=VECTOR_PERSONA_NAME,
            description="L'assistant par défaut, spécialisé en analyse de données.",
            system_prompt=SYSTEM_PROMPT,
            icon="Bot",
            color="#2D8659",
            is_system=True,
            is_active=True,
        )
        session.add(vector_persona)
        await session.commit()
        print(f"✓ Persona système Vector créé (id={vector_persona.id})")


async def main() -> None:
    await seed_agents()
    await seed_personas()


if __name__ == "__main__":
    asyncio.run(main())
