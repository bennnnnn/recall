"""Apply one spoken reminder change and read back what is actually saved.

A frequency, a clock, or a category is written here before the reply is chosen.
The reply names that saved row. It is not the model's sentence.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.todos.schemas import RecurrenceRule
from app.modules.todos.spoken_change import SpokenReminderChange, resolve_spoken_target

_HIDDEN_TOPICS = frozenset({"", "General", "Reminders"})
_READ_LIMIT = 30
_FAR = datetime(9999, 1, 1, tzinfo=UTC)


async def apply_spoken_change(
    session: AsyncSession,
    *,
    user_id: UUID,
    chat_id: UUID,
    user_timezone: str | None,
    spoken: SpokenReminderChange,
) -> tuple[str, int]:
    from app.modules import home as home_service
    from app.modules.todos.reminder_fences import (
        _load_existing,
        _mutate_one,
        _ReminderFence,
        _ReminderFenceCreateState,
        format_schedule_result,
    )

    state = _ReminderFenceCreateState(
        session=session,
        user_id=user_id,
        chat_id=chat_id,
        user_timezone=user_timezone,
    )
    await _load_existing(state)
    item: Any = resolve_spoken_target(state.existing, spoken)
    label = spoken.title_hint or "that reminder"
    if item is None or not (getattr(item, "content", None) or "").strip():
        if spoken.topic:
            return f"Could not update {label}.", 0
        return format_schedule_result(
            action=spoken.action,
            title=label,
            due_at=spoken.due_at,
            repeat=spoken.repeat,
            user_timezone=user_timezone,
            ok=False,
        ), 0
    title = str(item.content).strip()
    if spoken.topic or spoken.keep_date or (spoken.due_at is None and spoken.repeat):
        line, ok = await _apply_saved_fields(
            session,
            item,
            spoken,
            title=title,
            user_timezone=user_timezone,
        )
        if ok:
            await home_service.invalidate_home_cache(user_id)
        return line, (1 if ok else 0)
    draft = _ReminderFence(action=spoken.action, title=title, due_at=spoken.due_at)
    draft.repeat = spoken.repeat
    line, ok = await _mutate_one(state, draft)
    if ok:
        await home_service.invalidate_home_cache(user_id)
    return line, (1 if ok else 0)


async def _apply_saved_fields(
    session: AsyncSession,
    item: Any,
    spoken: SpokenReminderChange,
    *,
    title: str,
    user_timezone: str | None,
) -> tuple[str, bool]:
    from app.modules.todos import repository as todos_repo
    from app.modules.todos.reminder_fences import format_schedule_result, format_schedule_when

    fields: dict[str, Any] = {}
    due = getattr(item, "due_at", None)
    repeat = spoken.repeat or _kept_repeat(item)
    if spoken.keep_date:
        retimed = _due_with_clock(
            item,
            spoken.hour,
            spoken.minute,
            user_timezone=user_timezone,
            repeat=repeat,
        )
        if retimed is None:
            return format_schedule_result(
                action="set_due",
                title=title,
                due_at=None,
                repeat=repeat,
                user_timezone=user_timezone,
                ok=False,
            ), False
        fields["due_at"] = retimed
        due = retimed
    if spoken.repeat:
        if not isinstance(due, datetime):
            return format_schedule_result(
                action="set_due",
                title=title,
                due_at=None,
                repeat=spoken.repeat,
                user_timezone=user_timezone,
                ok=False,
            ), False
        fields["recurrence_rule"] = spoken.repeat
        repeat = spoken.repeat
    if spoken.topic:
        fields["topic"] = spoken.topic
    if not fields:
        return format_schedule_result(
            action="set_due",
            title=title,
            due_at=None,
            repeat=None,
            user_timezone=user_timezone,
            ok=False,
        ), False
    await todos_repo.update(session, item, **fields)
    if spoken.topic:
        when = format_schedule_when(due, user_timezone, repeat) if isinstance(due, datetime) else ""
        if when:
            return f"Moved: {title} to {spoken.topic} — {when}.", True
        return f"Moved: {title} to {spoken.topic}.", True
    return format_schedule_result(
        action="set_due",
        title=title,
        due_at=due if isinstance(due, datetime) else None,
        repeat=repeat,
        user_timezone=user_timezone,
        ok=True,
    ), True


def format_reminder_reading(items: Sequence[Any], user_timezone: str | None) -> str:
    """One line per saved reminder. Nothing in this text is invented."""
    from app.modules.todos.reminder_fences import format_schedule_when

    rows = list(items)
    open_lines: list[tuple[datetime, str]] = []
    done_names: list[str] = []
    for item in rows:
        title = (getattr(item, "content", None) or "").strip()
        if not title:
            continue
        if getattr(item, "checked", False):
            done_names.append(title)
            continue
        due = getattr(item, "due_at", None)
        repeat = _kept_repeat(item)
        if isinstance(due, datetime):
            when = format_schedule_when(due, user_timezone, repeat)
            stamp = due if due.tzinfo else due.replace(tzinfo=UTC)
        else:
            when = "no time"
            stamp = _FAR
        topic = (getattr(item, "topic", None) or "").strip()
        if topic in _HIDDEN_TOPICS:
            topic = ""
        line = f"{title} — {when}"
        if topic:
            line = f"{line} · {topic}"
        open_lines.append((stamp, f"{line}."))
    open_lines.sort(key=lambda pair: pair[0])
    lines = [line for _stamp, line in open_lines[:_READ_LIMIT]]
    hidden = len(open_lines) - len(lines)
    if hidden > 0:
        lines.append(f"And {hidden} more.")
    if done_names:
        shown = done_names[:_READ_LIMIT]
        extra = len(done_names) - len(shown)
        done = "Done: " + ", ".join(shown) + "."
        if extra:
            done = f"{done[:-1]}, and {extra} more."
        lines.append(done)
    if not lines:
        return "Nothing scheduled."
    return "\n".join(lines)


def _due_with_clock(
    item: Any,
    hour: int | None,
    minute: int | None,
    *,
    user_timezone: str | None,
    repeat: RecurrenceRule | None,
) -> datetime | None:
    from app.modules.todos import spoken_change
    from app.services import time_context as time_context_service

    due = getattr(item, "due_at", None)
    if not isinstance(due, datetime) or hour is None or minute is None:
        return None
    tz = time_context_service.resolve_timezone(user_timezone)
    local = due.astimezone(tz) if due.tzinfo else due.replace(tzinfo=UTC).astimezone(tz)
    retimed = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if retimed <= spoken_change._now(tz):
        retimed += timedelta(days=1)
    if repeat == "weekdays":
        while retimed.weekday() >= 5:
            retimed += timedelta(days=1)
    return retimed


def _kept_repeat(item: Any) -> RecurrenceRule | None:
    rule = getattr(item, "recurrence_rule", None)
    if rule == "daily" or rule == "weekdays" or rule == "weekly" or rule == "monthly":
        return rule
    return None
