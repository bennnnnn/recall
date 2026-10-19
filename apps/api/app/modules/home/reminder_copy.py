"""Copy for the home reminder row."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.orm import User
from app.models.schemas import HomeUrgentTodo
from app.services import time_context as time_context_service


def format_urgent_due_label(due_at: datetime, user_timezone: str | None) -> str:
    tz = time_context_service.resolve_timezone(user_timezone)
    now = datetime.now(tz)
    due_local = (
        due_at.astimezone(tz) if due_at.tzinfo else due_at.replace(tzinfo=UTC).astimezone(tz)
    )
    time_str = due_local.strftime("%I:%M %p").lstrip("0")
    if due_local.date() == now.date():
        return f"today at {time_str}"
    if due_local.date() == (now.date() + timedelta(days=1)):
        return f"tomorrow at {time_str}"
    return due_local.strftime("%a %b %d at %I:%M %p").lstrip("0")


def urgent_subtitle(user: User, urgent_todos: list[HomeUrgentTodo]) -> str | None:
    if not urgent_todos:
        return None
    if len(urgent_todos) > 1:
        return f"{len(urgent_todos)} reminders in the next hour."
    first = urgent_todos[0]
    if first.minutes_until < 0:
        return f'"{first.content}" is overdue.'
    when = format_urgent_due_label(first.due_at, user.timezone)
    return f"Coming up: {first.content} {when}."
