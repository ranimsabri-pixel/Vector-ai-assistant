"""Endpoints agents."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.agent import Agent
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.agent import AgentResponse

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[Agent]:
    """Retourne la liste des agents disponibles (Vector pour l'instant)."""
    result = await db.execute(select(Agent))
    return list(result.scalars().all())


@router.get("/{slug}", response_model=AgentResponse)
async def get_agent(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Agent:
    """Retourne un agent par son slug."""
    from fastapi import HTTPException, status

    result = await db.execute(select(Agent).where(Agent.slug == slug))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent introuvable")
    return agent
