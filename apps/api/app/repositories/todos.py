from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import TodoItem


async def list_for_user(
    session: AsyncSession, user_id: UUID, *, limit: int = 200, offset: int = 0
) -> list[TodoItem]:
    result = await session.execute(
        select(TodoItem)
        .where(TodoItem.user_id == user_id)
        .order_by(TodoItem.checked.asc(), TodoItem.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, todo_id: UUID, user_id: UUID) -> TodoItem | None:
    result = await session.execute(
        select(TodoItem).where(TodoItem.id == todo_id, TodoItem.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    user_id: UUID,
    content: str,
    chat_id: UUID | None = None,
) -> TodoItem:
    todo = TodoItem(user_id=user_id, content=content, chat_id=chat_id)
    session.add(todo)
    await session.commit()
    await session.refresh(todo)
    return todo


async def update(session: AsyncSession, todo: TodoItem, **fields: Any) -> TodoItem:
    for key, value in fields.items():
        if value is not None:
            if hasattr(todo, key):
                setattr(todo, key, value)
    await session.commit()
    await session.refresh(todo)
    return todo


async def delete_by_id(session: AsyncSession, todo_id: UUID, user_id: UUID) -> bool:
    result = cast(
        CursorResult[Any],
        await session.execute(
            delete(TodoItem).where(TodoItem.id == todo_id, TodoItem.user_id == user_id)
        ),
    )
    await session.commit()
    return result.rowcount > 0
