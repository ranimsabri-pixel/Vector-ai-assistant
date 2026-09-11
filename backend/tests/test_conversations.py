"""Tests des endpoints Conversations : CRUD, ownership, titre auto, stats."""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_conversation(client: AsyncClient, auth_headers: dict):
    """Creation d'une conversation avec titre explicite."""
    response = await client.post(
        "/conversations",
        headers=auth_headers,
        json={"title": "Ma conversation de test"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Ma conversation de test"
    assert data["messages"] == []


@pytest.mark.asyncio
async def test_create_conversation_default_title(client: AsyncClient, auth_headers: dict):
    """Sans titre fourni, la conversation prend le titre par defaut."""
    response = await client.post("/conversations", headers=auth_headers, json={})
    assert response.status_code == 201
    assert response.json()["title"] == "Nouvelle discussion"


@pytest.mark.asyncio
async def test_create_conversation_requires_auth(client: AsyncClient):
    """Sans token, la creation est refusee."""
    response = await client.post("/conversations", json={"title": "X"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_conversations_own_only(
    client: AsyncClient, auth_headers: dict, register_second_user
):
    """Le listing ne retourne que les conversations de l'utilisateur courant."""
    await client.post(
        "/conversations", headers=auth_headers, json={"title": "Conversation de A"}
    )

    other = await register_second_user()
    await client.post(
        "/conversations", headers=other["headers"], json={"title": "Conversation de B"}
    )

    response = await client.get("/conversations", headers=auth_headers)
    assert response.status_code == 200
    titles = [c["title"] for c in response.json()]
    assert "Conversation de A" in titles
    assert "Conversation de B" not in titles


@pytest.mark.asyncio
async def test_get_conversation_not_owned_returns_404(
    client: AsyncClient, auth_headers: dict, register_second_user
):
    """Un utilisateur ne peut pas lire la conversation d'un autre (404, pas 403,
    pour ne pas confirmer l'existence de la ressource)."""
    created = await client.post(
        "/conversations", headers=auth_headers, json={"title": "Privee"}
    )
    conv_id = created.json()["id"]

    other = await register_second_user()
    response = await client.get(f"/conversations/{conv_id}", headers=other["headers"])
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_conversation_not_owned_returns_404(
    client: AsyncClient, auth_headers: dict, register_second_user
):
    """Un utilisateur ne peut pas supprimer la conversation d'un autre."""
    created = await client.post(
        "/conversations", headers=auth_headers, json={"title": "A proteger"}
    )
    conv_id = created.json()["id"]

    other = await register_second_user()
    response = await client.delete(f"/conversations/{conv_id}", headers=other["headers"])
    assert response.status_code == 404

    # Le proprietaire, lui, peut la supprimer
    response = await client.delete(f"/conversations/{conv_id}", headers=auth_headers)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_append_message_and_retrieve(client: AsyncClient, auth_headers: dict):
    """Un message ajoute est bien present a la relecture de la conversation."""
    created = await client.post("/conversations", headers=auth_headers, json={})
    conv_id = created.json()["id"]

    response = await client.post(
        f"/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"role": "user", "message_kind": "user", "content": "Bonjour Vector"},
    )
    assert response.status_code == 201

    detail = await client.get(f"/conversations/{conv_id}", headers=auth_headers)
    contents = [m["content"] for m in detail.json()["messages"]]
    assert "Bonjour Vector" in contents


@pytest.mark.asyncio
async def test_generate_title_noop_below_two_messages(
    client: AsyncClient, auth_headers: dict
):
    """Sans au moins 2 messages (question + reponse), le titre par defaut
    n'est pas touche (pas d'appel LLM declenche)."""
    created = await client.post("/conversations", headers=auth_headers, json={})
    conv_id = created.json()["id"]

    response = await client.post(
        f"/conversations/{conv_id}/generate-title", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Nouvelle discussion"


@pytest.mark.asyncio
async def test_generate_title_never_overwrites_custom_title(
    client: AsyncClient, auth_headers: dict
):
    """Un titre deja personnalise n'est jamais ecrase par la generation auto,
    meme avec des messages presents."""
    created = await client.post(
        "/conversations", headers=auth_headers, json={"title": "Mon analyse Q3"}
    )
    conv_id = created.json()["id"]

    await client.post(
        f"/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"role": "user", "message_kind": "user", "content": "Question"},
    )
    await client.post(
        f"/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"role": "assistant", "message_kind": "agent", "content": "Reponse"},
    )

    response = await client.post(
        f"/conversations/{conv_id}/generate-title", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Mon analyse Q3"


@pytest.mark.asyncio
async def test_generate_title_calls_llm_when_eligible(
    client: AsyncClient, auth_headers: dict
):
    """Avec un titre par defaut et 2+ messages, le titre est remplace par la
    reponse du LLM (mocke pour eviter un vrai appel OpenAI)."""
    created = await client.post("/conversations", headers=auth_headers, json={})
    conv_id = created.json()["id"]

    await client.post(
        f"/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"role": "user", "message_kind": "user", "content": "Question"},
    )
    await client.post(
        f"/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"role": "assistant", "message_kind": "agent", "content": "Reponse"},
    )

    with patch(
        "app.ai.providers.openai.OpenAIProvider.chat",
        new=AsyncMock(return_value="Titre genere par le LLM"),
    ):
        response = await client.post(
            f"/conversations/{conv_id}/generate-title", headers=auth_headers
        )
    assert response.status_code == 200
    assert response.json()["title"] == "Titre genere par le LLM"


@pytest.mark.asyncio
async def test_conversation_stats_empty(client: AsyncClient, auth_headers: dict):
    """Stats d'une conversation sans message : tout a zero, pas d'erreur."""
    created = await client.post("/conversations", headers=auth_headers, json={})
    conv_id = created.json()["id"]

    response = await client.get(f"/conversations/{conv_id}/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_messages"] == 0
    assert data["total_tokens"] == 0
    assert data["total_cost_usd"] == 0.0


@pytest.mark.asyncio
async def test_conversation_stats_aggregates_tokens(
    client: AsyncClient, auth_headers: dict
):
    """Les tokens/cout de plusieurs messages assistant sont bien agreges."""
    created = await client.post("/conversations", headers=auth_headers, json={})
    conv_id = created.json()["id"]

    for prompt_tok, completion_tok, cost in [(100, 20, 0.001), (200, 30, 0.002)]:
        await client.post(
            f"/conversations/{conv_id}/messages",
            headers=auth_headers,
            json={
                "role": "assistant",
                "message_kind": "agent",
                "content": "Reponse",
                "prompt_tokens": prompt_tok,
                "completion_tokens": completion_tok,
                "total_tokens": prompt_tok + completion_tok,
                "cost_usd": cost,
                "model_used": "gpt-4o",
            },
        )

    response = await client.get(f"/conversations/{conv_id}/stats", headers=auth_headers)
    data = response.json()
    assert data["total_messages"] == 2
    assert data["total_prompt_tokens"] == 300
    assert data["total_completion_tokens"] == 50
    assert data["total_tokens"] == 350
    assert abs(data["total_cost_usd"] - 0.003) < 1e-9


@pytest.mark.asyncio
async def test_update_conversation_title_via_patch(client: AsyncClient, auth_headers: dict):
    """PATCH /conversations/{id} renomme la conversation."""
    created = await client.post("/conversations", headers=auth_headers, json={})
    conv_id = created.json()["id"]

    response = await client.patch(
        f"/conversations/{conv_id}", headers=auth_headers, json={"title": "Nouveau titre"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Nouveau titre"


@pytest.mark.asyncio
async def test_toggle_pin_conversation(client: AsyncClient, auth_headers: dict):
    """PATCH /conversations/{id} epingle/desepingle la conversation."""
    created = await client.post("/conversations", headers=auth_headers, json={})
    conv_id = created.json()["id"]
    assert created.json()["is_pinned"] is False

    response = await client.patch(
        f"/conversations/{conv_id}", headers=auth_headers, json={"is_pinned": True}
    )
    assert response.status_code == 200
    assert response.json()["is_pinned"] is True


@pytest.mark.asyncio
async def test_update_message_feedback(client: AsyncClient, auth_headers: dict):
    """PATCH /messages/{id}/feedback enregistre puis retire un feedback."""
    created = await client.post("/conversations", headers=auth_headers, json={})
    conv_id = created.json()["id"]

    msg = await client.post(
        f"/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"role": "assistant", "message_kind": "agent", "content": "Reponse"},
    )
    message_id = msg.json()["id"]

    response = await client.patch(
        f"/messages/{message_id}/feedback", headers=auth_headers, json={"feedback": "positive"}
    )
    assert response.status_code == 200
    assert response.json()["feedback"] == "positive"

    response = await client.patch(
        f"/messages/{message_id}/feedback", headers=auth_headers, json={"feedback": None}
    )
    assert response.status_code == 200
    assert response.json()["feedback"] is None


@pytest.mark.asyncio
async def test_update_message_feedback_not_owned_returns_404(
    client: AsyncClient, auth_headers: dict, register_second_user
):
    """Impossible de mettre un feedback sur le message d'un autre utilisateur."""
    created = await client.post("/conversations", headers=auth_headers, json={})
    conv_id = created.json()["id"]
    msg = await client.post(
        f"/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"role": "assistant", "message_kind": "agent", "content": "Reponse"},
    )
    message_id = msg.json()["id"]

    other = await register_second_user()
    response = await client.patch(
        f"/messages/{message_id}/feedback",
        headers=other["headers"],
        json={"feedback": "positive"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_message(client: AsyncClient, auth_headers: dict):
    """DELETE /messages/{id} retire le message de la conversation (regeneration)."""
    created = await client.post("/conversations", headers=auth_headers, json={})
    conv_id = created.json()["id"]
    msg = await client.post(
        f"/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"role": "assistant", "message_kind": "agent", "content": "A regenerer"},
    )
    message_id = msg.json()["id"]

    response = await client.delete(f"/messages/{message_id}", headers=auth_headers)
    assert response.status_code == 204

    detail = await client.get(f"/conversations/{conv_id}", headers=auth_headers)
    contents = [m["content"] for m in detail.json()["messages"]]
    assert "A regenerer" not in contents
