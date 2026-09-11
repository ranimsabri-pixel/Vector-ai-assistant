"""Tests des endpoints Corpus (S5 J34) : CRUD, ajout/retrait de documents, ownership."""
import pytest
from httpx import AsyncClient


async def _upload_document(client: AsyncClient, headers: dict, pdf_bytes: bytes, name: str) -> str:
    response = await client.post(
        "/documents/upload",
        headers=headers,
        files={"file": (f"{name}.pdf", pdf_bytes, "application/pdf")},
        data={"name": name},
    )
    return response.json()["id"]


@pytest.mark.asyncio
async def test_create_corpus(client: AsyncClient, auth_headers: dict):
    """Un corpus se cree vide, sans document."""
    response = await client.post(
        "/corpora",
        headers=auth_headers,
        json={"name": "Rapports 2026", "description": "Test"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Rapports 2026"
    assert data["document_count"] == 0
    assert data["documents"] == []


@pytest.mark.asyncio
async def test_create_corpus_requires_name(client: AsyncClient, auth_headers: dict):
    """Le nom est obligatoire (min_length=1)."""
    response = await client.post(
        "/corpora", headers=auth_headers, json={"description": "Sans nom"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_add_documents_to_corpus(
    client: AsyncClient, auth_headers: dict, mini_pdf_bytes: bytes, mock_embeddings
):
    """Ajouter des documents existants met a jour document_count et la liste."""
    corpus = await client.post("/corpora", headers=auth_headers, json={"name": "Mon corpus"})
    corpus_id = corpus.json()["id"]

    doc1_id = await _upload_document(client, auth_headers, mini_pdf_bytes, "Doc1")
    doc2_id = await _upload_document(client, auth_headers, mini_pdf_bytes, "Doc2")

    response = await client.post(
        f"/corpora/{corpus_id}/documents",
        headers=auth_headers,
        json={"document_ids": [doc1_id, doc2_id]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["document_count"] == 2
    assert {d["id"] for d in data["documents"]} == {doc1_id, doc2_id}


@pytest.mark.asyncio
async def test_add_foreign_document_rejected(
    client: AsyncClient,
    auth_headers: dict,
    register_second_user,
    mini_pdf_bytes: bytes,
    mock_embeddings,
):
    """Impossible d'ajouter a son corpus un document appartenant a un autre user."""
    corpus = await client.post("/corpora", headers=auth_headers, json={"name": "Mon corpus"})
    corpus_id = corpus.json()["id"]

    other = await register_second_user()
    foreign_doc_id = await _upload_document(
        client, other["headers"], mini_pdf_bytes, "Doc de B"
    )

    response = await client.post(
        f"/corpora/{corpus_id}/documents",
        headers=auth_headers,
        json={"document_ids": [foreign_doc_id]},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_corpus_ownership(
    client: AsyncClient, auth_headers: dict, register_second_user
):
    """Un utilisateur ne peut ni lire, ni modifier, ni supprimer le corpus d'un autre."""
    created = await client.post(
        "/corpora", headers=auth_headers, json={"name": "Prive"}
    )
    corpus_id = created.json()["id"]

    other = await register_second_user()

    get_resp = await client.get(f"/corpora/{corpus_id}", headers=other["headers"])
    assert get_resp.status_code == 404

    patch_resp = await client.patch(
        f"/corpora/{corpus_id}", headers=other["headers"], json={"name": "Vole"}
    )
    assert patch_resp.status_code == 404

    delete_resp = await client.delete(f"/corpora/{corpus_id}", headers=other["headers"])
    assert delete_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_corpus_keeps_documents(
    client: AsyncClient, auth_headers: dict, mini_pdf_bytes: bytes, mock_embeddings
):
    """Supprimer un corpus ne supprime PAS les documents qui y etaient lies."""
    corpus = await client.post("/corpora", headers=auth_headers, json={"name": "Ephemere"})
    corpus_id = corpus.json()["id"]

    doc_id = await _upload_document(client, auth_headers, mini_pdf_bytes, "Survivant")
    await client.post(
        f"/corpora/{corpus_id}/documents",
        headers=auth_headers,
        json={"document_ids": [doc_id]},
    )

    delete_resp = await client.delete(f"/corpora/{corpus_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    doc_resp = await client.get(f"/documents/{doc_id}", headers=auth_headers)
    assert doc_resp.status_code == 200


@pytest.mark.asyncio
async def test_remove_documents_from_corpus(
    client: AsyncClient, auth_headers: dict, mini_pdf_bytes: bytes, mock_embeddings
):
    """Retirer un document du corpus le fait disparaitre de la liste, sans le
    supprimer lui-meme."""
    corpus = await client.post("/corpora", headers=auth_headers, json={"name": "Test retrait"})
    corpus_id = corpus.json()["id"]

    doc_id = await _upload_document(client, auth_headers, mini_pdf_bytes, "A retirer")
    await client.post(
        f"/corpora/{corpus_id}/documents",
        headers=auth_headers,
        json={"document_ids": [doc_id]},
    )

    response = await client.request(
        "DELETE",
        f"/corpora/{corpus_id}/documents",
        headers=auth_headers,
        json={"document_ids": [doc_id]},
    )
    assert response.status_code == 200
    assert response.json()["document_count"] == 0

    doc_resp = await client.get(f"/documents/{doc_id}", headers=auth_headers)
    assert doc_resp.status_code == 200


@pytest.mark.asyncio
async def test_update_corpus_name_and_description(client: AsyncClient, auth_headers: dict):
    """PATCH /corpora/{id} renomme et/ou change la description."""
    created = await client.post(
        "/corpora", headers=auth_headers, json={"name": "Ancien nom"}
    )
    corpus_id = created.json()["id"]

    response = await client.patch(
        f"/corpora/{corpus_id}",
        headers=auth_headers,
        json={"name": "Nouveau nom", "description": "Nouvelle description"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Nouveau nom"
    assert response.json()["description"] == "Nouvelle description"


@pytest.mark.asyncio
async def test_list_corpora_includes_document_count(
    client: AsyncClient, auth_headers: dict, mini_pdf_bytes: bytes, mock_embeddings
):
    """Le listing des corpus inclut le bon document_count (sans requete N+1)."""
    corpus = await client.post("/corpora", headers=auth_headers, json={"name": "Avec docs"})
    corpus_id = corpus.json()["id"]
    doc_id = await _upload_document(client, auth_headers, mini_pdf_bytes, "Doc")
    await client.post(
        f"/corpora/{corpus_id}/documents",
        headers=auth_headers,
        json={"document_ids": [doc_id]},
    )

    response = await client.get("/corpora", headers=auth_headers)
    assert response.status_code == 200
    listed = next(c for c in response.json() if c["id"] == corpus_id)
    assert listed["document_count"] == 1
