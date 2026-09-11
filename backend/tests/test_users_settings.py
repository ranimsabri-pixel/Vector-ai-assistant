"""Tests des endpoints Settings/Compte (S5 J50) : PATCH /users/me,
POST /users/me/password, DELETE /users/me (hard delete + cascade)."""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.models.analysis import Analysis
from app.db.models.conversation import Conversation, Message
from app.db.models.corpus import Corpus, CorpusDocument
from app.db.models.dashboard import Dashboard
from app.db.models.dataset import Dataset, DatasetColumn
from app.db.models.document import Chunk, Document
from app.db.models.kpi import KPI, KPIValue
from app.db.models.persona import Persona, PersonaCorpus, PersonaDocument
from app.db.models.saved_dashboard import DashboardWidget, SavedDashboard
from app.db.models.user import User
from tests.conftest import DEFAULT_TEST_PASSWORD


# ============================================================
# T1/T2 — PATCH /users/me
# ============================================================

@pytest.mark.asyncio
async def test_patch_me_valid(client: AsyncClient, auth_headers: dict):
    response = await client.patch(
        "/users/me", headers=auth_headers, json={"full_name": "Nouveau Nom"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["full_name"] == "Nouveau Nom"


@pytest.mark.asyncio
async def test_patch_me_name_too_long_422(client: AsyncClient, auth_headers: dict):
    response = await client.patch(
        "/users/me", headers=auth_headers, json={"full_name": "x" * 61}
    )
    assert response.status_code == 422


# ============================================================
# T3/T4 — POST /users/me/password
# ============================================================

@pytest.mark.asyncio
async def test_change_password_valid(
    client: AsyncClient, auth_headers: dict, registered_user: dict
):
    response = await client.post(
        "/users/me/password",
        headers=auth_headers,
        json={"old_password": DEFAULT_TEST_PASSWORD, "new_password": "NouveauPass456"},
    )
    assert response.status_code == 200, response.text

    # L'ancien mot de passe ne fonctionne plus, le nouveau oui
    old_login = await client.post(
        "/auth/login",
        data={"username": registered_user["email"], "password": DEFAULT_TEST_PASSWORD},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/auth/login",
        data={"username": registered_user["email"], "password": "NouveauPass456"},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_old_401(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/users/me/password",
        headers=auth_headers,
        json={"old_password": "MauvaisMotDePasse1", "new_password": "NouveauPass456"},
    )
    assert response.status_code == 401


# ============================================================
# T5/T6 — DELETE /users/me
# ============================================================

async def _build_full_footprint(
    client: AsyncClient, headers: dict, mini_pdf_bytes: bytes, mock_embeddings
) -> dict:
    """Cree au moins une ligne dans chaque table liee a l'utilisateur, pour
    verifier exhaustivement le cascade delete : dataset, document (+chunks),
    corpus (+corpus_documents), persona liee au document et au corpus
    (+personas_documents, +personas_corpora), conversation (+messages)."""
    dataset = await client.post(
        "/datasets/upload",
        headers=headers,
        files={"file": ("test.csv", b"name,value\nA,1\nB,2\n", "text/csv")},
        data={"name": "Dataset cascade"},
    )
    assert dataset.status_code == 201, dataset.text

    document = await client.post(
        "/documents/upload",
        headers=headers,
        files={"file": ("test.pdf", mini_pdf_bytes, "application/pdf")},
        data={"name": "Document cascade"},
    )
    assert document.status_code == 201, document.text
    document_id = document.json()["id"]

    doc_detail = await client.get(f"/documents/{document_id}", headers=headers)
    assert doc_detail.status_code == 200
    assert doc_detail.json()["chunk_count"] > 0

    corpus = await client.post(
        "/corpora", headers=headers, json={"name": "Corpus cascade"}
    )
    assert corpus.status_code == 201, corpus.text
    corpus_id = corpus.json()["id"]

    add_doc = await client.post(
        f"/corpora/{corpus_id}/documents",
        headers=headers,
        json={"document_ids": [document_id]},
    )
    assert add_doc.status_code == 200, add_doc.text

    persona = await client.post(
        "/personas",
        headers=headers,
        json={
            "name": "Persona cascade",
            "system_prompt": "Persona de test pour verifier le cascade delete complet.",
            "icon": "Bot",
            "color": "#3B82F6",
        },
    )
    assert persona.status_code == 201, persona.text
    persona_id = persona.json()["id"]

    link_doc = await client.post(
        f"/personas/{persona_id}/documents",
        headers=headers,
        json={"document_ids": [document_id]},
    )
    assert link_doc.status_code == 200, link_doc.text

    link_corpus = await client.post(
        f"/personas/{persona_id}/corpora",
        headers=headers,
        json={"corpus_ids": [corpus_id]},
    )
    assert link_corpus.status_code == 200, link_corpus.text

    conversation = await client.post(
        "/conversations", headers=headers, json={"title": "Conversation cascade"}
    )
    assert conversation.status_code == 201, conversation.text
    conversation_id = conversation.json()["id"]

    message = await client.post(
        f"/conversations/{conversation_id}/messages",
        headers=headers,
        json={"role": "user", "message_kind": "user", "content": "Bonjour"},
    )
    assert message.status_code == 201, message.text

    return {
        "dataset_id": dataset.json()["id"],
        "document_id": document_id,
        "corpus_id": corpus_id,
        "persona_id": persona_id,
        "conversation_id": conversation_id,
    }


@pytest.mark.asyncio
async def test_delete_me_valid_cascades_everywhere(
    client: AsyncClient,
    db_session,
    mini_pdf_bytes: bytes,
    mock_embeddings,
):
    email = f"test_{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post(
        "/auth/register", json={"email": email, "password": DEFAULT_TEST_PASSWORD}
    )
    assert register.status_code == 201, register.text
    user_id = register.json()["id"]

    login = await client.post(
        "/auth/login", data={"username": email, "password": DEFAULT_TEST_PASSWORD}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    ids = await _build_full_footprint(client, headers, mini_pdf_bytes, mock_embeddings)

    response = await client.request(
        "DELETE", "/users/me", headers=headers, json={"password": DEFAULT_TEST_PASSWORD}
    )
    assert response.status_code == 204, response.text

    # L'utilisateur lui-meme a disparu
    assert (
        await db_session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none() is None

    # Toutes les ressources liees (directement ou transitivement) sont parties
    assert (
        await db_session.execute(select(Dataset).where(Dataset.id == ids["dataset_id"]))
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(select(Document).where(Document.id == ids["document_id"]))
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(
            select(Chunk).where(Chunk.document_id == ids["document_id"])
        )
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(select(Corpus).where(Corpus.id == ids["corpus_id"]))
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(
            select(CorpusDocument).where(CorpusDocument.corpus_id == ids["corpus_id"])
        )
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(select(Persona).where(Persona.id == ids["persona_id"]))
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(
            select(PersonaDocument).where(PersonaDocument.persona_id == ids["persona_id"])
        )
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(
            select(PersonaCorpus).where(PersonaCorpus.persona_id == ids["persona_id"])
        )
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(
            select(Conversation).where(Conversation.id == ids["conversation_id"])
        )
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(
            select(Message).where(Message.conversation_id == ids["conversation_id"])
        )
    ).scalar_one_or_none() is None


# Test ajoute J53 : couvre le cas ou un dataset possede des enfants au-dela
# des colonnes (analyses, dashboards, KPI + leurs valeurs, dashboards
# sauvegardes + widgets) -- la chaine FK users->datasets->{...} avait ete
# verifiee au niveau schema en J50 (information_schema) mais jamais
# exercee de bout en bout par un DELETE reel sur CES tables precises.
# C'est le test que le brief J53 designe comme le plus important : un trou
# de cascade ici laisserait des lignes orphelines en base apres suppression
# de compte, silencieusement.
@pytest.mark.asyncio
async def test_delete_me_cascades_dataset_children(
    client: AsyncClient, db_session
):
    email = f"test_{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post(
        "/auth/register", json={"email": email, "password": DEFAULT_TEST_PASSWORD}
    )
    user_id = register.json()["id"]
    login = await client.post(
        "/auth/login", data={"username": email, "password": DEFAULT_TEST_PASSWORD}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    dataset_resp = await client.post(
        "/datasets/upload",
        headers=headers,
        files={"file": ("test.csv", b"name,value\nA,1\nB,2\n", "text/csv")},
        data={"name": "Dataset cascade enfants"},
    )
    assert dataset_resp.status_code == 201, dataset_resp.text
    dataset_id = uuid.UUID(dataset_resp.json()["id"])

    # Peuple directement via l'ORM (pas de surface HTTP simple pour
    # analyses/KPI/dashboards sans declencher un vrai profilage IA) --
    # meme convention que la fixture db_session existante (retrieval RAG).
    column = DatasetColumn(dataset_id=dataset_id, name="value", dtype="int64")
    analysis = Analysis(dataset_id=dataset_id, type="domain", content={"domain": "test"})
    dashboard = Dashboard(
        user_id=user_id, dataset_id=dataset_id, title="Dashboard test", type="kpi_general"
    )
    kpi = KPI(dataset_id=dataset_id, name="Total", formula="SUM(value)")
    saved_dashboard = SavedDashboard(
        user_id=user_id, dataset_id=dataset_id, name="Saved dashboard test"
    )
    db_session.add_all([column, analysis, dashboard, kpi, saved_dashboard])
    await db_session.commit()
    await db_session.refresh(kpi)
    await db_session.refresh(saved_dashboard)

    kpi_value = KPIValue(kpi_id=kpi.id, value=42.0)
    widget = DashboardWidget(
        dashboard_id=saved_dashboard.id,
        widget_type="kpi",
        title="Widget test",
        config={},
    )
    db_session.add_all([kpi_value, widget])
    await db_session.commit()

    response = await client.request(
        "DELETE", "/users/me", headers=headers, json={"password": DEFAULT_TEST_PASSWORD}
    )
    assert response.status_code == 204, response.text

    for model, filter_col, filter_val in [
        (DatasetColumn, DatasetColumn.dataset_id, dataset_id),
        (Analysis, Analysis.dataset_id, dataset_id),
        (Dashboard, Dashboard.dataset_id, dataset_id),
        (KPI, KPI.dataset_id, dataset_id),
        (KPIValue, KPIValue.kpi_id, kpi.id),
        (SavedDashboard, SavedDashboard.dataset_id, dataset_id),
        (DashboardWidget, DashboardWidget.dashboard_id, saved_dashboard.id),
    ]:
        result = await db_session.execute(select(model).where(filter_col == filter_val))
        assert result.scalar_one_or_none() is None, (
            f"{model.__name__} n'a pas ete supprime en cascade"
        )


@pytest.mark.asyncio
async def test_delete_me_wrong_password_401_user_kept(
    client: AsyncClient, auth_headers: dict, registered_user: dict
):
    response = await client.request(
        "DELETE", "/users/me", headers=auth_headers, json={"password": "MauvaisMotDePasse1"}
    )
    assert response.status_code == 401

    # L'utilisateur existe toujours (le token reste valide)
    me = await client.get("/users/me", headers=auth_headers)
    assert me.status_code == 200
    assert me.json()["email"] == registered_user["email"]


# ============================================================
# Bonus — compte cree avant la regle renforcee (S5 J50)
# ============================================================

@pytest.mark.asyncio
async def test_legacy_weak_password_can_login_then_upgrade(
    client: AsyncClient, db_session
):
    """Un compte cree (en base, hors API) avec un mot de passe faible type
    '12345678' — comme c'etait permis avant J50 — doit toujours pouvoir se
    connecter, et peut ensuite le changer pour un mot de passe conforme a la
    regle renforcee (8+ caracteres, 1 lettre, 1 chiffre)."""
    email = f"test_{uuid.uuid4().hex[:10]}@example.com"
    user = User(
        email=email,
        password_hash=hash_password("12345678"),
        full_name="Compte historique",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    login = await client.post(
        "/auth/login", data={"username": email, "password": "12345678"}
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    change = await client.post(
        "/users/me/password",
        headers=headers,
        json={"old_password": "12345678", "new_password": "MotDePasseConforme1"},
    )
    assert change.status_code == 200, change.text

    relogin = await client.post(
        "/auth/login",
        data={"username": email, "password": "MotDePasseConforme1"},
    )
    assert relogin.status_code == 200
