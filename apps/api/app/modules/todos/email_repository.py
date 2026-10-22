"""Conditional finalization of a delivered dated To-do email occurrence."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import TodoItem
from app.modules.todos.occurrences import TodoEmailSnapshot


async def mark_email_sent_if_current(
    session: AsyncSession, snapshot: TodoEmailSnapshot, sent_at: datetime
) -> bool:
    """Stamp only the occurrence sent; push delivery has its own independent marker."""
    result = cast(
        CursorResult[Any],
        await session.execute(
            update(TodoItem)
            .where(
                TodoItem.id == snapshot.id,
                TodoItem.user_id == snapshot.user_id,
                TodoItem.content == snapshot.content,
                TodoItem.due_at == snapshot.due_at,
                TodoItem.recurrence_rule == snapshot.recurrence_rule,
                TodoItem.checked == snapshot.checked,
                TodoItem.email_sent_at == snapshot.email_sent_at,
            )
            .values(email_sent_at=sent_at)
            .execution_options(synchronize_session=False)
        ),
    )
    return result.rowcount > 0
