"""HTTP-facing todos CRUD (create/update/delete)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainError
from app.models.orm import TodoItem, User
from app.modules.conversation import history as chat_history
from app.modules.todos import repository as todos_repo
from app.modules.todos.due_day import has_time, overdue_from, start_of_day, stored_due
from app.modules.todos.occurrences import TodoScheduleSnapshot
from app.modules.todos.recurrence import (
    RecurrenceRule,
    completed_fields,
    is_recurrence_rule,
    next_open_due,
    snap_first_due,
)
from app.modules.todos.schedule_repository import advance_schedules_if_current
from app.services.time_context import normalize_due_at


class TodosError(DomainError):
    """A to-do refusal."""


def _duplicate(*, has_time: bool = True) -> TodosError:
    """Another open to-do already has this title at this time, or as a date alone on this
    day (uq_todo_open_content_due)."""
    when = "at that time" if has_time else "on that day"
    return TodosError(
        f"You already have this to-do {when}.", status_code=409, code="todo_duplicate"
    )


def _reminder_pushes_on(user: User) -> bool:
    """Reminder pushes reach this user; when they do not, listing advances recurring ones."""
    return bool(user.push_notifications_enabled and user.push_reminders_enabled)


async def list_todos_page(
    session: AsyncSession,
    user: User,
    *,
    limit: int = 200,
    cursor: UUID | None = None,
    completed_since: datetime | None = None,
) -> tuple[list[TodoItem], UUID | None]:
    """A page of the user's to-dos; with ``completed_since``, older completed ones are left out."""
    user_id = user.id
    selected = await todos_repo.list_after_id(
        session, user_id, limit=limit + 1, cursor=cursor, completed_since=completed_since
    )
    items = selected[:limit]
    page_ids = [item.id for item in items]
    # Preserve this boundary even when catch-up races a deletion of the last row.
    next_cursor = page_ids[-1] if len(selected) > limit else None
    # A push moves a timed repeat on as it goes out. Nothing goes out for a date alone,
    # so the list moves one on once its day has ended, whatever the push settings.
    passed = items if not _reminder_pushes_on(user) else [i for i in items if not has_time(i)]
    if await advance_past_recurring(session, passed, timezone=user.timezone):
        items = await todos_repo.list_by_ids(session, user_id, page_ids)
    return items, next_cursor


async def has_older_completed(session: AsyncSession, user: User, since: datetime) -> bool:
    """The user has completed to-dos last changed before ``since`` (a page left them out)."""
    return await todos_repo.has_completed_before(session, user.id, since)


async def create_todo(
    session: AsyncSession,
    user: User,
    *,
    content: str,
    topic: str | None,
    chat_id: UUID | None,
    due_at: datetime | None,
    recurrence_rule: RecurrenceRule | None = None,
    due_has_time: bool = True,
) -> TodoItem:
    if chat_id is not None:
        chat = await chat_history.get_chat(session, chat_id, user.id)
        if chat is None:
            raise TodosError("Chat not found", status_code=400)
    normalized_due = stored_due(due_at, user.timezone, has_time=due_has_time)
    if normalized_due is not None and recurrence_rule:
        normalized_due = snap_first_due(normalized_due, recurrence_rule, timezone=user.timezone)
    if normalized_due is None:
        recurrence_rule = None
    # Read before the try: a rollback expires the user, and reading it then fails.
    user_id = user.id
    try:
        item = await todos_repo.create(
            session,
            user_id=user_id,
            content=content,
            topic=topic or todos_repo.DEFAULT_TOPIC,
            chat_id=chat_id,
            due_at=normalized_due,
            recurrence_rule=recurrence_rule,
            due_has_time=due_has_time,
        )
    except IntegrityError as exc:
        if not todos_repo.is_open_content_due_conflict(exc) or normalized_due is None:
            raise
        await session.rollback()
        existing = await todos_repo.get_open_dated_duplicate(
            session, user_id, content=content, due_at=normalized_due, due_has_time=due_has_time
        )
        if existing is None:
            raise _duplicate(has_time=due_has_time) from exc
        return existing
    return item


