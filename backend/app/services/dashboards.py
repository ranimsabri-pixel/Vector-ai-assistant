"""
Service de gestion des dashboards persistants.

Un dashboard est un snapshot des KPIs calculés à un moment donné. Ça permet :
- D'avoir un historique des dashboards générés
- De recharger un dashboard sans recalculer (cache)
- De partager un dashboard par URL stable
"""
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.dashboard import Dashboard
from app.db.models.dataset import Dataset
from app.db.models.user import User


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_dashboard(
        self,
        user: User,
        dataset_id: UUID,
        title: str,
        kpi_specs: list[dict[str, Any]],
        kpi_results: list[dict[str, Any]],
    ) -> Dashboard:
        """
        Sauvegarde un dashboard (ou met à jour s'il existe déjà pour ce dataset).
        Un seul dashboard par dataset par utilisateur.
        """
        # Vérifie que le dataset appartient à l'utilisateur
        dataset = await self.db.get(Dataset, dataset_id)
        if not dataset or dataset.user_id != user.id:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Dataset introuvable",
            )

        # Cherche un dashboard existant pour ce dataset
        result = await self.db.execute(
            select(Dashboard).where(
                Dashboard.dataset_id == dataset_id,
                Dashboard.user_id == user.id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.title = title
            existing.kpi_specs = kpi_specs
            existing.kpi_results = kpi_results
            existing.generated_at = datetime.now(UTC)
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        else:
            new_dashboard = Dashboard(
                user_id=user.id,
                dataset_id=dataset_id,
                title=title,
                type="kpi_general",
                kpi_specs=kpi_specs,
                kpi_results=kpi_results,
                generated_at=datetime.now(UTC),
            )
            self.db.add(new_dashboard)
            await self.db.commit()
            await self.db.refresh(new_dashboard)
            return new_dashboard

    async def get_dashboard_by_dataset(
        self, user: User, dataset_id: UUID
    ) -> Dashboard | None:
        """Retourne le dashboard d'un dataset s'il existe."""
        result = await self.db.execute(
            select(Dashboard).where(
                Dashboard.dataset_id == dataset_id,
                Dashboard.user_id == user.id,
            )
        )
        return result.scalar_one_or_none()

    async def list_user_dashboards(self, user: User) -> list[Dashboard]:
        """Liste tous les dashboards de l'utilisateur, plus récents d'abord."""
        result = await self.db.execute(
            select(Dashboard)
            .where(Dashboard.user_id == user.id)
            .order_by(Dashboard.generated_at.desc().nullslast())
        )
        return list(result.scalars().all())

    async def delete_dashboard(self, user: User, dashboard_id: UUID) -> None:
        """Supprime un dashboard de l'utilisateur."""
        result = await self.db.execute(
            select(Dashboard).where(
                Dashboard.id == dashboard_id,
                Dashboard.user_id == user.id,
            )
        )
        dashboard = result.scalar_one_or_none()
        if not dashboard:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Dashboard introuvable",
            )
        await self.db.delete(dashboard)
        await self.db.commit()
