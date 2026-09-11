"""Tests de l'upload multi-fichiers direct sur un corpus (S5 J51) :
POST /corpora/{id}/documents/upload."""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.document import Document


async def _create_corpus(client: AsyncClient, headers: dict, name: str = "Corpus test") -> str:
    response = await client.post("/corpora", headers=headers, json={"name": name})
    return response.json()["id"]


@pytest.mark.asyncio
async def test_upload_docx_alone_creates_document(
    client: AsyncClient, auth_headers: dict, mini_docx_bytes: bytes, mock_embeddings
):
    corpus_id = await _create_corpus(client, auth_headers)
    response = await client.post(
        f"/corpora/{corpus_id}/documents/upload",
        headers=auth_headers,
        files=[
            (
                "files",
                (
                    "rapport.docx",
                    mini_docx_bytes,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            )
        ],
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert len(data["uploaded"]) == 1
    assert data["uploaded"][0]["filename"] == "rapport.docx"
    assert data["errors"] == []

    corpus = await client.get(f"/corpora/{corpus_id}", headers=auth_headers)
    assert corpus.json()["document_count"] == 1


@pytest.mark.asyncio
async def test_upload_pptx_alone_creates_document(
    client: AsyncClient, auth_headers: dict, mini_pptx_bytes: bytes, mock_embeddings
):
    corpus_id = await _create_corpus(client, auth_headers)
    response = await client.post(
        f"/corpora/{corpus_id}/documents/upload",
        headers=auth_headers,
        files=[
            (
                "files",
                (
                    "slides.pptx",
                    mini_pptx_bytes,
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ),
            )
        ],
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["uploaded"]) == 1


@pytest.mark.asyncio
async def test_upload_txt_alone_creates_document(
    client: AsyncClient, auth_headers: dict, mini_txt_bytes: bytes, mock_embeddings
):
    corpus_id = await _create_corpus(client, auth_headers)
    response = await client.post(
        f"/corpora/{corpus_id}/documents/upload",
        headers=auth_headers,
        files=[("files", ("notes.txt", mini_txt_bytes, "text/plain"))],
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["uploaded"]) == 1


@pytest.mark.asyncio
async def test_upload_mixed_batch_three_formats(
    client: AsyncClient,
    auth_headers: dict,
    mini_pdf_bytes: bytes,
    mini_docx_bytes: bytes,
    mini_pptx_bytes: bytes,
    mock_embeddings,
):
    corpus_id = await _create_corpus(client, auth_headers)
    response = await client.post(
        f"/corpora/{corpus_id}/documents/upload",
        headers=auth_headers,
        files=[
            ("files", ("a.pdf", mini_pdf_bytes, "application/pdf")),
            (
                "files",
                (
                    "b.docx",
                    mini_docx_bytes,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            ),
            (
                "files",
                (
                    "c.pptx",
                    mini_pptx_bytes,
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ),
            ),
        ],
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert len(data["uploaded"]) == 3
    assert data["errors"] == []

    corpus = await client.get(f"/corpora/{corpus_id}", headers=auth_headers)
    assert corpus.json()["document_count"] == 3


@pytest.mark.asyncio
async def test_upload_on_other_users_corpus_404(
    client: AsyncClient,
    auth_headers: dict,
    register_second_user,
    mini_txt_bytes: bytes,
):
    corpus_id = await _create_corpus(client, auth_headers)
    other = await register_second_user()

    response = await client.post(
        f"/corpora/{corpus_id}/documents/upload",
        headers=other["headers"],
        files=[("files", ("notes.txt", mini_txt_bytes, "text/plain"))],
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_upload_unsupported_format_422(
    client: AsyncClient, auth_headers: dict
):
    corpus_id = await _create_corpus(client, auth_headers)
    response = await client.post(
        f"/corpora/{corpus_id}/documents/upload",
        headers=auth_headers,
        files=[("files", ("archive.zip", b"PK\x03\x04fake", "application/zip"))],
    )
    # Aucun fichier n'a pu etre cree -> l'erreur reelle remonte telle quelle
    assert response.status_code in (400, 422)
    assert "zip" in response.text.lower() or "format" in response.text.lower()


@pytest.mark.asyncio
async def test_upload_file_too_large_413(client: AsyncClient, auth_headers: dict):
    corpus_id = await _create_corpus(client, auth_headers)
    too_big = b"x" * (51 * 1024 * 1024)  # 51 Mo > limite 50 Mo
    response = await client.post(
        f"/corpora/{corpus_id}/documents/upload",
        headers=auth_headers,
        files=[("files", ("gros.txt", too_big, "text/plain"))],
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_upload_batch_partial_failure_others_still_created(
    client: AsyncClient,
    auth_headers: dict,
    mini_docx_bytes: bytes,
    mini_pptx_bytes: bytes,
    mini_txt_bytes: bytes,
    mock_embeddings,
):
    """1 fichier invalide (mauvais format) au milieu d'un batch de 3 valides
    -> les 3 valides sont quand meme crees, l'erreur est remontee a part."""
    corpus_id = await _create_corpus(client, auth_headers)
    response = await client.post(
        f"/corpora/{corpus_id}/documents/upload",
        headers=auth_headers,
        files=[
            (
                "files",
                (
                    "b.docx",
                    mini_docx_bytes,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            ),
            ("files", ("bad.zip", b"PK\x03\x04fake", "application/zip")),
            (
                "files",
                (
                    "c.pptx",
                    mini_pptx_bytes,
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ),
            ),
            ("files", ("d.txt", mini_txt_bytes, "text/plain")),
        ],
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert len(data["uploaded"]) == 3
    assert len(data["errors"]) == 1
    assert data["errors"][0]["filename"] == "bad.zip"

    corpus = await client.get(f"/corpora/{corpus_id}", headers=auth_headers)
    assert corpus.json()["document_count"] == 3


@pytest.mark.asyncio
async def test_upload_max_files_per_request_exceeded(
    client: AsyncClient, auth_headers: dict, mini_txt_bytes: bytes
):
    corpus_id = await _create_corpus(client, auth_headers)
    files = [("files", (f"f{i}.txt", mini_txt_bytes, "text/plain")) for i in range(11)]
    response = await client.post(
        f"/corpora/{corpus_id}/documents/upload", headers=auth_headers, files=files
    )
    assert response.status_code == 422


# ============================================================
# Regression — le PDF ne doit pas regresser via ce nouvel endpoint
# ============================================================

@pytest.mark.asyncio
async def test_upload_pdf_via_corpus_endpoint_no_regression(
    client: AsyncClient, auth_headers: dict, mini_pdf_bytes: bytes, mock_embeddings
):
    corpus_id = await _create_corpus(client, auth_headers)
    response = await client.post(
        f"/corpora/{corpus_id}/documents/upload",
        headers=auth_headers,
        files=[("files", ("rapport.pdf", mini_pdf_bytes, "application/pdf"))],
    )
    assert response.status_code == 201, response.text
    doc_id = response.json()["uploaded"][0]["document_id"]

    detail = await client.get(f"/documents/{doc_id}", headers=auth_headers)
    assert detail.json()["status"] == "ready"
    assert detail.json()["file_type"] == "pdf"
    assert detail.json()["chunk_count"] > 0


@pytest.mark.asyncio
async def test_chat_on_pdf_only_corpus_no_regression(
    client: AsyncClient, auth_headers: dict, mini_pdf_bytes: bytes, mock_embeddings
):
    """Un corpus PDF-only (pas de fichiers J51) continue de fonctionner en
    chat -- verifie juste que la creation de conversation liee au corpus
    n'a pas regresse avec les nouveaux endpoints/schemas."""
    corpus_id = await _create_corpus(client, auth_headers)
    upload = await client.post(
        f"/corpora/{corpus_id}/documents/upload",
        headers=auth_headers,
        files=[("files", ("rapport.pdf", mini_pdf_bytes, "application/pdf"))],
    )
    assert upload.status_code == 201

    conv = await client.post(
        "/conversations", headers=auth_headers, json={"corpus_id": corpus_id}
    )
    assert conv.status_code == 201, conv.text
    assert conv.json()["corpus_id"] == corpus_id


# ============================================================
# Securite (S5 J53) — MIME spoofing, path traversal
# ============================================================

# Test ajoute J53 : couvre le cas ou l'extension declare un format valide
# (.pdf) mais le contenu binaire n'en est pas un -- seule l'extension est
# validee a l'upload (pas de sniffing de contenu), donc le fichier DOIT
# etre accepte, puis echouer PROPREMENT (status="error", pas de crash
# serveur/500) au moment de l'extraction reelle.
@pytest.mark.asyncio
async def test_upload_spoofed_pdf_extension_fails_gracefully_at_ingestion(
    client: AsyncClient, auth_headers: dict
):
    corpus_id = await _create_corpus(client, auth_headers)
    response = await client.post(
        f"/corpora/{corpus_id}/documents/upload",
        headers=auth_headers,
        files=[("files", ("fake.pdf", b"CECI N'EST PAS UN PDF", "application/pdf"))],
    )
    assert response.status_code == 201, response.text
    document_id = response.json()["uploaded"][0]["document_id"]

    detail = await client.get(f"/documents/{document_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "error"
    assert detail.json()["error_message"]


# Test ajoute J53 : un nom de fichier malveillant (sequences de traversal)
# ne doit jamais influencer le chemin reel sur disque -- storage.py genere
# toujours un nom {uuid4()}{ext}, le nom original n'est qu'une metadonnee
# d'affichage. Verifie ici au niveau du chemin stocke en base, pas juste
# suppose depuis la lecture du code.
@pytest.mark.asyncio
async def test_upload_path_traversal_filename_does_not_escape_storage(
    client: AsyncClient, auth_headers: dict, mini_pdf_bytes: bytes, mock_embeddings, db_session
):
    corpus_id = await _create_corpus(client, auth_headers)
    response = await client.post(
        f"/corpora/{corpus_id}/documents/upload",
        headers=auth_headers,
        files=[("files", ("../../../etc/passwd.pdf", mini_pdf_bytes, "application/pdf"))],
    )
    assert response.status_code == 201, response.text
    document_id = uuid.UUID(response.json()["uploaded"][0]["document_id"])

    document = (
        await db_session.execute(select(Document).where(Document.id == document_id))
    ).scalar_one()
    assert ".." not in document.file_path
    assert not document.file_path.startswith("/")
    assert not document.file_path.startswith("etc")
    # Nom de fichier original conserve tel quel comme simple metadonnee
    # d'affichage (jamais utilise comme chemin reel).
    assert document.original_filename == "../../../etc/passwd.pdf"
