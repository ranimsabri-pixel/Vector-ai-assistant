"""SavedDashboardService (S5 J36) — CRUD dashboards personnalises + widgets.

Pattern identique a ConversationService/CorpusService : constructeur (db,
storage), methodes async avec ownership check systematique via user en 1er arg.
"""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.dataset import Dataset
from app.db.models.saved_dashboard import DashboardWidget, SavedDashboard
from app.db.models.user import User
from app.schemas.saved_dashboard import DashboardWidgetCreate, DashboardWidgetUpdate
from app.services.storage import FileStorage
from app.services.widget_compute import _load_dataset, apply_filters, compute_widget_data


class SavedDashboardService:
    def __init__(self, db: AsyncSession, storage: FileStorage):
        self.db = db
        self.storage = storage

    # ============================================================
    # Create
    # ============================================================

    async def create_dashboard(
        self,
        user: User,
        name: str,
        dataset_id: UUID,
        description: str | None = None,
        widgets: list[DashboardWidgetCreate] | None = None,
    ) -> SavedDashboard:
        """Cree un dashboard (avec ou sans widgets initiaux).

        Verifie que le dataset appartient a l'user AVANT de creer quoi que
        ce soit.
        """
        dataset_result = await self.db.execute(
            select(Dataset).where(
                Dataset.id == dataset_id, Dataset.user_id == user.id
            )
        )
        if dataset_result.scalar_one_or_none() is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Dataset introuvable ou accès refusé"
            )

        dashboard = SavedDashboard(
            user_id=user.id,
            dataset_id=dataset_id,
            name=name,
            description=description,
        )
        self.db.add(dashboard)
        await self.db.flush()  # obtient dashboard.id sans commit

        for i, w in enumerate(widgets or []):
            self.db.add(
                DashboardWidget(
                    dashboard_id=dashboard.id,
                    widget_type=w.widget_type,
                    title=w.title,
                    config=w.config,
                    position=w.position if w.position else i,
                )
            )

        await self.db.commit()
        await self.db.refresh(dashboard)
        return dashboard

    # ============================================================
    # Read
    # ============================================================

    async def list_user_dashboards(self, user: User) -> list[dict]:
        """Liste des dashboards de l'utilisateur avec dataset_name + widget_count."""
        widget_count_subq = (
            select(
                DashboardWidget.dashboard_id,
                func.count(DashboardWidget.id).label("widget_count"),
            )
            .group_by(DashboardWidget.dashboard_id)
            .subquery()
        )

        query = (
            select(
                SavedDashboard,
                Dataset.name.label("dataset_name"),
                func.coalesce(widget_count_subq.c.widget_count, 0).label("widget_count"),
            )
            .join(Dataset, SavedDashboard.dataset_id == Dataset.id)
            .outerjoin(
                widget_count_subq,
                widget_count_subq.c.dashboard_id == SavedDashboard.id,
            )
            .where(SavedDashboard.user_id == user.id)
            .order_by(SavedDashboard.updated_at.desc())
        )

        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "id": dashboard.id,
                "name": dashboard.name,
                "description": dashboard.description,
                "dataset_id": dashboard.dataset_id,
                "dataset_name": dataset_name,
                "widget_count": widget_count,
                "created_at": dashboard.created_at,
                "updated_at": dashboard.updated_at,
            }
            for dashboard, dataset_name, widget_count in rows
        ]

    async def get_dashboard(self, user: User, dashboard_id: UUID) -> dict:
        """Detail complet d'un dashboard avec ses widgets."""
        query = (
            select(SavedDashboard, Dataset.name.label("dataset_name"))
            .join(Dataset, SavedDashboard.dataset_id == Dataset.id)
            .options(selectinload(SavedDashboard.widgets))
            .where(
                SavedDashboard.id == dashboard_id,
                SavedDashboard.user_id == user.id,
            )
        )
        result = await self.db.execute(query)
        row = result.first()
        if row is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Dashboard introuvable ou accès refusé"
            )
        dashboard, dataset_name = row

        return {
            "id": dashboard.id,
            "name": dashboard.name,
            "description": dashboard.description,
            "dataset_id": dashboard.dataset_id,
            "dataset_name": dataset_name,
            "widget_count": len(dashboard.widgets),
            "created_at": dashboard.created_at,
            "updated_at": dashboard.updated_at,
            "widgets": dashboard.widgets,
        }

    # ============================================================
    # Update
    # ============================================================

    async def update_dashboard(
        self,
        user: User,
        dashboard_id: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> SavedDashboard:
        dashboard = await self._get_owned(user, dashboard_id)
        if name is not None:
            dashboard.name = name
        if description is not None:
            dashboard.description = description
        await self.db.commit()
        await self.db.refresh(dashboard)
        return dashboard

    # ============================================================
    # Delete
    # ============================================================

    async def delete_dashboard(self, user: User, dashboard_id: UUID) -> None:
        """Supprime un dashboard (et ses widgets par cascade). Le dataset reste intact."""
        dashboard = await self._get_owned(user, dashboard_id)
        await self.db.delete(dashboard)
        await self.db.commit()

    # ============================================================
    # Widgets — CRUD
    # ============================================================

    async def add_widget(
        self, user: User, dashboard_id: UUID, payload: DashboardWidgetCreate
    ) -> DashboardWidget:
        dashboard = await self._get_owned(user, dashboard_id)

        widget = DashboardWidget(
            dashboard_id=dashboard.id,
            widget_type=payload.widget_type,
            title=payload.title,
            config=payload.config,
            position=payload.position,
        )
        self.db.add(widget)

        from sqlalchemy.sql import func as sql_func
        dashboard.updated_at = sql_func.now()

        await self.db.commit()
        await self.db.refresh(widget)
        return widget

    async def update_widget(
        self,
        user: User,
        dashboard_id: UUID,
        widget_id: UUID,
        payload: DashboardWidgetUpdate,
    ) -> DashboardWidget:
        await self._get_owned(user, dashboard_id)
        widget = await self._get_owned_widget(dashboard_id, widget_id)

        if payload.title is not None:
            widget.title = payload.title
        if payload.config is not None:
            widget.config = payload.config
        if payload.position is not None:
            widget.position = payload.position

        await self.db.commit()
        await self.db.refresh(widget)
        return widget

    async def delete_widget(
        self, user: User, dashboard_id: UUID, widget_id: UUID
    ) -> None:
        await self._get_owned(user, dashboard_id)
        widget = await self._get_owned_widget(dashboard_id, widget_id)
        await self.db.delete(widget)
        await self.db.commit()

    async def reorder_widgets(
        self, user: User, dashboard_id: UUID, widget_ids: list[UUID]
    ) -> None:
        """Reordonne les widgets : position = index dans widget_ids."""
        await self._get_owned(user, dashboard_id)

        result = await self.db.execute(
            select(DashboardWidget).where(
                DashboardWidget.dashboard_id == dashboard_id,
                DashboardWidget.id.in_(widget_ids),
            )
        )
        widgets_by_id = {w.id: w for w in result.scalars().all()}

        for position, widget_id in enumerate(widget_ids):
            widget = widgets_by_id.get(widget_id)
            if widget is not None:
                widget.position = position

        await self.db.commit()

    # ============================================================
    # Computation — donnees calculees pour affichage
    # ============================================================

    async def compute_dashboard_data(
        self, user: User, dashboard_id: UUID, filters: list[dict] | None = None
    ) -> dict:
        """Calcule les donnees de TOUS les widgets d'un dashboard."""
        detail = await self.get_dashboard(user, dashboard_id)
        dataset = await self.db.get(Dataset, detail["dataset_id"])

        return {
            str(widget.id): compute_widget_data(widget, dataset, self.storage, filters)
            for widget in detail["widgets"]
        }

    async def compute_single_widget_data(
        self,
        user: User,
        dashboard_id: UUID,
        widget_id: UUID,
        filters: list[dict] | None = None,
    ) -> dict:
        """Recalcule UN seul widget (utile pour la preview du modal d'edition)."""
        dashboard = await self._get_owned(user, dashboard_id)
        widget = await self._get_owned_widget(dashboard_id, widget_id)
        dataset = await self.db.get(Dataset, dashboard.dataset_id)
        return compute_widget_data(widget, dataset, self.storage, filters)

    async def export_filtered_csv(
        self,
        user: User,
        dashboard_id: UUID,
        filters: list[dict] | None = None,
    ) -> tuple[str, str]:
        """Exporte le dataset source (filtre applique) en CSV.

        Retourne (csv_text, filename).
        """
        dashboard = await self._get_owned(user, dashboard_id)
        dataset = await self.db.get(Dataset, dashboard.dataset_id)
        df = _load_dataset(dataset, self.storage)
        df = apply_filters(df, filters)
        filename = f"{dashboard.name}.csv".replace("/", "-").replace("\\", "-")
        return df.to_csv(index=False), filename

    async def preview_widget_data(
        self,
        user: User,
        dashboard_id: UUID,
        widget_type: str,
        config: dict,
        filters: list[dict] | None = None,
    ) -> dict:
        """Calcule les donnees d'un widget non persiste (etape preview du wizard).

        Construit un DashboardWidget en memoire (jamais ajoute a la session,
        donc jamais ecrit en base) pour reutiliser compute_widget_data tel quel.
        """
        dashboard = await self._get_owned(user, dashboard_id)
        dataset = await self.db.get(Dataset, dashboard.dataset_id)
        draft_widget = DashboardWidget(
            dashboard_id=dashboard.id,
            widget_type=widget_type,
            title="__preview__",
            config=config,
            position=0,
        )
        return compute_widget_data(draft_widget, dataset, self.storage, filters)

    # ============================================================
    # Helpers internes
    # ============================================================

    async def _get_owned(self, user: User, dashboard_id: UUID) -> SavedDashboard:
        """Recupere un dashboard + ownership check. Raise 404 si absent."""
        result = await self.db.execute(
            select(SavedDashboard).where(
                SavedDashboard.id == dashboard_id,
                SavedDashboard.user_id == user.id,
            )
        )
        dashboard = result.scalar_one_or_none()
        if dashboard is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Dashboard introuvable ou accès refusé"
            )
        return dashboard

    async def _get_owned_widget(
        self, dashboard_id: UUID, widget_id: UUID
    ) -> DashboardWidget:
        """Recupere un widget appartenant au dashboard donne. Raise 404 si absent.

        Suppose que l'ownership du dashboard a deja ete verifie par
        l'appelant (_get_owned) -- evite une jointure redondante.
        """
        result = await self.db.execute(
            select(DashboardWidget).where(
                DashboardWidget.id == widget_id,
                DashboardWidget.dashboard_id == dashboard_id,
            )
        )
        widget = result.scalar_one_or_none()
        if widget is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Widget introuvable"
            )
        return widget
