from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suggestions.models import Suggestion


async def list_for_user(session: AsyncSession, user_id: UUID, *, limit: int) -> list[Suggestion]:
    """Every stored suggestion, dismissed and expired included (data export)."""
    result = await session.execute(
        select(Suggestion)
        .where(Suggestion.user_id == user_id)
        .order_by(Suggestion.created_at.asc(), Suggestion.id.asc())
        .limit(limit)
    )
    return list(result.scalars().all())
