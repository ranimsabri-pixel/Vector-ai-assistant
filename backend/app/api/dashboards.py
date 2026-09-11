"""Endpoints HTTP pour les dashboards persistants."""
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.services.dashboards import DashboardService

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


class DashboardSaveRequest(BaseModel):
    dataset_id: UUID
    title: str
    kpi_specs: list[dict[str, Any]]
    kpi_results: list[dict[str, Any]]


class DashboardResponse(BaseModel):
    id: UUID
    user_id: UUID
    dataset_id: UUID
    title: str
    kpi_specs: list[dict[str, Any]] | None = None
    kpi_results: list[dict[str, Any]] | None = None
    generated_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/save", response_model=DashboardResponse)
async def save_dashboard(
    payload: DashboardSaveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Sauvegarde un dashboard (ou met à jour le dashboard existant du dataset)."""
    service = DashboardService(db)
    return await service.save_dashboard(
        current_user,
        payload.dataset_id,
        payload.title,
        payload.kpi_specs,
        payload.kpi_results,
    )


@router.get("/by-dataset/{dataset_id}", response_model=DashboardResponse | None)
async def get_dashboard_by_dataset(
    dataset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Récupère le dashboard d'un dataset (None si pas encore généré)."""
    service = DashboardService(db)
    return await service.get_dashboard_by_dataset(current_user, dataset_id)


@router.get("", response_model=list[DashboardResponse])
async def list_dashboards(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Liste tous les dashboards de l'utilisateur."""
    service = DashboardService(db)
    return await service.list_user_dashboards(current_user)


@router.delete("/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard(
    dashboard_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Supprime un dashboard."""
    service = DashboardService(db)
    await service.delete_dashboard(current_user, dashboard_id)