async def update_todo(
    session: AsyncSession,
    user: User,
    todo_id: UUID,
    fields: dict[str, Any],
) -> TodoItem:
    item = await todos_repo.get_by_id(session, todo_id, user.id)
    if not item:
        raise TodosError("Todo not found", status_code=404)
    patch = dict(fields)
    if "due_at" in patch and patch["due_at"] is None:
        if is_recurrence_rule(patch.get("recurrence_rule")):
            raise TodosError("recurrence_rule requires due_at", status_code=422)
        # An undated item cannot recur. Clearing its date therefore clears
        # the repeat rule atomically instead of leaving an invalid pair.
        patch["recurrence_rule"] = None
    if "due_at" in patch or "due_has_time" in patch:
        patch.update(_stored_due_fields(item, patch, user.timezone))
    rule = patch.get("recurrence_rule", item.recurrence_rule)
    due = patch["due_at"] if "due_at" in patch else item.due_at
    if is_recurrence_rule(rule) and due is None:
        raise TodosError("recurrence_rule requires due_at", status_code=422)
    if due is not None and is_recurrence_rule(rule):
        patch["due_at"] = snap_first_due(due, rule, timezone=user.timezone)
    patch = completed_fields(
        patch,
        due_at=patch.get("due_at", item.due_at),
        rule=rule,
        timezone=user.timezone,
        now=datetime.now(UTC),
    )
    if "due_at" in patch:
        # Ticking a repeating date alone moves it to its next day, still without a time.
        patch.setdefault("due_has_time", has_time(item))
    # Read before the try: a rollback expires the row.
    timed = patch.get("due_has_time", has_time(item))
    try:
        return await todos_repo.update(session, item, **patch)
    except IntegrityError as exc:
        if not todos_repo.is_open_content_due_conflict(exc):
            raise
        await session.rollback()
        raise _duplicate(has_time=timed) from exc


def _stored_due_fields(
    item: TodoItem, patch: dict[str, Any], timezone: str | None
) -> dict[str, Any]:
    """The due date and its flag as an edit stores them; a date alone is held at the start
    of its day.

    A ``due_at`` sent without the flag comes from an app before date-only to-dos. It meant
    a time, unless the to-do is a date alone and ``due_at`` is still a day's start: a title
    edit sends the saved one back, and a new date keeps the 00:00 that app showed. Read as
    a time, that date alone was reminded of at about 23:45 the night before.
    """
    due = patch["due_at"] if "due_at" in patch else item.due_at
    if due is None:
        return {"due_has_time": True}
    timed = patch.get("due_has_time")
    if timed is None:
        sent = normalize_due_at(due, timezone)
        timed = has_time(item) or (sent is not None and sent != start_of_day(sent, timezone))
    return {"due_at": stored_due(due, timezone, has_time=timed), "due_has_time": timed}


async def advance_past_recurring(
    session: AsyncSession,
    items: list[TodoItem],
    *,
    timezone: str | None,
    now: datetime | None = None,
) -> bool:
    """Move each overdue recurring item to its next occurrence; commits. Whether any moved.

    Only an item still as it was read moves (``advance_schedules_if_current``).
    """
    when = now or datetime.now(UTC)
    advances = []
    for item in items:
        rule = item.recurrence_rule
        if item.checked or item.due_at is None or not is_recurrence_rule(rule):
            continue
        timed = has_time(item)
        if overdue_from(item.due_at, timezone, has_time=timed) > when:
            continue
        advances.append(
            (
                TodoScheduleSnapshot.from_todo(item),
                next_open_due(item.due_at, rule, has_time=timed, now=when, timezone=timezone),
            )
        )
    if not advances:
        return False
    try:
        await advance_schedules_if_current(session, advances)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return True


async def delete_todo(session: AsyncSession, user: User, todo_id: UUID) -> None:
    deleted = await todos_repo.delete_by_id(session, todo_id, user.id)
    if not deleted:
        raise TodosError("Todo not found", status_code=404)
