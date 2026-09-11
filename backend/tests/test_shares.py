"""Tests du partage public de conversations (S5 J48)."""
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.conversation_share import ConversationShare


async def _create_conversation(client: AsyncClient, auth_headers: dict) -> str:
    response = await client.post(
        "/conversations", headers=auth_headers, json={"title": "Conversation partagée"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _add_message(
    client: AsyncClient,
    auth_headers: dict,
    conv_id: str,
    role: str,
    content: str,
    sources: list[dict] | None = None,
    attachments: list[dict] | None = None,
) -> None:
    response = await client.post(
        f"/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={
            "role": role,
            "message_kind": "user" if role == "user" else "agent",
            "content": content,
            "sources": sources,
            "attachments": attachments,
            "prompt_tokens": 42 if role == "assistant" else None,
            "completion_tokens": 17 if role == "assistant" else None,
            "cost_usd": 0.0021 if role == "assistant" else None,
            "model_used": "gpt-4o-mini" if role == "assistant" else None,
        },
    )
    assert response.status_code == 201, response.text


# Attachment shape produite par image_attachments.save_image_attachment —
# on la construit à la main plutôt que d'uploader une vraie image (le
# endpoint de partage ne lit que le JSONB Message.attachments, peu importe
# comment il a été peuplé).
_FAKE_IMAGE_ATTACHMENT = {
    "type": "image",
    "attachment_id": str(uuid4()),
    "file_name": "rapport-confidentiel-Q3.png",
    "mime_type": "image/png",
    "file_size": 123456,
    "width": 800,
    "height": 600,
    "storage_path": "attachments/some-user-id/some-conv-id/secret-uuid.png",
    "preview_base64": "data:image/png;base64,iVBORw0KGgoFAKEPREVIEW==",
}


# ============================================================
# POST /conversations/{id}/share
# ============================================================

@pytest.mark.asyncio
async def test_create_share(client: AsyncClient, auth_headers: dict):
    conv_id = await _create_conversation(client, auth_headers)
    response = await client.post(f"/conversations/{conv_id}/share", headers=auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["share_token"]) >= 32
    assert data["share_token"] in data["share_url"]
    assert f"/share?token={data['share_token']}" in data["share_url"]


@pytest.mark.asyncio
async def test_create_share_not_owner_404(
    client: AsyncClient, auth_headers: dict, register_second_user
):
    conv_id = await _create_conversation(client, auth_headers)
    other = await register_second_user()
    response = await client.post(f"/conversations/{conv_id}/share", headers=other["headers"])
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_share_returns_existing_active(client: AsyncClient, auth_headers: dict):
    conv_id = await _create_conversation(client, auth_headers)
    first = await client.post(f"/conversations/{conv_id}/share", headers=auth_headers)
    second = await client.post(f"/conversations/{conv_id}/share", headers=auth_headers)
    assert first.json()["share_token"] == second.json()["share_token"]


# ============================================================
# GET /share/{token} — endpoint public
# ============================================================

@pytest.mark.asyncio
async def test_get_share_public_no_auth(client: AsyncClient, auth_headers: dict):
    conv_id = await _create_conversation(client, auth_headers)
    await _add_message(client, auth_headers, conv_id, "user", "Bonjour Vector")
    share = await client.post(f"/conversations/{conv_id}/share", headers=auth_headers)
    token = share.json()["share_token"]

    # Aucun header Authorization envoyé.
    response = await client.get(f"/share/{token}")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["title"] == "Conversation partagée"
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "Bonjour Vector"


@pytest.mark.asyncio
async def test_get_share_invalid_token_404(client: AsyncClient):
    response = await client.get("/share/ce-token-nexiste-pas")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_share_revoked_404(client: AsyncClient, auth_headers: dict):
    conv_id = await _create_conversation(client, auth_headers)
    share = await client.post(f"/conversations/{conv_id}/share", headers=auth_headers)
    token = share.json()["share_token"]

    revoke = await client.delete(f"/conversations/{conv_id}/share", headers=auth_headers)
    assert revoke.status_code == 204

    response = await client.get(f"/share/{token}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_share_exposes_only_safe_fields(client: AsyncClient, auth_headers: dict):
    conv_id = await _create_conversation(client, auth_headers)
    await _add_message(
        client,
        auth_headers,
        conv_id,
        "assistant",
        "Voici la réponse",
        sources=[
            {
                "chunk_id": str(uuid4()),
                "document_id": str(uuid4()),
                "document_name": "rapport.pdf",
                "document_file_type": "pdf",
                "page_number": 3,
                "content_preview": "extrait pertinent du document",
                "similarity": 0.87,
            }
        ],
    )
    share = await client.post(f"/conversations/{conv_id}/share", headers=auth_headers)
    token = share.json()["share_token"]

    response = await client.get(f"/share/{token}")
    raw = response.text

    # Rien d'interne ne doit fuiter, ni au niveau message ni au niveau source.
    for forbidden in (
        "cost_usd", "prompt_tokens", "completion_tokens", "model_used",
        "tool_calls", "chunk_id", "document_id", "similarity", "@example.com",
    ):
        assert forbidden not in raw, f"'{forbidden}' ne devrait jamais apparaître dans le JSON public"

    data = response.json()
    source = data["messages"][0]["sources"][0]
    assert source["document_name"] == "rapport.pdf"
    assert source["page_number"] == 3
    assert source["content_preview"] == "extrait pertinent du document"
    assert set(source.keys()) == {"document_name", "page_number", "content_preview"}


@pytest.mark.asyncio
async def test_get_share_filters_out_status_and_tool_messages(
    client: AsyncClient, auth_headers: dict
):
    conv_id = await _create_conversation(client, auth_headers)
    await _add_message(client, auth_headers, conv_id, "user", "Question visible")
    # Bulle "tool" : artefact d'exécution interne, ne doit pas apparaître publiquement.
    response = await client.post(
        f"/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"role": "assistant", "message_kind": "tool", "content": "Outil exécuté"},
    )
    assert response.status_code == 201

    share = await client.post(f"/conversations/{conv_id}/share", headers=auth_headers)
    token = share.json()["share_token"]

    result = await client.get(f"/share/{token}")
    contents = [m["content"] for m in result.json()["messages"]]
    assert "Question visible" in contents
    assert "Outil exécuté" not in contents


# ============================================================
# DELETE /conversations/{id}/share
# ============================================================

@pytest.mark.asyncio
async def test_delete_share_owner(client: AsyncClient, auth_headers: dict):
    conv_id = await _create_conversation(client, auth_headers)
    await client.post(f"/conversations/{conv_id}/share", headers=auth_headers)
    response = await client.delete(f"/conversations/{conv_id}/share", headers=auth_headers)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_share_not_owner_404(
    client: AsyncClient, auth_headers: dict, register_second_user
):
    conv_id = await _create_conversation(client, auth_headers)
    await client.post(f"/conversations/{conv_id}/share", headers=auth_headers)
    other = await register_second_user()
    response = await client.delete(f"/conversations/{conv_id}/share", headers=other["headers"])
    assert response.status_code == 404


# ============================================================
# expires_at (colonne prête pour V2, pas exposée en création en V1 —
# on la renseigne directement via la DB pour tester le comportement)
# ============================================================

@pytest.mark.asyncio
async def test_expired_share_404(client: AsyncClient, auth_headers: dict, db_session):
    conv_id = await _create_conversation(client, auth_headers)
    share_resp = await client.post(f"/conversations/{conv_id}/share", headers=auth_headers)
    token = share_resp.json()["share_token"]

    result = await db_session.execute(
        select(ConversationShare).where(ConversationShare.share_token == token)
    )
    share = result.scalar_one()
    share.expires_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.commit()

    response = await client.get(f"/share/{token}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_share_token_is_cryptographically_random(client: AsyncClient, auth_headers: dict):
    """Le token ne doit jamais être un UUID (prévisible), et être unique
    entre deux conversations différentes."""
    conv_a = await _create_conversation(client, auth_headers)
    conv_b = await _create_conversation(client, auth_headers)
    share_a = await client.post(f"/conversations/{conv_a}/share", headers=auth_headers)
    share_b = await client.post(f"/conversations/{conv_b}/share", headers=auth_headers)

    token_a = share_a.json()["share_token"]
    token_b = share_b.json()["share_token"]
    assert token_a != token_b

    with pytest.raises(ValueError):
        UUID(token_a)


# ============================================================
# include_attachments (NEW J49) — opt-in, sécurité par défaut
# ============================================================

@pytest.mark.asyncio
async def test_share_without_attachments_hides_previews(
    client: AsyncClient, auth_headers: dict
):
    """Comportement par défaut (case décochée) : ni l'image, ni son nom de
    fichier, mais un signal has_hidden_attachments pour le placeholder."""
    conv_id = await _create_conversation(client, auth_headers)
    await _add_message(
        client, auth_headers, conv_id, "assistant", "Voici l'image",
        attachments=[_FAKE_IMAGE_ATTACHMENT],
    )
    # include_attachments absent du body -> défaut False côté schema Pydantic.
    share = await client.post(f"/conversations/{conv_id}/share", headers=auth_headers)
    assert share.json()["include_attachments"] is False
    token = share.json()["share_token"]

    response = await client.get(f"/share/{token}")
    message = response.json()["messages"][0]
    assert message["attachments"] is None
    assert message["has_hidden_attachments"] is True
    assert "rapport-confidentiel-Q3.png" not in response.text
    assert "FAKEPREVIEW" not in response.text


@pytest.mark.asyncio
async def test_share_with_attachments_exposes_previews(
    client: AsyncClient, auth_headers: dict
):
    """Case cochée (include_attachments=True) : la miniature apparaît,
    has_hidden_attachments repasse à False."""
    conv_id = await _create_conversation(client, auth_headers)
    await _add_message(
        client, auth_headers, conv_id, "assistant", "Voici l'image",
        attachments=[_FAKE_IMAGE_ATTACHMENT],
    )
    share = await client.post(
        f"/conversations/{conv_id}/share",
        headers=auth_headers,
        json={"include_attachments": True},
    )
    assert share.json()["include_attachments"] is True
    token = share.json()["share_token"]

    response = await client.get(f"/share/{token}")
    message = response.json()["messages"][0]
    assert message["has_hidden_attachments"] is False
    assert len(message["attachments"]) == 1
    att = message["attachments"][0]
    assert att["preview_base64"] == "data:image/png;base64,iVBORw0KGgoFAKEPREVIEW=="
    assert att["file_name"] == "rapport-confidentiel-Q3.png"
    assert att["mime_type"] == "image/png"


@pytest.mark.asyncio
async def test_share_never_exposes_storage_path(client: AsyncClient, auth_headers: dict):
    """Même avec include_attachments=True, le chemin disque interne et les
    métadonnées non nécessaires au rendu ne doivent jamais fuiter."""
    conv_id = await _create_conversation(client, auth_headers)
    await _add_message(
        client, auth_headers, conv_id, "assistant", "Voici l'image",
        attachments=[_FAKE_IMAGE_ATTACHMENT],
    )
    share = await client.post(
        f"/conversations/{conv_id}/share",
        headers=auth_headers,
        json={"include_attachments": True},
    )
    token = share.json()["share_token"]

    response = await client.get(f"/share/{token}")
    raw = response.text
    for forbidden in ("storage_path", "attachment_id", "file_size", "width", "height", "some-user-id"):
        assert forbidden not in raw, f"'{forbidden}' ne devrait jamais apparaître dans le JSON public"

    att = response.json()["messages"][0]["attachments"][0]
    assert set(att.keys()) == {"type", "file_name", "mime_type", "preview_base64"}


@pytest.mark.asyncio
async def test_existing_shares_default_to_false_attachments(
    client: AsyncClient, auth_headers: dict, db_session
):
    """Compatibilité ascendante : un share créé avant cette migration (donc
    sans valeur explicite) doit défaulter à False, jamais exposer d'image
    par accident sur d'anciens liens déjà partagés."""
    conv_id = await _create_conversation(client, auth_headers)
    await _add_message(
        client, auth_headers, conv_id, "assistant", "Voici l'image",
        attachments=[_FAKE_IMAGE_ATTACHMENT],
    )
    share = await client.post(f"/conversations/{conv_id}/share", headers=auth_headers)
    token = share.json()["share_token"]

    result = await db_session.execute(
        select(ConversationShare).where(ConversationShare.share_token == token)
    )
    db_share = result.scalar_one()
    assert db_share.include_attachments is False

    response = await client.get(f"/share/{token}")
    assert response.json()["messages"][0]["attachments"] is None
    assert response.json()["messages"][0]["has_hidden_attachments"] is True
