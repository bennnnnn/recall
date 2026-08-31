"""HTTP-facing todos CRUD (create/update/delete + home cache invalidate)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import TodoItem, User
from app.repositories import chats as chats_repo
from app.repositories import todos as todos_repo
from app.services import home as home_service
from app.services.time_context import normalize_due_at
from app.services.todos.recurrence import (
    RecurrenceRule,
    is_recurrence_rule,
    next_recurring_due,
    snap_first_due,
)


class TodosError(Exception):
    def __init__(self, detail: str, *, status_code: int) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


async def list_todos(
    session: AsyncSession, user: User, *, limit: int = 1000, offset: int = 0
) -> list[TodoItem]:
    items = await todos_repo.list_for_user(session, user.id, limit=limit, offset=offset)
    await _advance_past_recurring(session, items, timezone=user.timezone)
    return items


async def list_topics(session: AsyncSession, user: User) -> list[str]:
    return await todos_repo.list_topics(session, user.id)


async def create_todo(
    session: AsyncSession,
    user: User,
    *,
    content: str,
    topic: str | None,
    chat_id: UUID | None,
    project_id: UUID | None,
    due_at: datetime | None,
    recurrence_rule: RecurrenceRule | None = None,
) -> TodoItem:
    if chat_id is not None:
        chat = await chats_repo.get_by_id(session, chat_id, user.id)
        if chat is None:
            raise TodosError("Chat not found", status_code=400)
    if project_id is not None:
        raise TodosError("Reminders cannot be linked to a Learning project", status_code=400)
    normalized_due = normalize_due_at(due_at, user.timezone)
    if normalized_due is not None and recurrence_rule:
        normalized_due = snap_first_due(normalized_due, recurrence_rule, timezone=user.timezone)
    if normalized_due is None:
        recurrence_rule = None
    item = await todos_repo.create(
        session,
        user_id=user.id,
        content=content,
        topic=topic or todos_repo.DEFAULT_TOPIC,
        chat_id=chat_id,
        project_id=project_id,
        due_at=normalized_due,
        recurrence_rule=recurrence_rule,
    )
    await home_service.invalidate_home_cache(user.id)
    return item


async def reorder_todos(
    session: AsyncSession,
    user: User,
    items: list[tuple[UUID, int, str | None]],
) -> list[TodoItem]:
    reordered = await todos_repo.reorder(session, user.id, items)
    await home_service.invalidate_home_cache(user.id)
    return reordered


async def update_todo(
    session: AsyncSession,
    user: User,
    todo_id: UUID,
    fields: dict,
) -> TodoItem:
    item = await todos_repo.get_by_id(session, todo_id, user.id)
    if not item:
        raise TodosError("Todo not found", status_code=404)
    patch = dict(fields)
    if "project_id" in patch:
        raise TodosError("Reminders cannot be linked to a Learning project", status_code=400)
    if "due_at" in patch:
        if patch["due_at"] is None:
            raise TodosError("due_at cannot be cleared", status_code=422)
        patch["due_at"] = normalize_due_at(patch["due_at"], user.timezone)
        if patch["due_at"] is None:
            raise TodosError("due_at cannot be cleared", status_code=422)
        if patch["due_at"] != item.due_at:
            patch["notification_sent_at"] = None
            patch["email_sent_at"] = None
    rule = patch.get("recurrence_rule", item.recurrence_rule)
    due = patch["due_at"] if "due_at" in patch else item.due_at
    if due is not None and is_recurrence_rule(rule):
        patch["due_at"] = snap_first_due(due, rule, timezone=user.timezone)
    updated = await todos_repo.update(session, item, **patch)
    await home_service.invalidate_home_cache(user.id)
    return updated


async def _advance_past_recurring(
    session: AsyncSession,
    items: list[TodoItem],
    *,
    timezone: str | None,
    now: datetime | None = None,
) -> None:
    when = now or datetime.now(UTC)
    changed = False
    for item in items:
        rule = item.recurrence_rule
        if item.checked or item.due_at is None or not is_recurrence_rule(rule):
            continue
        if item.due_at > when:
            continue
        item.due_at = next_recurring_due(item.due_at, rule, now=when, timezone=timezone)
        item.notification_sent_at = None
        item.email_sent_at = None
        changed = True
    if changed:
        await session.commit()


async def delete_todo(session: AsyncSession, user: User, todo_id: UUID) -> None:
    deleted = await todos_repo.delete_by_id(session, todo_id, user.id)
    if not deleted:
        raise TodosError("Todo not found", status_code=404)
    await home_service.invalidate_home_cache(user.id)


async def delete_topic(session: AsyncSession, user: User, topic: str) -> None:
    removed = await todos_repo.delete_by_topic(session, user.id, topic)
    if not removed:
        raise TodosError("List not found", status_code=404)
    await home_service.invalidate_home_cache(user.id)
