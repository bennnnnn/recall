"""Apply one spoken reminder change and read back what is actually saved.

A frequency, a clock, or a category is written here before the reply is chosen.
The reply names that saved row. It is not the model's sentence.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import User
from app.modules.todos.due_day import has_time, local_day, stored_due
from app.modules.todos.recurrence import is_recurrence_rule
from app.modules.todos.schemas import RecurrenceRule
from app.modules.todos.spoken_change import (
    SpokenReminderChange,
    asks_about_my_reminders,
    names_reminders,
)
from app.modules.todos.spoken_target import match_from_context, resolve_spoken_target
from app.services.locale import LOCALE_NAMES

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
    user_text: str | None = None,
    prior_assistant: str | None = None,
    prior_user: str | None = None,
    reply: str | None = None,
) -> tuple[str, int] | None:
    """The saved result of a spoken change, or None when it is not about a reminder.

    "Finish the story" or "delete a git branch" parse like a change but name no
    saved reminder and say nothing about one; the model's reply stands. "It" or
    "that" points at a reminder only after a reply about reminders. A ``reply``
    that confirms a change in the app's own shape ("Reopened: buy milk.") is
    about a reminder, so a missing one gets the "Could not" line, not the claim.
    """
    from app.modules.todos.reminder_fence_parse import ReminderFence
    from app.modules.todos.reminder_writes import (
        ReminderWrites,
        format_schedule_result,
        load_existing,
        mutate_one,
    )
    from app.modules.todos.reply_check import (
        NEED_A_TIME,
        about_saved_reminders,
        claims_a_reminder_change,
        edits_prior_reply,
    )

    state = ReminderWrites(
        session=session, user_id=user_id, chat_id=chat_id, user_timezone=user_timezone
    )
    explicit = names_reminders(user_text)
    prior_about = about_saved_reminders(prior_assistant) or asks_about_my_reminders(prior_user)
    await load_existing(state)
    # "Put that in a table" reshapes the reply; a move needs a list's name (2026-11-07).
    if spoken.topic and not _a_list(spoken, prior_assistant, explicit):
        return None
    named_in_message = spoken.use_latest and match_from_context(state.existing, spoken) is not None
    if (
        spoken.use_latest
        and prior_assistant is not None
        and not explicit
        and not named_in_message
        and not prior_about
    ):
        return None
    item: Any = resolve_spoken_target(state.existing, spoken)
    # A named target must be a saved reminder; "it" was settled above.
    if (
        item is None
        and not explicit
        and user_text is not None
        and not spoken.use_latest
        and not claims_a_reminder_change(reply)
    ):
        return None
    # "Remove the gym on Monday" right after a workout plan edits the plan.
    if (
        item is not None
        and not explicit
        and not spoken.use_latest
        and not prior_about
        and edits_prior_reply(spoken.title_hint, prior_assistant=prior_assistant, reply=reply)
    ):
        return None
    if spoken.needs_time:
        return NEED_A_TIME, 0
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
    if (
        spoken.topic
        or spoken.keep_date
        or spoken.day
        or spoken.shift_days
        or (spoken.due_at is None and spoken.repeat)
    ):
        line, ok = await _apply_saved_fields(
            session,
            item,
            spoken,
            title=title,
            user_timezone=user_timezone,
        )
        return line, (1 if ok else 0)
    draft = ReminderFence(action=spoken.action, title=title, due_at=spoken.due_at)
    draft.repeat = spoken.repeat
    line, ok = await mutate_one(state, draft)
    return line, (1 if ok else 0)


# "Put that in Spanish" asks for the reply in another language Recall speaks.
_LANGUAGES = frozenset(name.lower() for name in LOCALE_NAMES.values())


def _a_list(spoken: SpokenReminderChange, prior_assistant: str | None, named: bool) -> bool:
    """A move's ``topic`` can be a list and "it" a reminder. "a table" or "an email" is a shape
    for the reply and "Spanish" a language; and after a plan that mentions a reminder in
    passing, "put that in a table" is about the plan (live, 2026-11-07: it became a card moving
    the reminder "To a table")."""
    from app.modules.todos.reply_check import opens_on_saved_reminders

    wanted = (spoken.topic or "").strip().lower()
    if wanted.startswith(("a ", "an ")) or wanted in _LANGUAGES:
        return False
    return (
        not spoken.use_latest
        or named
        or prior_assistant is None
        or opens_on_saved_reminders(prior_assistant)
    )


def _not_saved(title: str, repeat: RecurrenceRule | None, user_timezone: str | None) -> str:
    from app.modules.todos.reminder_writes import format_schedule_result

    return format_schedule_result(
        action="set_due",
        title=title,
        due_at=None,
        repeat=repeat,
        user_timezone=user_timezone,
        ok=False,
    )


async def _anchor_zone(session: AsyncSession, item: Any, fallback: str | None) -> str | None:
    """The zone a date alone is held in: the profile's. The turn's is the phone's, which a
    flight leaves ahead of the profile for a while, and read there "Friday" became Saturday."""
    user_id = getattr(item, "user_id", None)
    user = await session.get(User, user_id) if user_id is not None else None
    zone = user.timezone if user is not None else None
    return zone if isinstance(zone, str) and zone else fallback


async def _apply_saved_fields(
    session: AsyncSession,
    item: Any,
    spoken: SpokenReminderChange,
    *,
    title: str,
    user_timezone: str | None,
) -> tuple[str, bool]:
    from app.modules.todos import repository as todos_repo
    from app.modules.todos.reminder_writes import format_schedule_result, format_schedule_when

    fields: dict[str, Any] = {}
    due = getattr(item, "due_at", None)
    timed = has_time(item)
    anchor = user_timezone if timed else await _anchor_zone(session, item, user_timezone)
    repeat = spoken.repeat or _kept_repeat(item)
    if spoken.keep_date:
        retimed = _due_with_clock(
            item,
            spoken.hour,
            spoken.minute,
            user_timezone=user_timezone,
            repeat=repeat,
            anchor=anchor,
        )
        if retimed is None:
            return _not_saved(title, repeat, user_timezone), False
        fields["due_at"] = retimed
        due = retimed
        timed = True
    if spoken.day or spoken.shift_days:
        moved = _moved_due(item, spoken, user_timezone=user_timezone, anchor=anchor)
        if moved is None:
            return _not_saved(title, repeat, user_timezone), False
        fields["due_at"] = moved
        due = moved
    if "due_at" in fields:
        # A clock said gives it a time; a new day alone keeps a date alone without one.
        fields["due_has_time"] = timed
    if spoken.repeat:
        if not isinstance(due, datetime):
            return _not_saved(title, spoken.repeat, user_timezone), False
        fields["recurrence_rule"] = spoken.repeat
        repeat = spoken.repeat
    if spoken.topic:
        fields["topic"] = spoken.topic
    if not fields:
        return _not_saved(title, None, user_timezone), False
    await todos_repo.update(session, item, commit=False, **fields)
    # A date alone is named by its day where it is held.
    zone = user_timezone if timed else anchor
    if spoken.topic:
        when = (
            format_schedule_when(due, zone, repeat, has_time=timed)
            if isinstance(due, datetime)
            else ""
        )
        if when:
            return f"Moved: {title} to {spoken.topic} — {when}.", True
        return f"Moved: {title} to {spoken.topic}.", True
    return format_schedule_result(
        action="set_due",
        title=title,
        due_at=due if isinstance(due, datetime) else None,
        repeat=repeat,
        user_timezone=zone,
        ok=True,
        has_time=timed,
    ), True


def _moved_due(
    item: Any, spoken: SpokenReminderChange, *, user_timezone: str | None, anchor: str | None
) -> datetime | None:
    """The saved clock on the named day, or the same day and clock a week on. A date alone
    moves from its day where it is held (``anchor``) and is held at the new day's start
    there; the named day is the phone's."""
    from app.modules.todos.spoken_when import date_for_day
    from app.services import time_context as time_context_service

    due = getattr(item, "due_at", None)
    if not isinstance(due, datetime):
        return None
    tz = time_context_service.resolve_timezone(user_timezone)
    local = (due if due.tzinfo else due.replace(tzinfo=UTC)).astimezone(tz)
    if not has_time(item):
        local = datetime.combine(local_day(due, anchor), time())
    if spoken.shift_days:
        moved = local + timedelta(days=spoken.shift_days)
    else:
        day = date_for_day(spoken.day or "", datetime.now(tz))
        if day is None:
            return None
        moved = local.replace(year=day.year, month=day.month, day=day.day)
    return moved if has_time(item) else stored_due(moved, anchor, has_time=False)


