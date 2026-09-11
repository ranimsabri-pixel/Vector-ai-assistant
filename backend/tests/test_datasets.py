"""Tests des endpoints Datasets : upload, profilage, ownership, export."""
import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


def _csv_bytes(rows: int = 5) -> bytes:
    lines = ["name,value"]
    for i in range(rows):
        lines.append(f"Item {i},{i * 10}")
    return ("\n".join(lines) + "\n").encode("utf-8")


_FAKE_LLM_ANALYSIS = {
    "domain": "sales",
    "domain_label": "Données commerciales",
    "description": "Dataset de test pour l'analyse semantique.",
    "key_columns": ["name", "value"],
    "suggested_kpis": [
        {
            "name": "Total value",
            "description": "Somme des valeurs",
            "columns_used": ["value"],
            "priority": "high",
        }
    ],
    "warnings": [],
}


@pytest.mark.asyncio
async def test_upload_csv_creates_dataset(client: AsyncClient, auth_headers: dict):
    """Un CSV valide cree un dataset en statut 'uploaded' (pas encore profile)."""
    response = await client.post(
        "/datasets/upload",
        headers=auth_headers,
        files={"file": ("test.csv", _csv_bytes(), "text/csv")},
        data={"name": "Mon dataset de test"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Mon dataset de test"
    assert data["status"] == "uploaded"
    assert data["row_count"] == 5
    assert data["column_count"] == 2


@pytest.mark.asyncio
async def test_upload_invalid_extension_rejected(client: AsyncClient, auth_headers: dict):
    """Une extension non supportee est refusee avant meme d'essayer de parser."""
    response = await client.post(
        "/datasets/upload",
        headers=auth_headers,
        files={"file": ("test.exe", b"MZ\x90\x00binary", "application/octet-stream")},
        data={"name": "Invalide"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_unreadable_csv_content_rejected(
    client: AsyncClient, auth_headers: dict
):
    """Un fichier .csv dont le contenu n'est pas un CSV valide est refuse
    proprement (pas de 500)."""
    response = await client.post(
        "/datasets/upload",
        headers=auth_headers,
        files={"file": ("test.csv", b"\x00\x01\x02\x03\xff\xfe", "text/csv")},
        data={"name": "Corrompu"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_datasets_own_only(
    client: AsyncClient, auth_headers: dict, register_second_user
):
    """Le listing ne retourne que les datasets de l'utilisateur courant."""
    await client.post(
        "/datasets/upload",
        headers=auth_headers,
        files={"file": ("mine.csv", _csv_bytes(), "text/csv")},
        data={"name": "Dataset de A"},
    )

    other = await register_second_user()
    await client.post(
        "/datasets/upload",
        headers=other["headers"],
        files={"file": ("theirs.csv", _csv_bytes(), "text/csv")},
        data={"name": "Dataset de B"},
    )

    response = await client.get("/datasets", headers=auth_headers)
    names = [d["name"] for d in response.json()]
    assert "Dataset de A" in names
    assert "Dataset de B" not in names


@pytest.mark.asyncio
async def test_delete_dataset_not_owned_returns_404(
    client: AsyncClient, auth_headers: dict, register_second_user
):
    """Un utilisateur ne peut pas supprimer le dataset d'un autre."""
    created = await client.post(
        "/datasets/upload",
        headers=auth_headers,
        files={"file": ("mine.csv", _csv_bytes(), "text/csv")},
        data={"name": "A proteger"},
    )
    dataset_id = created.json()["id"]

    other = await register_second_user()
    response = await client.delete(f"/datasets/{dataset_id}", headers=other["headers"])
    assert response.status_code == 404

    response = await client.delete(f"/datasets/{dataset_id}", headers=auth_headers)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_profile_endpoint_computes_stats(client: AsyncClient, auth_headers: dict):
    """Le profilage (synchrone) calcule les statistiques par colonne."""
    created = await client.post(
        "/datasets/upload",
        headers=auth_headers,
        files={"file": ("test.csv", _csv_bytes(20), "text/csv")},
        data={"name": "A profiler"},
    )
    dataset_id = created.json()["id"]

    response = await client.post(f"/datasets/{dataset_id}/profile", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

    columns = await client.get(f"/datasets/{dataset_id}/columns", headers=auth_headers)
    assert columns.status_code == 200
    col_names = {c["name"] for c in columns.json()}
    assert col_names == {"name", "value"}
    value_col = next(c for c in columns.json() if c["name"] == "value")
    assert value_col["dtype"] == "numeric"
    assert value_col["numeric_stats"] is not None


@pytest.mark.asyncio
async def test_upload_with_column_overrides_deletes_column(
    client: AsyncClient, auth_headers: dict
):
    """Une colonne marquee deleted=True a l'upload disparait apres profilage."""
    overrides = [{"original_name": "value", "deleted": True}]
    created = await client.post(
        "/datasets/upload",
        headers=auth_headers,
        files={"file": ("test.csv", _csv_bytes(), "text/csv")},
        data={"name": "Avec overrides", "column_overrides": json.dumps(overrides)},
    )
    dataset_id = created.json()["id"]

    await client.post(f"/datasets/{dataset_id}/profile", headers=auth_headers)

    columns = await client.get(f"/datasets/{dataset_id}/columns", headers=auth_headers)
    col_names = {c["name"] for c in columns.json()}
    assert "value" not in col_names
    assert "name" in col_names


@pytest.mark.asyncio
async def test_dataset_sample_export_respects_limit(
    client: AsyncClient, auth_headers: dict
):
    """L'export d'echantillon retourne exactement le nombre de lignes demande."""
    created = await client.post(
        "/datasets/upload",
        headers=auth_headers,
        files={"file": ("test.csv", _csv_bytes(20), "text/csv")},
        data={"name": "Pour export"},
    )
    dataset_id = created.json()["id"]

    response = await client.get(
        f"/datasets/{dataset_id}/sample?limit=5", headers=auth_headers
    )
    assert response.status_code == 200
    lines = [line for line in response.text.strip().splitlines() if line]
    # 1 ligne d'en-tete + 5 lignes de donnees
    assert len(lines) == 6


@pytest.mark.asyncio
async def test_dataset_sample_limit_over_max_rejected(
    client: AsyncClient, auth_headers: dict
):
    """La limite d'export est plafonnee a 1000 par la validation FastAPI (422
    si depassee, pas un cappage silencieux)."""
    created = await client.post(
        "/datasets/upload",
        headers=auth_headers,
        files={"file": ("test.csv", _csv_bytes(), "text/csv")},
        data={"name": "Limite"},
    )
    dataset_id = created.json()["id"]

    response = await client.get(
        f"/datasets/{dataset_id}/sample?limit=5000", headers=auth_headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reprofile_returns_profiling_status_immediately(
    client: AsyncClient, auth_headers: dict
):
    """/reprofile est asynchrone (BackgroundTasks) : la reponse immediate a
    le statut 'profiling', pas encore 'ready'."""
    created = await client.post(
        "/datasets/upload",
        headers=auth_headers,
        files={"file": ("test.csv", _csv_bytes(), "text/csv")},
        data={"name": "A reprofiler"},
    )
    dataset_id = created.json()["id"]
    await client.post(f"/datasets/{dataset_id}/profile", headers=auth_headers)

    response = await client.post(f"/datasets/{dataset_id}/reprofile", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "profiling"


@pytest.mark.asyncio
async def test_analyze_requires_ready_status(client: AsyncClient, auth_headers: dict):
    """L'analyse semantique est refusee tant que le dataset n'est pas profile."""
    created = await client.post(
        "/datasets/upload",
        headers=auth_headers,
        files={"file": ("test.csv", _csv_bytes(), "text/csv")},
        data={"name": "Pas encore profile"},
    )
    dataset_id = created.json()["id"]

    response = await client.post(f"/datasets/{dataset_id}/analyze", headers=auth_headers)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_analyze_dataset_llm_success(client: AsyncClient, auth_headers: dict):
    """L'analyse semantique combine regles + reponse LLM (mockee)."""
    created = await client.post(
        "/datasets/upload",
        headers=auth_headers,
        files={"file": ("test.csv", _csv_bytes(20), "text/csv")},
        data={"name": "A analyser"},
    )
    dataset_id = created.json()["id"]
    await client.post(f"/datasets/{dataset_id}/profile", headers=auth_headers)

    with patch(
        "app.ai.providers.openai.OpenAIProvider.structured_output",
        new=AsyncMock(return_value=_FAKE_LLM_ANALYSIS),
    ):
        response = await client.post(f"/datasets/{dataset_id}/analyze", headers=auth_headers)

    assert response.status_code == 200
    analysis = response.json()["semantic_analysis"]
    assert analysis["llm_analysis"]["domain"] == "sales"
    assert analysis["rule_based"]["primary_domain"] is not None


@pytest.mark.asyncio
async def test_analyze_llm_failure_falls_back_to_rules(
    client: AsyncClient, auth_headers: dict
):
    """Si le LLM echoue (timeout/erreur), l'analyse retombe sur un fallback
    base sur les regles seules, sans faire echouer la requete."""
    created = await client.post(
        "/datasets/upload",
        headers=auth_headers,
        files={"file": ("test.csv", _csv_bytes(20), "text/csv")},
        data={"name": "LLM en panne"},
    )
    dataset_id = created.json()["id"]
    await client.post(f"/datasets/{dataset_id}/profile", headers=auth_headers)

    with patch(
        "app.ai.providers.openai.OpenAIProvider.structured_output",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        response = await client.post(f"/datasets/{dataset_id}/analyze", headers=auth_headers)

    assert response.status_code == 200
    analysis = response.json()["semantic_analysis"]
    assert analysis["llm_analysis"] is not None
    assert "domain" in analysis["llm_analysis"]


@pytest.mark.asyncio
async def test_generate_and_calculate_auto_kpis(client: AsyncClient, auth_headers: dict):
    """Genere les KPIs auto puis les calcule tous en une passe."""
    created = await client.post(
        "/datasets/upload",
        headers=auth_headers,
        files={"file": ("test.csv", _csv_bytes(20), "text/csv")},
        data={"name": "Pour KPIs"},
    )
    dataset_id = created.json()["id"]
    await client.post(f"/datasets/{dataset_id}/profile", headers=auth_headers)

    generate_resp = await client.post(
        f"/datasets/{dataset_id}/auto-kpis/generate", headers=auth_headers
    )
    assert generate_resp.status_code == 200
    assert generate_resp.json()["auto_kpis"]["generated_count"] > 0

    calculate_resp = await client.post(
        f"/datasets/{dataset_id}/auto-kpis/calculate-all", headers=auth_headers
    )
    assert calculate_resp.status_code == 200
    assert len(calculate_resp.json()) > 0


@pytest.mark.asyncio
async def test_column_values_endpoint(client: AsyncClient, auth_headers: dict):
    """Les valeurs uniques d'une colonne sont retournees triees."""
    created = await client.post(
        "/datasets/upload",
        headers=auth_headers,
        files={"file": ("test.csv", _csv_bytes(5), "text/csv")},
        data={"name": "Pour valeurs colonne"},
    )
    dataset_id = created.json()["id"]
    await client.post(f"/datasets/{dataset_id}/profile", headers=auth_headers)

    response = await client.get(
        f"/datasets/{dataset_id}/columns/name/values", headers=auth_headers
    )
    assert response.status_code == 200
    values = response.json()
    assert values == sorted(values)
    assert "Item 0" in values


@pytest.mark.asyncio
async def test_column_values_unknown_column_returns_404(
    client: AsyncClient, auth_headers: dict
):
    """Une colonne inexistante retourne 404, pas une 500."""
    created = await client.post(
        "/datasets/upload",
        headers=auth_headers,
        files={"file": ("test.csv", _csv_bytes(5), "text/csv")},
        data={"name": "Sans cette colonne"},
    )
    dataset_id = created.json()["id"]
    await client.post(f"/datasets/{dataset_id}/profile", headers=auth_headers)

    response = await client.get(
        f"/datasets/{dataset_id}/columns/inexistante/values", headers=auth_headers
    )
    assert response.status_code == 404
