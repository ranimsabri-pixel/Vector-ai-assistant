"""
Configuration centralisée — lit le .env via Pydantic Settings.
Utilisation : from app.core.config import get_settings ; settings = get_settings()
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Toutes les variables d'environnement de l'application Vector."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Base de données ---
    DATABASE_URL: str
    DATABASE_URL_SYNC: str

    # --- OpenAI ---
    OPENAI_API_KEY: str
    OPENAI_MODEL_CHAT: str = "gpt-4o"
    OPENAI_MODEL_MINI: str = "gpt-4o-mini"
    OPENAI_MODEL_EMBED: str = "text-embedding-3-small"

    # --- Authentification ---
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 jours
    ALGORITHM: str = "HS256"

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:3000"

    # --- Recherche web (Tavily) ---
    TAVILY_API_KEY: str = ""

    # --- Mock LLM (S5 J52) : bascule OpenAIProvider/WebSearchService sur des
    # reponses deterministes, pour les specs Playwright offline. Ne DOIT
    # jamais valoir true hors des runs e2e:mocked -- defaut false partout
    # ailleurs (dev normal, tests pytest, prod).
    USE_MOCK_LLM: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        """Convertit la chaîne CSV en liste d'origines."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # --- Uploads ---
    UPLOAD_DIR: str = "uploads"
    MAX_DATASET_SIZE_MB: int = 100
    MAX_DOCUMENT_SIZE_MB: int = 10

    # --- Logs ---
    LOG_LEVEL: str = "INFO"

    # --- Démo publique Render (S5 J55) ---
    # Rate limiting (slowapi) : desactive par defaut (dev local, pytest,
    # CI qui enregistrent/uploadent en boucle depuis la meme IP se
    # feraient sinon bloquer par la limite register "5/jour"). Active
    # explicitement via une variable d'env Render en production.
    RATE_LIMIT_ENABLED: bool = False
    # Kill switch : bascule à true (env var Render) pour couper chat/upload
    # sans redéployer, si abus pendant la démo jury.
    DEMO_DISABLED: bool = False
    # Compte pré-rempli, identifiants affichés publiquement sur la landing —
    # PAS un secret. Exclu du nettoyage 48h (app/services/demo_cleanup.py).
    DEMO_ACCOUNT_EMAIL: str = "demo@vector.ai"
    DEMO_ACCOUNT_PASSWORD: str = "VectorDemo2026!"


@lru_cache
def get_settings() -> Settings:
    """
    Retourne une instance Settings, mise en cache (singleton).
    La même instance est partagée partout dans l'app.
    """
    return Settings()
