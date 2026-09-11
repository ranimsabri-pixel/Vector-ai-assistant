"""Rate limiting in-memory (S5 J55) — démo publique Render, tier gratuit
mono-instance. slowapi/limits gardent l'état en mémoire du process ; pas
de state partagé nécessaire puisque Render free tier n'autorise qu'une
seule instance (cf docs/DEPLOYMENT_RENDER.md décision D). Remplace le
Redis jamais branché (voir suppression de REDIS_URL, même sprint).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

limiter = Limiter(key_func=get_remote_address, enabled=get_settings().RATE_LIMIT_ENABLED)
