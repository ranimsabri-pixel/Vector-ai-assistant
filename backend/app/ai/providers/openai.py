"""
Implémentation concrète du LLMProvider avec l'API OpenAI.
"""
import asyncio
from collections.abc import AsyncIterator
from typing import Any

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.ai.providers.base import LLMProvider, Message
from app.ai.providers.mock_responses import (
    mock_chat_answer,
    mock_embedding_for,
    mock_structured_output,
    mock_usage,
)
from app.core.config import get_settings

settings = get_settings()

# Retry sur erreurs réseau/quota, exponentiel, max 3 essais
_retry_decorator = retry(
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)


class OpenAIProvider(LLMProvider):
    """Implémentation OpenAI du LLMProvider."""

    def __init__(self, api_key: str | None = None):
        # S5 J52 : en mode mock, aucun client OpenAI reel n'est cree -- aucun
        # appel reseau ne peut donc partir par erreur, meme si un chemin de
        # code oublie de checker self._mock avant d'utiliser self.client.
        self._mock = settings.USE_MOCK_LLM
        self.client = (
            None if self._mock else AsyncOpenAI(api_key=api_key or settings.OPENAI_API_KEY)
        )
        self.default_chat_model = settings.OPENAI_MODEL_CHAT
        self.default_embed_model = settings.OPENAI_MODEL_EMBED

    @_retry_decorator
    async def chat(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        usage_holder: dict[str, Any] | None = None,
    ) -> str:
        """Chat non-streaming : retourne la réponse complète.

        usage_holder (S5 J41+ Feature 2) : dict optionnel rempli en sortie
        avec prompt_tokens/completion_tokens/total_tokens/model, si fourni.
        """
        if self._mock:
            answer = mock_chat_answer([m.to_dict() for m in messages])
            if usage_holder is not None:
                usage_holder.update(mock_usage(answer, self.default_chat_model))
            return answer

        params: dict[str, Any] = {
            "model": model or self.default_chat_model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
        }
        if max_tokens is not None:
            params["max_tokens"] = max_tokens

        response = await self.client.chat.completions.create(**params)
        if usage_holder is not None and response.usage is not None:
            usage_holder["prompt_tokens"] = response.usage.prompt_tokens
            usage_holder["completion_tokens"] = response.usage.completion_tokens
            usage_holder["total_tokens"] = response.usage.total_tokens
            usage_holder["model"] = response.model
        return response.choices[0].message.content or ""

    async def chat_stream(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        usage_holder: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """Chat streaming : yield les tokens un par un.

        usage_holder (S5 J41+ Feature 2) : si fourni, demande a l'API
        d'inclure l'usage dans le stream (stream_options include_usage) et
        remplit le dict en sortie une fois le stream termine. Le dernier
        chunk contenant l'usage n'a AUCUN choice (choices == []) — il ne
        faut donc jamais indexer chunk.choices[0] sans garde.
        """
        if self._mock:
            answer = mock_chat_answer([m.to_dict() for m in messages])
            for word in answer.split(" "):
                yield word + " "
                await asyncio.sleep(0)  # laisse la boucle d'evenements respirer
            if usage_holder is not None:
                usage_holder.update(mock_usage(answer, self.default_chat_model))
            return

        params: dict[str, Any] = {
            "model": model or self.default_chat_model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if usage_holder is not None:
            params["stream_options"] = {"include_usage": True}

        stream = await self.client.chat.completions.create(**params)
        async for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
            if usage_holder is not None and chunk.usage is not None:
                usage_holder["prompt_tokens"] = chunk.usage.prompt_tokens
                usage_holder["completion_tokens"] = chunk.usage.completion_tokens
                usage_holder["total_tokens"] = chunk.usage.total_tokens
                usage_holder["model"] = model or self.default_chat_model

    @_retry_decorator
    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Embed une liste de textes en batch."""
        if self._mock:
            return [mock_embedding_for(t) for t in texts]

        response = await self.client.embeddings.create(
            model=model or self.default_embed_model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    @_retry_decorator
    async def structured_output(
        self,
        messages: list[Message],
        json_schema: dict[str, Any],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """
        Génère du JSON strict via response_format json_schema.
        Le json_schema doit suivre la spec OpenAI :
        {name: str, schema: {...}, strict: bool}
        """
        if self._mock:
            return mock_structured_output(json_schema)

        response = await self.client.chat.completions.create(
            model=model or self.default_chat_model,
            messages=[m.to_dict() for m in messages],
            temperature=temperature,
            response_format={
                "type": "json_schema",
                "json_schema": json_schema,
            },
        )
        import json
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    @_retry_decorator
    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """
        Appel chat avec support tool calling.

        Le LLM peut décider d'appeler un ou plusieurs outils en réponse.

        Args:
            messages: format OpenAI brut (role + content, parfois tool_calls)
            tools: schémas d'outils au format OpenAI (TOOLS_SCHEMA)
            model: nom du modèle (défaut: settings.OPENAI_MODEL_CHAT)
            temperature: créativité du LLM

        Returns:
            dict avec :
            - content: str | None (texte de réponse si pas de tool call)
            - tool_calls: list[dict] (liste des outils à appeler)
            - finish_reason: str
            - usage: dict | None (prompt_tokens/completion_tokens/total_tokens/model)
        """
        used_model = model or self.default_chat_model

        if self._mock:
            # Toujours une reponse finale, jamais de tool call : suffisant
            # pour les specs J52 (aucune n'exerce le tool calling en soi).
            answer = mock_chat_answer(messages)
            return {
                "content": answer,
                "tool_calls": [],
                "finish_reason": "stop",
                "usage": mock_usage(answer, used_model),
            }

        response = await self.client.chat.completions.create(
            model=used_model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=temperature,
        )

        choice = response.choices[0]
        message = choice.message

        # Format de retour normalisé
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,  # string JSON
                })

        usage = None
        if response.usage is not None:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "model": response.model or used_model,
            }

        return {
            "content": message.content,
            "tool_calls": tool_calls,
            "finish_reason": choice.finish_reason,
            "usage": usage,
        }
