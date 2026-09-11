"""Tests du tool compute_from_dataset (S5 J46 — Option A tool calling).

Utilise un vrai dataset (fichier CSV réel sur disque + ligne Dataset réelle
en BDD), comme le reste de la suite (S5 J43 : pas de mocks sur la DB/le
filesystem, uniquement sur les API externes — ici aucun appel LLM n'est
impliqué, execute_compute_from_dataset est un pur calcul pandas)."""
import uuid
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.dataset import Dataset
from app.db.models.user import User
from app.services.dataset_tools import (
    ALL_OPERATIONS,
    execute_compute_from_dataset,
    get_compute_tool_schema,
)
from app.services.storage import FileStorage

VENTES_CSV = (
    "produit,region,ventes,remise,mois\n"
    "Chaise,Nord,320,10,2026-01\n"
    "Fauteuil,Sud,410,5,2026-01\n"
    "Chaise,Est,150,20,2026-02\n"
    "Table,Ouest,280,15,2026-02\n"
    "Fauteuil,Nord,190,25,2026-03\n"
)


async def _create_ready_dataset(db_session, user: User) -> Dataset:
    """Ecrit un vrai CSV sur disque + cree la ligne Dataset correspondante."""
    storage = FileStorage()
    user_dir = storage._user_dir(user.id)
    file_path = user_dir / f"{uuid.uuid4()}.csv"
    file_path.write_text(VENTES_CSV, encoding="utf-8")
    relative_path = str(file_path.relative_to(storage.base_dir))

    dataset = Dataset(
        user_id=user.id,
        name="Ventes test J46",
        original_filename="ventes.csv",
        file_path=relative_path,
        file_size_bytes=len(VENTES_CSV.encode("utf-8")),
        row_count=5,
        column_count=5,
        status="ready",
    )
    db_session.add(dataset)
    await db_session.commit()
    await db_session.refresh(dataset)
    return dataset


@pytest_asyncio.fixture
async def ready_dataset(db_session, registered_user: dict) -> Dataset:
    user = await db_session.get(User, UUID(registered_user["id"]))
    return await _create_ready_dataset(db_session, user)


@pytest_asyncio.fixture
async def owner(db_session, registered_user: dict) -> User:
    return await db_session.get(User, UUID(registered_user["id"]))


# ============================================================
# Opérations simples
# ============================================================

@pytest.mark.asyncio
async def test_sum(db_session, owner, ready_dataset):
    result = await execute_compute_from_dataset(
        db_session, owner, str(ready_dataset.id), operation="sum", column="ventes"
    )
    assert result["success"] is True
    assert result["result"]["raw_value"] == 1350.0
    assert "1350" in result["result"]["formatted"].replace(" ", "").replace("\xa0", "")


@pytest.mark.asyncio
async def test_mean(db_session, owner, ready_dataset):
    result = await execute_compute_from_dataset(
        db_session, owner, str(ready_dataset.id), operation="mean", column="ventes"
    )
    assert result["success"] is True
    assert result["result"]["raw_value"] == 270.0


@pytest.mark.asyncio
async def test_max(db_session, owner, ready_dataset):
    result = await execute_compute_from_dataset(
        db_session, owner, str(ready_dataset.id), operation="max", column="ventes"
    )
    assert result["success"] is True
    assert result["result"]["raw_value"] == 410.0


@pytest.mark.asyncio
async def test_min(db_session, owner, ready_dataset):
    result = await execute_compute_from_dataset(
        db_session, owner, str(ready_dataset.id), operation="min", column="ventes"
    )
    assert result["success"] is True
    assert result["result"]["raw_value"] == 150.0


@pytest.mark.asyncio
async def test_count_distinct(db_session, owner, ready_dataset):
    result = await execute_compute_from_dataset(
        db_session, owner, str(ready_dataset.id), operation="count_distinct", column="produit"
    )
    assert result["success"] is True
    assert result["result"]["raw_value"] == 3  # Chaise, Fauteuil, Table


# ============================================================
# top_n / group_by_agg
# ============================================================

@pytest.mark.asyncio
async def test_top_n_best_selling_product(db_session, owner, ready_dataset):
    """Le vrai test de verite : 'quel produit s'est le mieux vendu ?'"""
    result = await execute_compute_from_dataset(
        db_session,
        owner,
        str(ready_dataset.id),
        operation="top_n",
        column="ventes",
        group_by="produit",
        aggregation="sum",
        limit=1,
    )
    assert result["success"] is True
    breakdown = result["result"]["metadata"]["breakdown"]
    assert list(breakdown.keys())[0] == "Fauteuil"
    assert breakdown["Fauteuil"] == 600.0  # 410 + 190


