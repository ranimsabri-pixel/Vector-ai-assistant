"""
Vector — Commando IA Analyse de Données
Point d'entrée FastAPI
"""
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import (
    agent,
    agents,
    auth,
    chat,
    conversations,
    corpus,
    dashboards,
    datasets,
    documents,
    messages,
    personas,
    rag,
    saved_dashboards,
    shares,
    users,
)
from app.core.config import get_settings
from app.core.limiter import limiter
from app.services.demo_cleanup import cleanup_inactive_accounts

settings = get_settings()
logger = logging.getLogger(__name__)

# S5 J55 : nettoyage des comptes démo inactifs (>48h) — Render free tier
# n'a pas de cron séparé, tourne dans ce même process (cf
# app/services/demo_cleanup.py). Toutes les 6h : assez frequent pour ne
# pas laisser trainer trop de comptes, assez rare pour rester negligeable
# en charge sur un tier a 0.1 vCPU.
_scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _scheduler.add_job(cleanup_inactive_accounts, "interval", hours=6)
    _scheduler.start()
    try:
        yield
    finally:
        _scheduler.shutdown(wait=False)


app = FastAPI(
    title="Vector API",
    description="Commando IA d'analyse de données — backend FastAPI",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiting in-memory (S5 J55) — voir app/core/limiter.py
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS : autoriser le frontend à appeler le backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(agents.router)
app.include_router(chat.router)
app.include_router(datasets.router)
app.include_router(dashboards.router)
app.include_router(agent.router)
app.include_router(documents.router)
app.include_router(rag.router)
app.include_router(conversations.router)
app.include_router(messages.router)
app.include_router(corpus.router)
app.include_router(personas.router)
app.include_router(saved_dashboards.router)
app.include_router(shares.router)
app.include_router(shares.public_router)
@app.get("/health", tags=["meta"])
async def health_check() -> dict:
    """Endpoint de vérification de santé."""
    return {"status": "ok", "service": "vector-backend", "version": "0.1.0"}


@app.get("/", tags=["meta"])
async def root() -> dict:
    """Endpoint racine."""
    return {
        "message": "Vector API — Commando IA Analyse de Données",
        "docs": "/docs",
    }
