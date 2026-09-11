"""
Configuration Alembic — version async, intégrée avec nos settings et modèles Vector.
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import settings et Base
from app.core.config import get_settings
from app.db.base import Base

# Import de tous les modèles pour qu'ils soient enregistrés dans Base.metadata
from app.db import models  # noqa: F401

config = context.config

# Injection dynamique de l'URL depuis .env
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Configure le logging Alembic
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata : Alembic compare ceci avec l'état actuel de la base
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Mode offline : génère du SQL sans se connecter à la base."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Exécute les migrations sur une connexion synchrone."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Mode async : crée un moteur async et applique les migrations."""
    section = config.get_section(config.config_ini_section, {})

    # Neon (et DATABASE_URL cote Render en general) fournit "postgresql://"
    # standard, sans driver explicite -- SQLAlchemy resout ca en psycopg2
    # sync par defaut, incompatible avec async_engine_from_config ci-dessous.
    # make_url()+.set() (pas de str.replace()) pour ne pas casser les query
    # params (ex: ?sslmode=require). Ne touche pas une URL qui a deja un
    # driver explicite (+asyncpg, +psycopg2...).
    url = make_url(section["sqlalchemy.url"])
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+asyncpg")

    # sslmode/channel_binding/sslcert/sslkey/sslrootcert sont des
    # conventions libpq (psycopg2) qu'asyncpg ne parse pas -- TypeError:
    # connect() got an unexpected keyword argument 'sslmode' si on les
    # laisse dans l'URL. SSL est active plus bas via connect_args
    # (API native asyncpg) a la place de ces query params.
    url = url.difference_update_query(
        ["sslmode", "channel_binding", "sslcert", "sslkey", "sslrootcert"]
    )
    section["sqlalchemy.url"] = url.render_as_string(hide_password=False)

    # SSL n'est requis qu'en production (Neon, RDS, etc.). En dev local,
    # docker-compose expose Postgres sans TLS (bridge network isolé), et
    # forcer ssl="require" fait échouer la connexion avec "rejected SSL
    # upgrade".
    is_local = url.host in {"localhost", "127.0.0.1", "db", "postgres", "pgvector"}
    engine_kwargs = {"prefix": "sqlalchemy.", "poolclass": pool.NullPool}
    if not is_local:
        engine_kwargs["connect_args"] = {"ssl": "require"}
    connectable = async_engine_from_config(section, **engine_kwargs)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Lance les migrations en mode online (connecté à la DB)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()