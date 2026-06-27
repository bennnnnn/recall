from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.orm import User
from app.models.schemas import SuggestionOut
from app.repositories import suggestions as suggestions_repo

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


@router.get("", response_model=list[SuggestionOut])
async def list_suggestions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[SuggestionOut]:
    items = await suggestions_repo.list_active(session, user.id)
    return [SuggestionOut.model_validate(item) for item in items]


@router.post("/{suggestion_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_suggestion(
    suggestion_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    ok = await suggestions_repo.dismiss(session, suggestion_id, user.id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found"
        )
