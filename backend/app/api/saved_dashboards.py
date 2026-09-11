"""Endpoints SavedDashboard (S5 J36) — dashboards personnalises + widgets.

Prefixe /saved-dashboards (et non /dashboards, deja pris par les dashboards
generes par les tools LLM, cf. api/dashboards.py).

11 endpoints :
- POST   /saved-dashboards                              Creer un dashboard
- GET    /saved-dashboards                              Lister ses dashboards
- GET    /saved-dashboards/{id}                         Detail avec widgets
- GET    /saved-dashboards/{id}/data                    Donnees calculees de TOUS les widgets
- GET    /saved-dashboards/{id}/export-data              Export CSV du dataset source (filtre)
- POST   /saved-dashboards/{id}/preview                 Donnees d'un widget non persiste (wizard)
- PATCH  /saved-dashboards/{id}                         Renommer / redecrire
- DELETE /saved-dashboards/{id}                         Supprimer
- POST   /saved-dashboards/{id}/widgets                 Ajouter un widget
- GET    /saved-dashboards/{id}/widgets/{wid}/data      Recalculer UN widget
- PATCH  /saved-dashboards/{id}/widgets/{wid}           Modifier un widget
- DELETE /saved-dashboards/{id}/widgets/{wid}           Supprimer un widget
- POST   /saved-dashboards/{id}/widgets/reorder         Reordonner
"""
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.saved_dashboard import (
    DashboardWidgetCreate,
    DashboardWidgetResponse,
    DashboardWidgetUpdate,
    SavedDashboardCreate,
    SavedDashboardDetail,
    SavedDashboardSummary,
    SavedDashboardUpdate,
    WidgetPreviewRequest,
    WidgetReorderPayload,
)
from app.services.saved_dashboards import SavedDashboardService
from app.services.storage import FileStorage, get_storage

router = APIRouter(prefix="/saved-dashboards", tags=["saved-dashboards"])


def _parse_filters(filters: str | None) -> list[dict] | None:
    """Parse le query param filters (JSON encode) -> list[dict] ou None."""
    if not filters:
        return None
    try:
        parsed = json.loads(filters)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Paramètre 'filters' : JSON invalide"
        ) from e
    if not isinstance(parsed, list):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Paramètre 'filters' doit être une liste"
        )
    return parsed


# ============================================================
# Create
# ============================================================

@router.post("", response_model=SavedDashboardDetail, status_code=status.HTTP_201_CREATED)
async def create_saved_dashboard(
    payload: SavedDashboardCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Cree un nouveau dashboard personnalise (avec ou sans widgets initiaux)."""
    service = SavedDashboardService(db, storage)
    dashboard = await service.create_dashboard(
        user=current_user,
        name=payload.name,
        dataset_id=payload.dataset_id,
        description=payload.description,
        widgets=payload.widgets,
    )
    return await service.get_dashboard(current_user, dashboard.id)


# ============================================================
# Read
# ============================================================

@router.get("", response_model=list[SavedDashboardSummary])
async def list_saved_dashboards(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Liste mes dashboards personnalises."""
    service = SavedDashboardService(db, storage)
    return await service.list_user_dashboards(current_user)


@router.get("/{dashboard_id}", response_model=SavedDashboardDetail)
async def get_saved_dashboard(
    dashboard_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Detail d'un dashboard avec la liste de ses widgets (config, pas les donnees calculees)."""
    service = SavedDashboardService(db, storage)
    return await service.get_dashboard(current_user, dashboard_id)


@router.get("/{dashboard_id}/data")
async def get_saved_dashboard_data(
    dashboard_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
    filters: Annotated[str | None, Query(description="Filtres JSON, ex: [{\"column\":\"region\",\"op\":\"eq\",\"value\":\"North\"}]")] = None,
):
    """Calcule les donnees de TOUS les widgets du dashboard (dict {widget_id: data})."""
    service = SavedDashboardService(db, storage)
    parsed_filters = _parse_filters(filters)
    return await service.compute_dashboard_data(current_user, dashboard_id, parsed_filters)


@router.get("/{dashboard_id}/export-data")
async def export_dashboard_data(
    dashboard_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
    filters: Annotated[str | None, Query()] = None,
):
    """Exporte le dataset source du dashboard en CSV (filtres optionnels appliques)."""
    service = SavedDashboardService(db, storage)
    parsed_filters = _parse_filters(filters)
    csv_text, filename = await service.export_filtered_csv(
        current_user, dashboard_id, parsed_filters
    )
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{dashboard_id}/preview")
async def preview_widget(
    dashboard_id: UUID,
    payload: WidgetPreviewRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Calcule les donnees d'un widget pas encore enregistre (etape preview du wizard)."""
    service = SavedDashboardService(db, storage)
    return await service.preview_widget_data(
        current_user, dashboard_id, payload.widget_type, payload.config
    )


# ============================================================
# Update
# ============================================================

@router.patch("/{dashboard_id}", response_model=SavedDashboardDetail)
async def update_saved_dashboard(
    dashboard_id: UUID,
    payload: SavedDashboardUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Renomme et/ou change la description d'un dashboard."""
    service = SavedDashboardService(db, storage)
    await service.update_dashboard(
        current_user, dashboard_id, name=payload.name, description=payload.description
    )
    return await service.get_dashboard(current_user, dashboard_id)


# ============================================================
# Delete
# ============================================================

@router.delete("/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_dashboard(
    dashboard_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Supprime un dashboard personnalise (le dataset source reste intact)."""
    service = SavedDashboardService(db, storage)
    await service.delete_dashboard(current_user, dashboard_id)


# ============================================================
# Widgets — CRUD
# ============================================================

@router.post(
    "/{dashboard_id}/widgets",
    response_model=DashboardWidgetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_widget(
    dashboard_id: UUID,
    payload: DashboardWidgetCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Ajoute un widget a un dashboard existant."""
    service = SavedDashboardService(db, storage)
    return await service.add_widget(current_user, dashboard_id, payload)


@router.get("/{dashboard_id}/widgets/{widget_id}/data")
async def get_widget_data(
    dashboard_id: UUID,
    widget_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
    filters: Annotated[str | None, Query()] = None,
):
    """Recalcule UN seul widget (utile pour la preview du modal d'edition)."""
    service = SavedDashboardService(db, storage)
    parsed_filters = _parse_filters(filters)
    return await service.compute_single_widget_data(
        current_user, dashboard_id, widget_id, parsed_filters
    )


@router.patch("/{dashboard_id}/widgets/{widget_id}", response_model=DashboardWidgetResponse)
async def update_widget(
    dashboard_id: UUID,
    widget_id: UUID,
    payload: DashboardWidgetUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Modifie la config/titre/position d'un widget."""
    service = SavedDashboardService(db, storage)
    return await service.update_widget(current_user, dashboard_id, widget_id, payload)


@router.delete(
    "/{dashboard_id}/widgets/{widget_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_widget(
    dashboard_id: UUID,
    widget_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Supprime un widget."""
    service = SavedDashboardService(db, storage)
    await service.delete_widget(current_user, dashboard_id, widget_id)


@router.post("/{dashboard_id}/widgets/reorder", response_model=SavedDashboardDetail)
async def reorder_widgets(
    dashboard_id: UUID,
    payload: WidgetReorderPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[FileStorage, Depends(get_storage)],
):
    """Reordonne les widgets : position = index dans widget_ids."""
    service = SavedDashboardService(db, storage)
    await service.reorder_widgets(current_user, dashboard_id, payload.widget_ids)
    return await service.get_dashboard(current_user, dashboard_id)