@pytest.mark.asyncio
async def test_group_by_agg(db_session, owner, ready_dataset):
    result = await execute_compute_from_dataset(
        db_session,
        owner,
        str(ready_dataset.id),
        operation="group_by_agg",
        column="ventes",
        group_by="produit",
        aggregation="sum",
    )
    assert result["success"] is True
    breakdown = result["result"]["metadata"]["breakdown"]
    assert breakdown == {"Fauteuil": 600.0, "Chaise": 470.0, "Table": 280.0}


@pytest.mark.asyncio
async def test_top_n_requires_group_by(db_session, owner, ready_dataset):
    result = await execute_compute_from_dataset(
        db_session, owner, str(ready_dataset.id), operation="top_n", column="ventes"
    )
    assert result["success"] is False
    assert "group_by" in result["error"]


# ============================================================
# Corrélation
# ============================================================

@pytest.mark.asyncio
async def test_correlation(db_session, owner, ready_dataset):
    result = await execute_compute_from_dataset(
        db_session,
        owner,
        str(ready_dataset.id),
        operation="correlation",
        column="ventes",
        column2="remise",
    )
    assert result["success"] is True
    assert -1.0 <= result["result"]["correlation"] <= 1.0
    assert isinstance(result["result"]["correlation"], float)


# ============================================================
# Filtres (dont startswith — scénario d'acceptation J46)
# ============================================================

@pytest.mark.asyncio
async def test_filters_startswith(db_session, owner, ready_dataset):
    """'Compare les ventes des produits qui commencent par C vs F'."""
    result = await execute_compute_from_dataset(
        db_session,
        owner,
        str(ready_dataset.id),
        operation="sum",
        column="ventes",
        filters=[{"column": "produit", "op": "startswith", "value": "C"}],
    )
    assert result["success"] is True
    assert result["result"]["raw_value"] == 470.0  # Chaise : 320 + 150


# ============================================================
# Erreurs — jamais de crash, toujours success: False + message clair
# ============================================================

@pytest.mark.asyncio
async def test_unknown_column_returns_error(db_session, owner, ready_dataset):
    result = await execute_compute_from_dataset(
        db_session, owner, str(ready_dataset.id), operation="sum", column="colonne_inexistante"
    )
    assert result["success"] is False
    assert "colonne_inexistante" in result["error"].lower() or "introuvable" in result["error"].lower()


@pytest.mark.asyncio
async def test_dataset_not_found_returns_error(db_session, owner):
    result = await execute_compute_from_dataset(
        db_session, owner, str(uuid.uuid4()), operation="sum", column="ventes"
    )
    assert result["success"] is False
    assert "introuvable" in result["error"].lower()


@pytest.mark.asyncio
async def test_unknown_operation_returns_error(db_session, owner, ready_dataset):
    result = await execute_compute_from_dataset(
        db_session, owner, str(ready_dataset.id), operation="divide_by_zero", column="ventes"
    )
    assert result["success"] is False
    assert "opération" in result["error"].lower() or "operation" in result["error"].lower()


@pytest.mark.asyncio
async def test_invalid_dataset_id_returns_error(db_session, owner):
    result = await execute_compute_from_dataset(
        db_session, owner, "pas-un-uuid", operation="sum", column="ventes"
    )
    assert result["success"] is False


# ============================================================
# Ownership — un user ne peut pas calculer sur le dataset d'un autre
# ============================================================

@pytest.mark.asyncio
async def test_ownership_blocks_other_user(db_session, ready_dataset, register_second_user):
    other = await register_second_user()
    other_result = await db_session.execute(select(User).where(User.email == other["email"]))
    other_user = other_result.scalar_one()

    result = await execute_compute_from_dataset(
        db_session, other_user, str(ready_dataset.id), operation="sum", column="ventes"
    )
    assert result["success"] is False
    assert "introuvable" in result["error"].lower()


# ============================================================
# Schéma OpenAI du tool
# ============================================================

def test_tool_schema_shape():
    schema = get_compute_tool_schema()
    assert schema["type"] == "function"
    fn = schema["function"]
    assert fn["name"] == "compute_from_dataset"
    params = fn["parameters"]
    assert set(params["required"]) == {"dataset_id", "operation"}
    assert set(params["properties"]["operation"]["enum"]) == ALL_OPERATIONS
