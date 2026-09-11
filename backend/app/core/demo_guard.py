"""Kill switch démo publique (S5 J55) — DEMO_DISABLED=true coupe les
endpoints coûteux (appels LLM, upload) sans arrêter le conteneur, pour
reprendre la main en cas d'abus pendant la démo Render. Dependency FastAPI
plutôt que middleware global : n'affecte que les routes qui l'incluent
explicitement (chat, upload), jamais login/health/consultation.
"""
from fastapi import HTTPException, status

from app.core.config import get_settings


async def ensure_demo_enabled() -> None:
    if get_settings().DEMO_DISABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Démo temporairement désactivée. Réessayez plus tard.",
        )
