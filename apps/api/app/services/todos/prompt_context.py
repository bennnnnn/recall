"""Todo selection/formatting injected into the chat system prompt."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import TodoItem, User
from app.repositories import todos as todos_repo
from app.repositories.todos import DEFAULT_TOPIC
from app.services import day_planning as day_planning_service
from app.services import time_context as time_context_service
from app.services.todos.classification import query_implies_todos
from app.services.todos.prompt_hint import TODO_HINT


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _topic_key(topic: str) -> str:
    return _normalize(topic or DEFAULT_TOPIC)


def _due_local(due_at: datetime, user_timezone: str | None):
    tz = time_context_service.resolve_timezone(user_timezone)
    due = due_at
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    return due.astimezone(tz)


def _reminder_day_group(todo: TodoItem, user_timezone: str | None) -> tuple[str, str]:
    """Sort key and heading for grouping reminders by calendar day."""
    assert todo.due_at is not None
    tz = time_context_service.resolve_timezone(user_timezone)
    now = datetime.now(tz)
    due_local = _due_local(todo.due_at, user_timezone)
    if not todo.checked and due_local < now:
        return ("0", "Overdue")
    due_date = due_local.date()
    if due_date == now.date():
        return ("1", "Today")
    if due_date == (now + timedelta(days=1)).date():
        return ("2", "Tomorrow")
    return ("3", due_local.strftime("%a %b %d"))


def _todo_priority(
    item: TodoItem,
    *,
    query_text: str | None,
    user_timezone: str | None,
) -> tuple[int, int, datetime]:
    """Lower tuple sorts first — overdue/today reminders beat distant lists."""
    tz = time_context_service.resolve_timezone(user_timezone)
    now = datetime.now(tz)
    bucket = 50
    if item.due_at is not None:
        due_local = _due_local(item.due_at, user_timezone)
        if not item.checked and due_local < now:
            bucket = 0
        elif due_local.date() == now.date():
            bucket = 1
        elif due_local.date() == (now + timedelta(days=1)).date():
            bucket = 2
        elif not item.checked:
            bucket = 4
        else:
            bucket = 6
        sort_due = due_local
    else:
        bucket = 8 if not item.checked else 9
        sort_due = datetime.max.replace(tzinfo=UTC)

    q = _normalize(query_text or "")
    match_rank = 0
    if q:
        hay = f"{_normalize(item.content)} {_topic_key(item.topic)}"
        if q in hay or any(token in hay for token in q.split() if len(token) >= 4):
            match_rank = -1
    return (bucket, match_rank, sort_due)


def select_todos_for_prompt(
    items: list[TodoItem],
    settings: Settings,
    *,
    query_text: str | None = None,
    user_timezone: str | None = None,
) -> list[TodoItem]:
    """Trim large todo snapshots — always keep overdue/today open reminders."""
    limit = max(8, settings.todo_prompt_limit)
    if len(items) <= limit:
        return items

    ranked = sorted(
        items,
        key=lambda item: _todo_priority(item, query_text=query_text, user_timezone=user_timezone),
    )
    return ranked[:limit]


def format_todos_block(items: list[TodoItem], *, user_timezone: str | None = None) -> str:
    if not items:
        return ""

    reminders = [item for item in items if item.due_at is not None]
    list_items = [item for item in items if item.due_at is None]

    overdue_open = [
        item
        for item in reminders
        if not item.checked
        and time_context_service.describe_due_at(item.due_at, user_timezone).startswith("overdue")
    ]

    lines: list[str] = []

    if overdue_open:
        names = ", ".join(f"{i.content} ({i.topic})" for i in overdue_open[:5])
        extra = f" (+{len(overdue_open) - 5} more)" if len(overdue_open) > 5 else ""
        lines.append(
            f"⚠ {len(overdue_open)} overdue reminder(s): {names}{extra} — nudge if relevant."
        )

    if reminders:
        lines.append("User Reminders (in-app calendar — grouped by day):")
        open_reminders = [item for item in reminders if not item.checked]
        done_reminders = [item for item in reminders if item.checked]
        display = open_reminders + done_reminders

        grouped: dict[tuple[str, str], list[TodoItem]] = {}
        for todo in display:
            key = _reminder_day_group(todo, user_timezone)
            grouped.setdefault(key, []).append(todo)

        for key in sorted(grouped.keys(), key=lambda item: item[0]):
            heading = key[1]
            lines.append(f"\n### {heading}")
            day_items = sorted(
                grouped[key],
                key=lambda item: _due_local(item.due_at, user_timezone),  # type: ignore[arg-type]
            )
            for todo in day_items:
                status = "done" if todo.checked else "open"
                mark = "✓" if todo.checked else "○"
                due_local = _due_local(todo.due_at, user_timezone)  # type: ignore[arg-type]
                clock = due_local.strftime("%H:%M")
                due_label = time_context_service.describe_due_at(
                    todo.due_at, user_timezone, checked=todo.checked
                )
                rel = f", {due_label}" if due_label else ""
                topic = todo.topic.strip() or DEFAULT_TOPIC
                project_bit = (
                    f", project:{todo.project_id}" if getattr(todo, "project_id", None) else ""
                )
                lines.append(
                    f"- {mark} {todo.content} at {clock}{rel} ({status}, topic: {topic}{project_bit})"
                )

    if list_items:
        by_topic: dict[str, list[TodoItem]] = {}
        for item in list_items:
            topic = item.topic.strip() or DEFAULT_TOPIC
            by_topic.setdefault(topic, []).append(item)

        lines.append("\nUser Lists (no due date — checklists only, not on the Reminders calendar):")
        for topic in sorted(by_topic.keys(), key=str.casefold):
            lines.append(f"\n## {topic}")
            for todo in by_topic[topic]:
                status = "done" if todo.checked else "open"
                mark = "✓" if todo.checked else "○"
                lines.append(f"- {mark} {todo.content} ({status})")

    return "\n".join(lines)


def _has_overdue_open_reminders(items: list[TodoItem], user_timezone: str | None) -> bool:
    for item in items:
        if item.checked or item.due_at is None:
            continue
        label = time_context_service.describe_due_at(item.due_at, user_timezone)
        if label.startswith("overdue"):
            return True
    return False


def should_inject_todos_prompt(
    items: list[TodoItem],
    *,
    query_text: str | None = None,
    user_timezone: str | None = None,
) -> bool:
    """Skip todo blocks on unrelated turns to save tokens; keep overdue nudges."""
    if query_text and day_planning_service.is_day_planning_question(query_text):
        return True
    if query_implies_todos(query_text):
        return True
    return _has_overdue_open_reminders(items, user_timezone)


async def load_todos_for_prompt(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    client_timezone: str | None = None,
    query_text: str | None = None,
) -> str:
    items = await todos_repo.list_for_user(session, user.id, limit=settings.todo_inject_limit)
    tz = time_context_service.effective_timezone(user.timezone, client_timezone)
    if not should_inject_todos_prompt(items, query_text=query_text, user_timezone=tz):
        return ""
    selected = select_todos_for_prompt(items, settings, query_text=query_text, user_timezone=tz)
    return format_todos_block(selected, user_timezone=tz)


async def build_todos_system_section(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    client_timezone: str | None = None,
    query_text: str | None = None,
) -> str | None:
    """Todo hint + snapshot block, or None when the turn is unrelated."""
    items = await todos_repo.list_for_user(session, user.id, limit=settings.todo_inject_limit)
    tz = time_context_service.effective_timezone(user.timezone, client_timezone)
    if not should_inject_todos_prompt(items, query_text=query_text, user_timezone=tz):
        return None
    selected = select_todos_for_prompt(items, settings, query_text=query_text, user_timezone=tz)
    block = format_todos_block(selected, user_timezone=tz)
    if block:
        return f"{TODO_HINT}\n\n{block}"
    return TODO_HINT
