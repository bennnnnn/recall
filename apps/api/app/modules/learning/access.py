"""Owned-project lookup for chat and other callers outside Learning."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.learning.models import Learning
from app.modules.learning.repository import get_by_id


async def get_owned_project(
    session: AsyncSession, project_id: UUID, user_id: UUID
) -> Learning | None:
    return await get_by_id(session, project_id, user_id)
