"""Reads of the retired suggestions table that the account still needs."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suggestions import repository as suggestions_repo
from app.modules.suggestions.models import Suggestion


async def list_for_export(session: AsyncSession, user_id: UUID, *, limit: int) -> list[Suggestion]:
    """Every suggestion stored for the user, for their data export."""
    return await suggestions_repo.list_for_user(session, user_id, limit=limit)
