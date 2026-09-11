"""Endpoints HTTP pour les datasets."""
import json
import os
from typing import Annotated
from uuid import UUID

import pandas as pd
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.demo_guard import ensure_demo_enabled
from app.core.limiter import limiter
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.dataset import (
    ColumnOverridesUpdateRequest,
    DatasetColumnResponse,
    DatasetListResponse,
    DatasetResponse,
    KPIResultResponse,
)
from app.services.datasets import DatasetService, reprofile_in_background
from app.services.storage import FileStorage, get_storage

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post(
    "/upload",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(ensure_demo_enabled)],
)
@limiter.limit("3/hour")
async def upload_dataset(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
    file: Annotated[UploadFile, File(description="Fichier CSV ou Excel")],
    name: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    column_overrides: Annotated[
        str | None,
        Form(description="JSON : [{original_name, new_name?, type?, deleted?}]"),
    ] = None,
):
    """Upload un fichier de données (CSV ou Excel) et crée un dataset."""
    parsed_overrides = None
    if column_overrides:
        try:
            parsed_overrides = json.loads(column_overrides)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Paramètre 'column_overrides' : JSON invalide",
            ) from e
        if not isinstance(parsed_overrides, list):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Paramètre 'column_overrides' doit être une liste",
            )

    service = DatasetService(db, storage)
    return await service.upload(
        current_user,
        file,
        name=name,
        description=description,
        column_overrides=parsed_overrides,
    )


@router.get("", response_model=list[DatasetListResponse])
async def list_datasets(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Liste les datasets de l'utilisateur connecté (récents d'abord)."""
    service = DatasetService(db, storage)
    return await service.list_user_datasets(current_user)


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Récupère un dataset par son ID (avec sample inclus)."""
    service = DatasetService(db, storage)
    return await service.get_dataset(current_user, dataset_id)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Supprime un dataset (et son fichier sur le disque)."""
    service = DatasetService(db, storage)
    await service.delete_dataset(current_user, dataset_id)


@router.post("/{dataset_id}/profile", response_model=DatasetResponse)
async def profile_dataset(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Lance le profilage automatique des colonnes du dataset."""
    service = DatasetService(db, storage)
    return await service.profile(current_user, dataset_id)


@router.post("/{dataset_id}/reprofile", response_model=DatasetResponse)
async def reprofile_dataset(
    dataset_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Relance le profilage complet d'un dataset deja pret (utile pour
    calculer les statistiques enrichies J39 sur un dataset profile avant
    leur introduction). Retourne immediatement avec status='profiling' ;
    le profilage tourne en tache de fond, a poller via GET /datasets/{id}."""
    service = DatasetService(db, storage)
    dataset = await service.mark_for_reprofile(current_user, dataset_id)
    background_tasks.add_task(reprofile_in_background, dataset_id, current_user.id)
    return dataset


@router.get(
    "/{dataset_id}/columns",
    response_model=list[DatasetColumnResponse],
)
async def get_dataset_columns(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Récupère les colonnes profilées d'un dataset."""
    service = DatasetService(db, storage)
    return await service.get_dataset_columns(current_user, dataset_id)


@router.patch("/{dataset_id}/columns", response_model=DatasetResponse)
async def update_dataset_columns(
    dataset_id: UUID,
    payload: ColumnOverridesUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Corrige les colonnes d'un dataset déjà profilé (renommer / supprimer /
    forcer un type) puis relance automatiquement le profilage."""
    service = DatasetService(db, storage)
    overrides = [o.model_dump(exclude_none=True) for o in payload.overrides]
    return await service.update_column_overrides(current_user, dataset_id, overrides)


@router.get("/{dataset_id}/sample")
async def sample_dataset(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
):
    """Exporte un echantillon (100/500/1000 lignes) du dataset en CSV."""
    service = DatasetService(db, storage)
    dataset = await service.get_dataset(current_user, dataset_id)

    full_path = storage.get_full_path(dataset.file_path)
    ext = os.path.splitext(dataset.original_filename)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(full_path).head(limit)
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(full_path).head(limit)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Format non supporté : {ext}")

    csv_content = df.to_csv(index=False)

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{dataset.name}_sample_{limit}.csv"'
        },
    )


@router.get("/{dataset_id}/columns/{column_name}/values")
async def get_column_values(
    dataset_id: UUID,
    column_name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Valeurs uniques d'une colonne (pour les filtres categoriels des dashboards)."""
    service = DatasetService(db, storage)
    return await service.get_column_values(current_user, dataset_id, column_name)


@router.post("/{dataset_id}/analyze", response_model=DatasetResponse)
async def analyze_dataset_endpoint(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """
    Lance l'analyse sémantique business du dataset.
    Détecte le domaine (CRM, marketing, sales, finance...) et propose des KPIs.
    Le dataset doit avoir été profilé au préalable.
    """
    service = DatasetService(db, storage)
    return await service.analyze(current_user, dataset_id)


@router.post(
    "/{dataset_id}/auto-kpis/generate",
    response_model=DatasetResponse,
)
async def generate_auto_kpis_endpoint(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """
    Génère automatiquement la liste des KPIs calculables pour le dataset.
    Le dataset doit avoir été profilé au préalable.
    """
    service = DatasetService(db, storage)
    return await service.generate_auto_kpis(current_user, dataset_id)


@router.post(
    "/{dataset_id}/auto-kpis/{spec_id}/calculate",
    response_model=KPIResultResponse,
)
async def calculate_auto_kpi_endpoint(
    dataset_id: UUID,
    spec_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Calcule la valeur d'un KPI auto-généré spécifique."""
    service = DatasetService(db, storage)
    result = await service.calculate_auto_kpi(current_user, dataset_id, spec_id)
    return result.to_dict()


@router.post(
    "/{dataset_id}/auto-kpis/calculate-all",
    response_model=list[KPIResultResponse],
)
async def calculate_all_auto_kpis_endpoint(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Calcule TOUS les KPIs auto-générés en une seule passe (batch)."""
    service = DatasetService(db, storage)
    results = await service.calculate_all_auto_kpis(current_user, dataset_id)
    return [r.to_dict() for r in results]
@router.post(
    "/{dataset_id}/advanced-kpis/generate",
    response_model=DatasetResponse,
)
async def generate_advanced_kpis_endpoint(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """
    Génère des KPIs avancés via patterns business + traduction LLM.
    S'ajoutent aux auto_kpis simples déjà générés (déduplication par id).
    """
    service = DatasetService(db, storage)
    return await service.generate_advanced_kpis(current_user, dataset_id)
