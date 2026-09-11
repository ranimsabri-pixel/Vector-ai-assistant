"""Endpoints Messages (S5 J30) — feedback + suppression (régénération).

2 endpoints :
- PATCH  /messages/{message_id}/feedback    Enregistre/retire le feedback
- DELETE /messages/{message_id}             Supprime un message (régénération)
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.conversation import MessageFeedbackUpdate, MessageResponse
from app.services.conversations import ConversationService

router = APIRouter(prefix="/messages", tags=["messages"])


@router.patch("/{message_id}/feedback", response_model=MessageResponse)
async def update_message_feedback(
    message_id: UUID,
    payload: MessageFeedbackUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Enregistre, change ou retire (feedback=null) le rating d'un message agent."""
    service = ConversationService(db)
    return await service.update_message_feedback(
        user=current_user,
        message_id=message_id,
        feedback=payload.feedback,
    )


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Supprime un message (utilisé lors de la régénération d'une réponse)."""
    service = ConversationService(db)
    await service.delete_message(user=current_user, message_id=message_id)
