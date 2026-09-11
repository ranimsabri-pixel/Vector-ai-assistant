"""Tests des Personas (S5 J49) : CRUD, ownership, protection du persona
systeme, validation, association documents/corpus, integration chat."""
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.ai.agent_loop import run_agent
from app.db.models.user import User

VALID_PROMPT = "Tu es un analyste financier. Réponds toujours avec des ratios quand pertinent."


def _persona_payload(**overrides) -> dict:
    payload = {
        "name": "Vector Finance",
        "description": "Analyste financier",
        "system_prompt": VALID_PROMPT,
        "icon": "LineChart",
        "color": "#3B82F6",
    }
    payload.update(overrides)
    return payload


async def _get_system_persona_id(client: AsyncClient, headers: dict) -> str:
    response = await client.get("/personas", headers=headers)
    for p in response.json():
        if p["is_system"]:
            return p["id"]
    raise AssertionError("Persona systeme Vector introuvable — seed manquant ?")


# ============================================================
# CRUD
# ============================================================

@pytest.mark.asyncio
async def test_create_persona(client: AsyncClient, auth_headers: dict):
    response = await client.post("/personas", headers=auth_headers, json=_persona_payload())
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Vector Finance"
    assert data["is_system"] is False
    assert data["system_prompt"] == VALID_PROMPT
    assert data["documents"] == []
    assert data["corpora"] == []


@pytest.mark.asyncio
async def test_list_personas_includes_system_vector(client: AsyncClient, auth_headers: dict):
    await client.post("/personas", headers=auth_headers, json=_persona_payload())
    response = await client.get("/personas", headers=auth_headers)
    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert "Vector Finance" in names
    assert any(p["is_system"] for p in response.json())


