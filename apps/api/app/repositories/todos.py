from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import TodoItem

DEFAULT_TOPIC = "General"


async def list_due_soon(
    session: AsyncSession,
    user_id: UUID,
    *,
    before_utc: datetime,
) -> list[TodoItem]:
    """Open todos with due_at at or before *before_utc*, soonest first."""
    result = await session.execute(
        select(TodoItem)
        .where(
            TodoItem.user_id == user_id,
            TodoItem.checked.is_(False),
            TodoItem.due_at.isnot(None),
            TodoItem.due_at <= before_utc,
        )
        .order_by(TodoItem.due_at.asc())
        .limit(5)
    )
    return list(result.scalars().all())


async def list_for_user(
    session: AsyncSession, user_id: UUID, *, limit: int = 200, offset: int = 0
) -> list[TodoItem]:
    result = await session.execute(
        select(TodoItem)
        .where(TodoItem.user_id == user_id)
        .order_by(
            TodoItem.topic.asc(),
            TodoItem.sort_order.asc().nulls_last(),
            TodoItem.checked.asc(),
            TodoItem.created_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def next_sort_order(
    session: AsyncSession, user_id: UUID, topic: str, *, list_only: bool = True
) -> int:
    normalized = topic.strip() or DEFAULT_TOPIC
    stmt = select(func.max(TodoItem.sort_order)).where(
        TodoItem.user_id == user_id,
        TodoItem.topic == normalized,
    )
    if list_only:
        stmt = stmt.where(TodoItem.due_at.is_(None))
    result = await session.execute(stmt)
    current = result.scalar()
    return int(current or 0) + 1


async def list_topics(session: AsyncSession, user_id: UUID) -> list[str]:
    result = await session.execute(
        select(TodoItem.topic)
        .where(TodoItem.user_id == user_id)
        .distinct()
        .order_by(TodoItem.topic.asc())
    )
    return [row[0] for row in result.all()]


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
    topic: str = DEFAULT_TOPIC,
    chat_id: UUID | None = None,
    due_at: datetime | None = None,
    sort_order: int | None = None,
) -> TodoItem:
    normalized_topic = topic.strip() or DEFAULT_TOPIC
    resolved_sort = sort_order
    if resolved_sort is None and due_at is None:
        resolved_sort = await next_sort_order(session, user_id, normalized_topic)
    todo = TodoItem(
        user_id=user_id,
        content=content.strip(),
        topic=normalized_topic,
        chat_id=chat_id,
        due_at=due_at,
        sort_order=resolved_sort,
    )
    session.add(todo)
    await session.commit()
    await session.refresh(todo)
    return todo


async def update(session: AsyncSession, todo: TodoItem, **fields: Any) -> TodoItem:
    for key, value in fields.items():
        if hasattr(todo, key):
            if key == "topic" and isinstance(value, str):
                value = value.strip() or DEFAULT_TOPIC
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


async def delete_by_topic(session: AsyncSession, user_id: UUID, topic: str) -> int:
    normalized = topic.strip()
    if not normalized:
        return 0
    result = cast(
        CursorResult[Any],
        await session.execute(
            delete(TodoItem).where(
                TodoItem.user_id == user_id,
                func.lower(TodoItem.topic) == normalized.lower(),
                TodoItem.due_at.is_(None),
            )
        ),
    )
    await session.commit()
    return int(result.rowcount or 0)


async def reorder(
    session: AsyncSession,
    user_id: UUID,
    items: list[tuple[UUID, int, str | None]],
) -> list[TodoItem]:
    updated: list[TodoItem] = []
    for todo_id, sort_order, topic in items:
        todo = await get_by_id(session, todo_id, user_id)
        if not todo:
            continue
        fields: dict[str, Any] = {"sort_order": sort_order}
        if topic is not None:
            fields["topic"] = topic.strip() or DEFAULT_TOPIC
        updated.append(await update(session, todo, **fields))
    return updated
