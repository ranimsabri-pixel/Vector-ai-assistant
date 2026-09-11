"""
Configuration du moteur SQLAlchemy async et de la fabrique de sessions.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

# DATABASE_URL reste un "postgresql://..." standard (Neon, compat
# psql/DBeaver) -- meme normalisation qu'en Alembic (migrations/env.py) :
# driver asyncpg force, query params libpq (sslmode, channel_binding...)
# retires (asyncpg ne les parse pas -- TypeError: connect() got an
# unexpected keyword argument 'sslmode'), SSL active via connect_args
# uniquement en dehors du dev local (docker-compose n'a pas de TLS).
_db_url = make_url(settings.DATABASE_URL)
if _db_url.drivername == "postgresql":
    _db_url = _db_url.set(drivername="postgresql+asyncpg")
_db_url = _db_url.difference_update_query(
    ["sslmode", "channel_binding", "sslcert", "sslkey", "sslrootcert"]
)

_is_local_db = _db_url.host in {"localhost", "127.0.0.1", "db", "postgres", "pgvector"}
_engine_kwargs = {
    "echo": settings.LOG_LEVEL == "DEBUG",
    "pool_size": 5,
    "max_overflow": 10,
    "pool_pre_ping": True,
}
if not _is_local_db:
    _engine_kwargs["connect_args"] = {"ssl": "require"}

# --- Moteur async pour FastAPI ---
engine = create_async_engine(_db_url.render_as_string(hide_password=False), **_engine_kwargs)

# --- Fabrique de sessions ---
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency FastAPI : fournit une session DB à un endpoint,
    et la ferme proprement après la requête (même en cas d'erreur).
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
