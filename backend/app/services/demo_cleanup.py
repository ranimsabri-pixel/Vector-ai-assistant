"""Nettoyage des comptes de démo publique (S5 J55) — Render free tier n'a
pas de cron séparé, ce job tourne dans le même process Uvicorn via
APScheduler (cf app/main.py). Supprime les comptes créés il y a plus de
48h, sauf le compte de démo pré-rempli (identifié par email fixe, pas par
un flag DB dédié — évite une migration Alembic pour ce seul besoin).
Hard delete + cascade FK déjà en place (même mécanisme que DELETE /users/me,
app/api/users.py) : vide automatiquement conversations, datasets,
documents, corpora, personas.
"""
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models.user import User
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

INACTIVE_ACCOUNT_MAX_AGE = timedelta(hours=48)


async def cleanup_inactive_accounts() -> int:
    """Supprime les comptes (hors démo) créés il y a plus de 48h.

    Retourne le nombre de comptes supprimés.
    """
    settings = get_settings()
    cutoff = datetime.now(UTC) - INACTIVE_ACCOUNT_MAX_AGE

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(
                User.created_at < cutoff,
                User.email != settings.DEMO_ACCOUNT_EMAIL,
            )
        )
        stale_users = result.scalars().all()

        for user in stale_users:
            await db.delete(user)
        await db.commit()

    if stale_users:
        logger.info("Nettoyage démo : %d compte(s) inactif(s) supprimé(s)", len(stale_users))
    return len(stale_users)
