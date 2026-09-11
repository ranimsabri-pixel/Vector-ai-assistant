"""Tests du provider OpenAI avec mocks."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.providers.base import Message
from app.ai.providers.openai import OpenAIProvider


@pytest.mark.asyncio
async def test_chat_returns_content():
    """chat() retourne le contenu de la réponse OpenAI."""
    provider = OpenAIProvider(api_key="fake")

    # Mock la réponse OpenAI
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Bonjour !"

    provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = await provider.chat([Message("user", "Salut")])
    assert result == "Bonjour !"


@pytest.mark.asyncio
async def test_chat_stream_yields_tokens():
    """chat_stream() yield les tokens d'un stream OpenAI."""
    provider = OpenAIProvider(api_key="fake")

    # Construire un faux stream
    async def fake_stream():
        for content in ["Hello", " ", "world"]:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = content
            yield chunk

    provider.client.chat.completions.create = AsyncMock(return_value=fake_stream())

    tokens = []
    async for token in provider.chat_stream([Message("user", "Hi")]):
        tokens.append(token)

    assert tokens == ["Hello", " ", "world"]


@pytest.mark.asyncio
async def test_embed_returns_vectors():
    """embed() retourne les vecteurs d'embeddings."""
    provider = OpenAIProvider(api_key="fake")

    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]

    provider.client.embeddings.create = AsyncMock(return_value=mock_response)

    result = await provider.embed(["text"])
    assert result == [[0.1, 0.2, 0.3]]