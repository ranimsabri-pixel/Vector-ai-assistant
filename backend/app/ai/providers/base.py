"""
Interface abstraite pour les providers LLM.
Tous les fournisseurs (OpenAI, Anthropic, etc.) doivent implémenter cette interface.
"""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class Message:
    """Un message dans une conversation."""
    def __init__(self, role: str, content: str):
        self.role = role  # 'system' | 'user' | 'assistant'
        self.content = content

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class LLMProvider(ABC):
    """
    Interface abstraite pour un fournisseur de LLM.
    Toute implémentation concrète (OpenAI, Anthropic, etc.) doit hériter de cette classe.
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """
        Envoie une liste de messages, retourne la réponse complète (non-streaming).
        """
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """
        Envoie une liste de messages, yield les tokens un par un en streaming.
        """
        ...

    @abstractmethod
    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """
        Convertit une liste de textes en vecteurs d'embeddings.
        Retourne une liste de vecteurs (dimension dépendante du modèle).
        """
        ...

    @abstractmethod
    async def structured_output(
        self,
        messages: list[Message],
        json_schema: dict[str, Any],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """
        Génère une sortie JSON qui respecte le schéma fourni.
        Idéal pour : extraire des données structurées, lister des KPIs, etc.
        """
        ...
