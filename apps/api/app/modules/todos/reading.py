"""The saved to-dos read back in chat: one line per reminder, nothing invented.

Asked "what's on my to-do list?" (``read_asks``), a model listed a reminder whose card was
never tapped and left out one saved for that evening (2026-10-25). The reply to such a
question is the saved rows, written here; the model's list is never shown.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.todos import repository as todos_repo
from app.modules.todos.due_day import has_time
from app.modules.todos.recurrence import RecurrenceRule, is_recurrence_rule
from app.services import time_context as time_context_service

# The rows a read-back may list from.
_READ_ROWS = 500
_HIDDEN_TOPICS = frozenset({"", "General", "Reminders"})
_READ_LIMIT = 30
_FAR = datetime(9999, 1, 1, tzinfo=UTC)
# A title shorter than this ("go") names nothing for certain.
_TITLE_MIN_CHARS = 3
_WORDS = re.compile(r"[^\W_]+")


async def read_back(session: AsyncSession, user_id: UUID, user_timezone: str | None) -> str:
    """The user's saved to-dos, as the reply to a question about them."""
    items = await todos_repo.list_for_user(session, user_id, limit=_READ_ROWS, needed_first=True)
    return format_reminder_reading(items, user_timezone)


async def saved_todo_named(session: AsyncSession, user_id: UUID, text: str) -> str | None:
    """The user's saved to-do ``text`` names ("move gym to 7pm" names "gym"), casefolded:
    a message about that to-do, whatever its verb. None when it names none."""
    folded = f" {' '.join(_WORDS.findall(text.casefold()))} "
    items = await todos_repo.list_for_user(session, user_id, limit=_READ_ROWS, needed_first=True)
    for item in items:
        title = " ".join(_WORDS.findall((getattr(item, "content", None) or "").casefold()))
        if len(title) >= _TITLE_MIN_CHARS and f" {title} " in folded:
            return title
    return None


def format_reminder_reading(items: Sequence[Any], user_timezone: str | None) -> str:
    """One line per saved reminder. Nothing in this text is invented."""
    open_lines: list[tuple[datetime, str]] = []
    done_names: list[str] = []
    for item in items:
        title = (getattr(item, "content", None) or "").strip()
        if not title:
            continue
        if getattr(item, "checked", False):
            done_names.append(title)
            continue
        due = getattr(item, "due_at", None)
        if isinstance(due, datetime):
            when = format_schedule_when(
                due, user_timezone, _kept_repeat(item), has_time=has_time(item)
            )
            stamp = due if due.tzinfo else due.replace(tzinfo=UTC)
        else:
            when = "no time"
            stamp = _FAR
        topic = (getattr(item, "topic", None) or "").strip()
        line = f"{title} — {when}"
        if topic not in _HIDDEN_TOPICS:
            line = f"{line} · {topic}"
        open_lines.append((stamp, f"{line}."))
    open_lines.sort(key=lambda pair: pair[0])
    lines = [line for _stamp, line in open_lines[:_READ_LIMIT]]
    hidden = len(open_lines) - len(lines)
    if hidden > 0:
        lines.append(f"And {hidden} more.")
    if done_names:
        lines.append(_done_line(done_names))
    if not lines:
        return "Nothing scheduled."
    return "\n".join(lines)


def _done_line(names: list[str]) -> str:
    shown = names[:_READ_LIMIT]
    extra = len(names) - len(shown)
    done = "Done: " + ", ".join(shown) + "."
    return f"{done[:-1]}, and {extra} more." if extra else done


def format_schedule_when(
    due_at: datetime,
    user_timezone: str | None,
    repeat: RecurrenceRule | str | None = None,
    *,
    has_time: bool = True,
) -> str:
    """The day and clock of a reminder, "Thursday, Oct 15, 6:00 PM"; a date alone has
    no clock, "Thursday, Oct 15"."""
    tz = time_context_service.resolve_timezone(user_timezone)
    due_local = (
        due_at.astimezone(tz) if due_at.tzinfo else due_at.replace(tzinfo=UTC).astimezone(tz)
    )
    hour = due_local.strftime("%I").lstrip("0") or "0"
    when = f"{due_local.strftime('%A')}, {due_local.strftime('%b')} {due_local.day}"
    if has_time:
        when = f"{when}, {hour}:{due_local.strftime('%M')} {due_local.strftime('%p')}"
    if repeat:
        when = f"{when} · {repeat}"
    return when


def _kept_repeat(item: Any) -> RecurrenceRule | None:
    rule = getattr(item, "recurrence_rule", None)
    return rule if is_recurrence_rule(rule) else None