@pytest.mark.asyncio
async def test_get_persona_detail(client: AsyncClient, auth_headers: dict):
    created = await client.post("/personas", headers=auth_headers, json=_persona_payload())
    persona_id = created.json()["id"]

    response = await client.get(f"/personas/{persona_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["system_prompt"] == VALID_PROMPT


@pytest.mark.asyncio
async def test_update_persona(client: AsyncClient, auth_headers: dict):
    created = await client.post("/personas", headers=auth_headers, json=_persona_payload())
    persona_id = created.json()["id"]

    response = await client.put(
        f"/personas/{persona_id}",
        headers=auth_headers,
        json={"name": "Vector Finance V2", "icon": "Calculator"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Vector Finance V2"
    assert data["icon"] == "Calculator"
    assert data["system_prompt"] == VALID_PROMPT  # inchange


@pytest.mark.asyncio
async def test_delete_persona(client: AsyncClient, auth_headers: dict):
    created = await client.post("/personas", headers=auth_headers, json=_persona_payload())
    persona_id = created.json()["id"]

    response = await client.delete(f"/personas/{persona_id}", headers=auth_headers)
    assert response.status_code == 204

    follow_up = await client.get(f"/personas/{persona_id}", headers=auth_headers)
    assert follow_up.status_code == 404


# ============================================================
# Ownership
# ============================================================

@pytest.mark.asyncio
async def test_persona_not_visible_or_editable_by_other_user(
    client: AsyncClient, auth_headers: dict, register_second_user
):
    created = await client.post("/personas", headers=auth_headers, json=_persona_payload())
    persona_id = created.json()["id"]

    other = await register_second_user()

    get_resp = await client.get(f"/personas/{persona_id}", headers=other["headers"])
    assert get_resp.status_code == 404

    put_resp = await client.put(
        f"/personas/{persona_id}", headers=other["headers"], json={"name": "Vole"}
    )
    assert put_resp.status_code == 404

    delete_resp = await client.delete(f"/personas/{persona_id}", headers=other["headers"])
    assert delete_resp.status_code == 404


@pytest.mark.asyncio
async def test_persona_list_scoped_to_owner_plus_system(
    client: AsyncClient, auth_headers: dict, register_second_user
):
    await client.post("/personas", headers=auth_headers, json=_persona_payload())

    other = await register_second_user()
    response = await client.get("/personas", headers=other["headers"])
    names = [p["name"] for p in response.json()]
    assert "Vector Finance" not in names
    assert any(p["is_system"] for p in response.json())


# ============================================================
# Protection du persona systeme (is_system)
# ============================================================

@pytest.mark.asyncio
async def test_system_persona_visible_but_readonly(client: AsyncClient, auth_headers: dict):
    system_id = await _get_system_persona_id(client, auth_headers)

    get_resp = await client.get(f"/personas/{system_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["is_system"] is True

    put_resp = await client.put(
        f"/personas/{system_id}", headers=auth_headers, json={"name": "Hack"}
    )
    assert put_resp.status_code == 404

    delete_resp = await client.delete(f"/personas/{system_id}", headers=auth_headers)
    assert delete_resp.status_code == 404


# ============================================================
# Validation
# ============================================================

@pytest.mark.asyncio
async def test_create_persona_invalid_icon_rejected(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/personas", headers=auth_headers, json=_persona_payload(icon="NotAnIcon")
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_persona_invalid_color_rejected(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/personas", headers=auth_headers, json=_persona_payload(color="#000000")
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_persona_prompt_too_short_rejected(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/personas", headers=auth_headers, json=_persona_payload(system_prompt="Court")
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_persona_name_too_long_rejected(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/personas", headers=auth_headers, json=_persona_payload(name="x" * 61)
    )
    assert response.status_code == 422


# ============================================================
# Association documents/corpus
# ============================================================

@pytest.mark.asyncio
async def test_link_and_unlink_document(
    client: AsyncClient, auth_headers: dict, mini_pdf_bytes: bytes, mock_embeddings
):
    persona_id = (
        await client.post("/personas", headers=auth_headers, json=_persona_payload())
    ).json()["id"]
    doc = await client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("rapport.pdf", mini_pdf_bytes, "application/pdf")},
        data={"name": "RapportTest"},
    )
    document_id = doc.json()["id"]

    link_resp = await client.post(
        f"/personas/{persona_id}/documents",
        headers=auth_headers,
        json={"document_ids": [document_id]},
    )
    assert link_resp.status_code == 200
    assert {d["id"] for d in link_resp.json()["documents"]} == {document_id}

    unlink_resp = await client.delete(
        f"/personas/{persona_id}/documents/{document_id}", headers=auth_headers
    )
    assert unlink_resp.status_code == 200
    assert unlink_resp.json()["documents"] == []


@pytest.mark.asyncio
async def test_link_document_not_owned_rejected(
    client: AsyncClient,
    auth_headers: dict,
    register_second_user,
    mini_pdf_bytes: bytes,
    mock_embeddings,
):
    persona_id = (
        await client.post("/personas", headers=auth_headers, json=_persona_payload())
    ).json()["id"]

    other = await register_second_user()
    other_doc = await client.post(
        "/documents/upload",
        headers=other["headers"],
        files={"file": ("autre.pdf", mini_pdf_bytes, "application/pdf")},
        data={"name": "DocAutrui"},
    )
    other_document_id = other_doc.json()["id"]

    response = await client.post(
        f"/personas/{persona_id}/documents",
        headers=auth_headers,
        json={"document_ids": [other_document_id]},
    )
    assert response.status_code == 404


# Test ajoute J53 : l'association corpus (POST/DELETE
# /personas/{id}/corpora) n'avait aucune couverture -- seule
# l'association document etait testee, alors que le meme pattern
# d'ownership check s'applique cote service (add_corpora).
@pytest.mark.asyncio
async def test_link_and_unlink_corpus(client: AsyncClient, auth_headers: dict):
    persona_id = (
        await client.post("/personas", headers=auth_headers, json=_persona_payload())
    ).json()["id"]
    corpus_id = (
        await client.post("/corpora", headers=auth_headers, json={"name": "Corpus persona"})
    ).json()["id"]

    link_resp = await client.post(
        f"/personas/{persona_id}/corpora",
        headers=auth_headers,
        json={"corpus_ids": [corpus_id]},
    )
    assert link_resp.status_code == 200
    assert {c["id"] for c in link_resp.json()["corpora"]} == {corpus_id}

    unlink_resp = await client.delete(
        f"/personas/{persona_id}/corpora/{corpus_id}", headers=auth_headers
    )
    assert unlink_resp.status_code == 200
    assert unlink_resp.json()["corpora"] == []


# Test ajoute J53 : symetrique de test_link_document_not_owned_rejected
# pour les corpus -- verifie que le meme garde-fou d'ownership existe
# sur ce second chemin d'association, pas seulement les documents.
@pytest.mark.asyncio
async def test_link_corpus_not_owned_rejected(
    client: AsyncClient, auth_headers: dict, register_second_user
):
    persona_id = (
        await client.post("/personas", headers=auth_headers, json=_persona_payload())
    ).json()["id"]

    other = await register_second_user()
    other_corpus = await client.post(
        "/corpora", headers=other["headers"], json={"name": "Corpus autrui"}
    )
    other_corpus_id = other_corpus.json()["id"]

    response = await client.post(
        f"/personas/{persona_id}/corpora",
        headers=auth_headers,
        json={"corpus_ids": [other_corpus_id]},
    )
    assert response.status_code == 404


# ============================================================
# Integration chat — run_agent() directement (pas d'appel LLM reel,
# chat_with_tools mocke pour capturer le system prompt envoye)
# ============================================================

def _mock_chat_response(final_message: str = "Réponse test."):
    return {
        "content": final_message,
        "tool_calls": None,
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "model": "gpt-4o-mini"},
    }


async def _get_orm_user(db_session, email: str) -> User:
    result = await db_session.execute(select(User).where(User.email == email))
    return result.scalar_one()


@pytest.mark.asyncio
async def test_chat_uses_persona_system_prompt(
    client: AsyncClient, auth_headers: dict, registered_user: dict, db_session
):
    persona_id = (
        await client.post("/personas", headers=auth_headers, json=_persona_payload())
    ).json()["id"]
    conv = await client.post(
        "/conversations", headers=auth_headers, json={"persona_id": persona_id}
    )
    conversation_id = conv.json()["id"]
    assert conv.json()["persona_name"] == "Vector Finance"

    user = await _get_orm_user(db_session, registered_user["email"])

    with patch(
        "app.ai.agent_loop._llm.chat_with_tools",
        new=AsyncMock(return_value=_mock_chat_response()),
    ) as mocked:
        result = await run_agent(
            user_message="Quelle est la santé financière de mon entreprise ?",
            db=db_session,
            user=user,
            conversation_id=UUID(conversation_id),
        )

    assert result["message"] == "Réponse test."
    sent_messages = mocked.call_args.kwargs["messages"]
    system_content = sent_messages[0]["content"]
    assert system_content.startswith(VALID_PROMPT)


@pytest.mark.asyncio
async def test_chat_without_persona_uses_default_prompt(
    client: AsyncClient, auth_headers: dict, registered_user: dict, db_session
):
    """Sans persona_id (comportement par defaut) : SYSTEM_PROMPT inchange."""
    from app.ai.agent_loop import SYSTEM_PROMPT

    conv = await client.post("/conversations", headers=auth_headers, json={})
    conversation_id = conv.json()["id"]
    assert conv.json()["persona_id"] is None

    user = await _get_orm_user(db_session, registered_user["email"])

    with patch(
        "app.ai.agent_loop._llm.chat_with_tools",
        new=AsyncMock(return_value=_mock_chat_response()),
    ) as mocked:
        await run_agent(
            user_message="Bonjour",
            db=db_session,
            user=user,
            conversation_id=UUID(conversation_id),
        )

    sent_messages = mocked.call_args.kwargs["messages"]
    assert sent_messages[0]["content"] == SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_chat_with_persona_enriches_rag_context_from_linked_document(
    client: AsyncClient,
    auth_headers: dict,
    registered_user: dict,
    db_session,
    mini_pdf_bytes: bytes,
    mock_embeddings,
):
    persona_id = (
        await client.post("/personas", headers=auth_headers, json=_persona_payload())
    ).json()["id"]

    doc = await client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("rapport.pdf", mini_pdf_bytes, "application/pdf")},
        data={"name": "RapportFinancier2026"},
    )
    document_id = doc.json()["id"]
    await client.post(
        f"/personas/{persona_id}/documents",
        headers=auth_headers,
        json={"document_ids": [document_id]},
    )

    conv = await client.post(
        "/conversations", headers=auth_headers, json={"persona_id": persona_id}
    )
    conversation_id = conv.json()["id"]

    user = await _get_orm_user(db_session, registered_user["email"])

    with patch(
        "app.ai.agent_loop._llm.chat_with_tools",
        new=AsyncMock(return_value=_mock_chat_response()),
    ) as mocked:
        await run_agent(
            user_message="Que dit le rapport ?",
            db=db_session,
            user=user,
            conversation_id=UUID(conversation_id),
        )

    system_content = mocked.call_args.kwargs["messages"][0]["content"]
    assert "CONTEXTE DOCUMENTAIRE" in system_content
    assert "RapportFinancier2026" in system_content


@pytest.mark.asyncio
async def test_persona_locked_after_first_message(
    client: AsyncClient, auth_headers: dict
):
    system_id = await _get_system_persona_id(client, auth_headers)
    other_persona_id = (
        await client.post("/personas", headers=auth_headers, json=_persona_payload())
    ).json()["id"]

    conv = await client.post("/conversations", headers=auth_headers, json={})
    conversation_id = conv.json()["id"]

    # Change de persona sur une conversation vide -> OK
    switch_resp = await client.patch(
        f"/conversations/{conversation_id}",
        headers=auth_headers,
        json={"persona_id": other_persona_id},
    )
    assert switch_resp.status_code == 200
    assert switch_resp.json()["persona_id"] == other_persona_id

    await client.post(
        f"/conversations/{conversation_id}/messages",
        headers=auth_headers,
        json={"role": "user", "message_kind": "user", "content": "Salut"},
    )

    # Nouvelle tentative de changement -> verrouille
    locked_resp = await client.patch(
        f"/conversations/{conversation_id}",
        headers=auth_headers,
        json={"persona_id": system_id},
    )
    assert locked_resp.status_code == 409
