"""
Endpoint WebSocket pour le chat streaming avec un agent (Vector).
"""
from typing import Annotated

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.base import Message
from app.ai.providers.openai import OpenAIProvider
from app.core.security import decode_access_token
from app.db.models.agent import Agent
from app.db.models.user import User
from app.db.session import AsyncSessionLocal
from app.schemas.auth import TokenPayload

router = APIRouter(prefix="/ws", tags=["chat"])


async def get_user_from_token(token: str, db: AsyncSession) -> User | None:
    """Authentifie via un token JWT (utilisé pour WebSocket — pas de header Authorization)."""
    payload = decode_access_token(token)
    if payload is None:
        return None
    try:
        token_data = TokenPayload(**payload)
    except (ValueError, TypeError):
        return None
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user


@router.websocket("/chat")
async def chat_endpoint(
    websocket: WebSocket,
    token: Annotated[str, Query()],
    agent_slug: Annotated[str, Query()] = "vector",
):
    """
    Chat streaming avec un agent IA.

    Authentification : token JWT en query param (WebSocket n'a pas de header Authorization
    standard, donc on passe le token dans l'URL).

    Format messages reçus du client :
      {"type": "user_message", "content": "Bonjour Vector"}

    Format messages envoyés au client :
      {"type": "token", "content": "Bon"}        ← chaque token streamé
      {"type": "token", "content": "jour"}
      ...
      {"type": "done"}                            ← fin de la réponse
      {"type": "error", "detail": "..."}          ← en cas d'erreur
    """
    await websocket.accept()

    async with AsyncSessionLocal() as db:
        # Authentification
        user = await get_user_from_token(token, db)
        if user is None:
            await websocket.send_json({"type": "error", "detail": "Token invalide"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Charger l'agent
        result = await db.execute(select(Agent).where(Agent.slug == agent_slug))
        agent = result.scalar_one_or_none()
        if agent is None:
            await websocket.send_json({"type": "error", "detail": "Agent introuvable"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Historique en mémoire (pour cette session uniquement — la persistance arrivera en S2)
        history: list[Message] = [Message("system", agent.system_prompt)]
        provider = OpenAIProvider()

        try:
            while True:
                payload = await websocket.receive_json()
                if payload.get("type") != "user_message":
                    continue

                user_content = (payload.get("content") or "").strip()
                if not user_content:
                    continue

                history.append(Message("user", user_content))

                # Stream la réponse de Vector
                assistant_content = ""
                try:
                    async for token in provider.chat_stream(history):
                        assistant_content += token
                        await websocket.send_json({"type": "token", "content": token})
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "detail": f"Erreur LLM : {type(e).__name__}",
                    })
                    continue

                history.append(Message("assistant", assistant_content))
                await websocket.send_json({"type": "done"})

        except WebSocketDisconnect:
            return
