from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.orm import User
from app.models.schemas import SearchResultItem, SearchResults
from app.services import search as search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResults)
async def search(
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SearchResults:
    results, total = await search_service.search_conversations(
        session, user.id, query=q, limit=limit, offset=offset
    )
    return SearchResults(
        results=[SearchResultItem.model_validate(r) for r in results],
        total=total,
    )