def format_reminder_reading(items: Sequence[Any], user_timezone: str | None) -> str:
    """One line per saved reminder. Nothing in this text is invented."""
    from app.modules.todos.reminder_writes import format_schedule_when

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
            when = format_schedule_when(due, user_timezone, repeat, has_time=has_time(item))
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
    anchor: str | None = None,
) -> datetime | None:
    from app.modules.todos import spoken_change
    from app.services import time_context as time_context_service

    due = getattr(item, "due_at", None)
    if not isinstance(due, datetime) or hour is None or minute is None:
        return None
    tz = time_context_service.resolve_timezone(user_timezone)
    local = due.astimezone(tz) if due.tzinfo else due.replace(tzinfo=UTC).astimezone(tz)
    if not has_time(item):
        # A date alone's day is where it is held; the clock said is the phone's.
        local = datetime.combine(local_day(due, anchor), time(), tz)
    retimed = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if retimed <= spoken_change._now(tz):
        retimed += timedelta(days=1)
    if repeat == "weekdays":
        while retimed.weekday() >= 5:
            retimed += timedelta(days=1)
    return retimed


def _kept_repeat(item: Any) -> RecurrenceRule | None:
    rule = getattr(item, "recurrence_rule", None)
    return rule if is_recurrence_rule(rule) else None
