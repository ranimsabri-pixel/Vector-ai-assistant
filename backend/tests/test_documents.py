"""Tests des endpoints Documents : upload PDF/docx/pptx, ingestion, ownership.

L'ingestion (extraction + chunking + embedding) tourne en BackgroundTask,
mais via ASGITransport elle s'execute de façon synchrone avant que la
reponse HTTP ne soit retournee au client de test. La fixture partagee
`mock_embeddings` (conftest.py) mocke OpenAIProvider.embed pour ne jamais
appeler la vraie API OpenAI.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_pdf_ingests_successfully(
    client: AsyncClient, auth_headers: dict, mini_pdf_bytes: bytes, mock_embeddings
):
    """Un PDF valide est uploade puis ingere (statut final 'ready')."""
    response = await client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("test.pdf", mini_pdf_bytes, "application/pdf")},
        data={"name": "Mon PDF de test"},
    )
    assert response.status_code == 201
    doc_id = response.json()["id"]

    detail = await client.get(f"/documents/{doc_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "ready"
    assert detail.json()["chunk_count"] > 0


@pytest.mark.asyncio
async def test_upload_docx_ingests_successfully(
    client: AsyncClient, auth_headers: dict, mini_docx_bytes: bytes, mock_embeddings
):
    """Un Word valide est uploade puis ingere."""
    response = await client.post(
        "/documents/upload",
        headers=auth_headers,
        files={
            "file": (
                "test.docx",
                mini_docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 201
    doc_id = response.json()["id"]

    detail = await client.get(f"/documents/{doc_id}", headers=auth_headers)
    assert detail.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_upload_txt_ingests_successfully(
    client: AsyncClient, auth_headers: dict, mini_txt_bytes: bytes, mock_embeddings
):
    """Un .txt valide est uploade puis ingere (S5 J51)."""
    response = await client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("test.txt", mini_txt_bytes, "text/plain")},
    )
    assert response.status_code == 201
    doc_id = response.json()["id"]

    detail = await client.get(f"/documents/{doc_id}", headers=auth_headers)
    assert detail.json()["status"] == "ready"
    assert detail.json()["chunk_count"] > 0


@pytest.mark.asyncio
async def test_upload_md_ingests_successfully(
    client: AsyncClient, auth_headers: dict, mini_md_bytes: bytes, mock_embeddings
):
    """Un .md valide est uploade puis ingere (S5 J51)."""
    response = await client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("test.md", mini_md_bytes, "text/markdown")},
    )
    assert response.status_code == 201
    doc_id = response.json()["id"]

    detail = await client.get(f"/documents/{doc_id}", headers=auth_headers)
    assert detail.json()["status"] == "ready"
    assert detail.json()["chunk_count"] > 0


@pytest.mark.asyncio
async def test_upload_pptx_ingests_successfully(
    client: AsyncClient, auth_headers: dict, mini_pptx_bytes: bytes, mock_embeddings
):
    """Un PowerPoint valide (2 slides) est uploade puis ingere."""
    response = await client.post(
        "/documents/upload",
        headers=auth_headers,
        files={
            "file": (
                "test.pptx",
                mini_pptx_bytes,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )
    assert response.status_code == 201
    doc_id = response.json()["id"]

    detail = await client.get(f"/documents/{doc_id}", headers=auth_headers)
    assert detail.json()["status"] == "ready"

    chunks = await client.get(f"/documents/{doc_id}/chunks", headers=auth_headers)
    assert len(chunks.json()) >= 2  # au moins un chunk par slide


@pytest.mark.asyncio
async def test_upload_unsupported_format_rejected(client: AsyncClient, auth_headers: dict):
    """Un format non supporte (.zip -- txt/md sont acceptes depuis S5 J51)
    est refuse avant l'ingestion."""
    response = await client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("archive.zip", b"PK\x03\x04fake zip", "application/zip")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_documents_ownership(
    client: AsyncClient, auth_headers: dict, register_second_user, mini_pdf_bytes, mock_embeddings
):
    """Le listing ne retourne que les documents de l'utilisateur courant."""
    await client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("mine.pdf", mini_pdf_bytes, "application/pdf")},
        data={"name": "Document de A"},
    )

    other = await register_second_user()
    await client.post(
        "/documents/upload",
        headers=other["headers"],
        files={"file": ("theirs.pdf", mini_pdf_bytes, "application/pdf")},
        data={"name": "Document de B"},
    )

    response = await client.get("/documents", headers=auth_headers)
    names = [d["name"] for d in response.json()]
    assert "Document de A" in names
    assert "Document de B" not in names


@pytest.mark.asyncio
async def test_delete_document_not_owned_returns_404(
    client: AsyncClient, auth_headers: dict, register_second_user, mini_pdf_bytes, mock_embeddings
):
    """Un utilisateur ne peut pas supprimer le document d'un autre."""
    created = await client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("mine.pdf", mini_pdf_bytes, "application/pdf")},
        data={"name": "A proteger"},
    )
    doc_id = created.json()["id"]

    other = await register_second_user()
    response = await client.delete(f"/documents/{doc_id}", headers=other["headers"])
    assert response.status_code == 404

    response = await client.delete(f"/documents/{doc_id}", headers=auth_headers)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_reingest_reprocesses_document(
    client: AsyncClient, auth_headers: dict, mini_pdf_bytes: bytes, mock_embeddings
):
    """/reingest relance le pipeline complet et le document repasse a 'ready'."""
    created = await client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("test.pdf", mini_pdf_bytes, "application/pdf")},
        data={"name": "A reingerer"},
    )
    doc_id = created.json()["id"]

    response = await client.post(f"/documents/{doc_id}/reingest", headers=auth_headers)
    assert response.status_code == 200

    detail = await client.get(f"/documents/{doc_id}", headers=auth_headers)
    assert detail.json()["status"] == "ready"
