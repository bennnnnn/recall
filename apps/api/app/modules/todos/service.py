"""Public todo operations for other product modules.

This module does not import home or chat, so Gmail and live talk can call it
without a circular import.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import TodoItem, User
from app.modules.todos import repository as todos_repo


async def create_external_todo(
    session: AsyncSession,
    user: User,
    *,
    content: str,
    topic: str,
    due_at: datetime | None,
    source: str,
) -> TodoItem:
    """Create a reminder owned by another product. The caller updates home cache."""
    return await todos_repo.create(
        session,
        user_id=user.id,
        content=content,
        topic=topic,
        due_at=due_at,
        source=source,
    )


async def list_owned_todos(session: AsyncSession, user_id: UUID, *, limit: int) -> list[TodoItem]:
    """Read a user's reminders without advancing recurrence."""
    return await todos_repo.list_for_user(session, user_id, limit=limit)
