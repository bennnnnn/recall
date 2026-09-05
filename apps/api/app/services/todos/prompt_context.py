"""Todo selection/formatting injected into the chat system prompt."""

from __future__ import annotations

import re
from dataclasses import dataclass
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


@dataclass(frozen=True)
class TodosPromptSections:
    """Schedule inject split so Gmail-sourced rows keep untrusted framing."""

    own: str | None = None
    gmail: str | None = None


def _todo_source(item: TodoItem) -> str:
    source = getattr(item, "source", "user")
    return source if source in {"user", "gmail"} else "user"


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
    """Lower tuple sorts first — overdue/today reminders beat later dates."""
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
        return [item for item in items if item.due_at is not None]

    ranked = sorted(
        [item for item in items if item.due_at is not None],
        key=lambda item: _todo_priority(item, query_text=query_text, user_timezone=user_timezone),
    )
    return ranked[:limit]


def format_todos_block(items: list[TodoItem], *, user_timezone: str | None = None) -> str:
    if not items:
        return ""

    reminders = [item for item in items if item.due_at is not None]
    if not reminders:
        return ""

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

    lines.append("User Schedule (in-app calendar — grouped by day):")
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
            repeat = f", repeats {todo.recurrence_rule}" if todo.recurrence_rule else ""
            lines.append(
                f"- {mark} {todo.content} at {clock}{rel}{repeat} ({status}, topic: {topic})"
            )

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


async def build_todos_system_section(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    client_timezone: str | None = None,
    query_text: str | None = None,
) -> TodosPromptSections | None:
    """Todo hint + snapshot blocks, or None when the turn is unrelated.

    Gmail-confirmed reminders stay in a separate block so prompt_builder can
    wrap them as third-party untrusted content instead of first-party notes.
    """
    tz = time_context_service.effective_timezone(user.timezone, client_timezone)
    probe: list[TodoItem] = []
    text_hit = bool(
        (query_text and day_planning_service.is_day_planning_question(query_text))
        or query_implies_todos(query_text)
    )
    if not text_hit:
        probe = await todos_repo.list_due_soon(session, user.id, before_utc=datetime.now(UTC))
    if not should_inject_todos_prompt(probe, query_text=query_text, user_timezone=tz):
        return None
    items = await todos_repo.list_for_user(session, user.id, limit=settings.todo_inject_limit)
    selected = select_todos_for_prompt(items, settings, query_text=query_text, user_timezone=tz)
    own_items = [item for item in selected if _todo_source(item) != "gmail"]
    gmail_items = [item for item in selected if _todo_source(item) == "gmail"]
    own_block = format_todos_block(own_items, user_timezone=tz)
    gmail_block = format_todos_block(gmail_items, user_timezone=tz)
    own_section = (
        f"{TODO_HINT}\n\n{own_block}" if own_block else (TODO_HINT if not gmail_block else None)
    )
    return TodosPromptSections(own=own_section, gmail=gmail_block or None)
