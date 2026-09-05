"""Conditional finalization of a delivered Schedule email occurrence."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import TodoItem


@dataclass(frozen=True)
class TodoEmailSnapshot:
    id: UUID
    user_id: UUID
    content: str
    due_at: datetime | None
    recurrence_rule: str | None
    checked: bool
    email_sent_at: datetime | None

    @classmethod
    def from_todo(cls, todo: TodoItem) -> "TodoEmailSnapshot":
        return cls(
            todo.id,
            todo.user_id,
            todo.content,
            todo.due_at,
            todo.recurrence_rule,
            todo.checked,
            todo.email_sent_at,
        )


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
