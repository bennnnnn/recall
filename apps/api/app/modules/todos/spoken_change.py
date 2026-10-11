"""Apply a clear done, reopen, delete, or move from the user's own words.

The model often confirms those changes without a reminder fence, or labels
"mark done" as a delete. The words the user typed decide the change. A later
extractor must not run again and rewrite the row.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from datetime import tzinfo as TzInfo
from typing import Literal, Protocol

from app.modules.todos.schemas import RecurrenceRule

SpokenAction = Literal["complete", "uncheck", "delete", "set_due"]

_SKIP = frozenset(
    {
        "the",
        "a",
        "an",
        "my",
        "me",
        "to",
        "it",
        "reminder",
        "reminders",
        "todo",
        "todos",
        "task",
        "tasks",
        "call",
        "item",
    }
)
_BULK = frozenset({"overdue", "all", "them", "everything", "these", "those"})
_DONE_TAILS = (" as completed", " as complete", " as done", " completed", " complete", " done")
_TRAILING = (" reminders", " reminder", " todos", " todo", " tasks", " task", " call")
_REPEAT_MARKS: tuple[tuple[str, RecurrenceRule], ...] = (
    ("weekday", "weekdays"),
    ("every day", "daily"),
    ("daily", "daily"),
    ("every week", "weekly"),
    ("weekly", "weekly"),
    ("every month", "monthly"),
    ("monthly", "monthly"),
)


class _Named(Protocol):
    content: str
    checked: bool


@dataclass(frozen=True)
class SpokenReminderChange:
    action: SpokenAction
    title_hint: str
    due_at: datetime | None = None
    repeat: RecurrenceRule | None = None


def user_stated_reminder_change(user_text: str | None) -> bool:
    """True when this turn already says which reminder to change."""
    return parse_spoken_reminder_change(user_text) is not None


def parse_spoken_reminder_change(
    user_text: str | None,
    *,
    user_timezone: str | None = None,
    now: datetime | None = None,
) -> SpokenReminderChange | None:
    """Parse one named done, reopen, delete, or move. Bulk and undated moves stay out."""
    text = _prepare(user_text)
    if not text:
        return None
    lowered = text.lower()
    if lowered.startswith("remove ") and _rest(text, "remove ").lower().startswith("the date"):
        return None
    verbs: tuple[tuple[str, SpokenAction], ...] = (
        ("mark ", "complete"),
        ("complete ", "complete"),
        ("finish ", "complete"),
        ("reopen ", "uncheck"),
        ("uncheck ", "uncheck"),
        ("delete ", "delete"),
        ("remove ", "delete"),
        ("move ", "set_due"),
        ("reschedule ", "set_due"),
    )
    for verb, action in verbs:
        if not lowered.startswith(verb):
            continue
        rest = _rest(text, verb)
        if action == "set_due":
            return _parse_move(rest, user_timezone=user_timezone, now=now)
        if action == "complete":
            rest = _strip_done_tail(rest)
        hint = _clean_title(rest)
        if _words(hint) & _BULK or not _words(hint):
            return None
        return SpokenReminderChange(action=action, title_hint=hint)
    return None


def match_spoken_reminder(
    items: Sequence[_Named],
    hint: str,
    *,
    action: SpokenAction,
) -> _Named | None:
    """Match a hint to one reminder. A tie matches nothing."""
    hint_words = _words(hint)
    if not hint_words:
        return None
    pool = _pool(items, action)
    scored: list[tuple[int, _Named]] = []
    for item in pool:
        words = _words(item.content or "")
        if not words:
            continue
        if hint_words <= words or words <= hint_words:
            scored.append((len(hint_words & words), item))
    if not scored:
        return None
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][1]


def _pool(items: Sequence[_Named], action: SpokenAction) -> list[_Named]:
    if action == "uncheck":
        checked = [item for item in items if item.checked]
        return checked or list(items)
    if action == "delete":
        return list(items)
    open_items = [item for item in items if not item.checked]
    return open_items or list(items)


def _parse_move(
    rest: str,
    *,
    user_timezone: str | None,
    now: datetime | None,
) -> SpokenReminderChange | None:
    from app.modules.todos.reminder_fences import _DAY_NAMES, _due_date_for_day, _parse_clock
    from app.services import time_context as time_context_service

    lowered = rest.lower()
    to_at = lowered.find(" to ")
    if to_at < 0:
        return None
    hint = _clean_title(rest[:to_at])
    if not _words(hint):
        return None
    after = rest[to_at + len(" to ") :]
    day_end = 0
    while day_end < len(after) and after[day_end].isalpha():
        day_end += 1
    day_name = after[:day_end].lower()
    if day_name not in _DAY_NAMES:
        return None
    at_rel = after.lower().find(" at ", day_end)
    if at_rel < 0:
        return None
    clock = _parse_clock(after, at_rel + len(" at "))
    if clock is None:
        return None
    tz = time_context_service.resolve_timezone(user_timezone)
    when = now.astimezone(tz) if now is not None else _now(tz)
    day = _due_date_for_day(day_name, when)
    if day is None:
        return None
    hour, minute = clock
    due = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
    return SpokenReminderChange(
        action="set_due",
        title_hint=hint,
        due_at=due,
        repeat=_repeat(after[at_rel:].lower()),
    )


def _now(tz: TzInfo) -> datetime:
    return datetime.now(tz)


def _repeat(tail: str) -> RecurrenceRule | None:
    for mark, rule in _REPEAT_MARKS:
        if mark in tail:
            return rule
    return None


def _prepare(user_text: str | None) -> str:
    text = (user_text or "").strip()
    while text and text[-1] in ".!?":
        text = text[:-1].rstrip()
    for lead in ("please ", "can you "):
        if text.lower().startswith(lead):
            text = text[len(lead) :].lstrip()
    return text


def _rest(text: str, verb: str) -> str:
    return text[len(verb) :].strip()


def _strip_done_tail(text: str) -> str:
    lowered = text.lower()
    for tail in _DONE_TAILS:
        if lowered.endswith(tail):
            return text[: -len(tail)].rstrip()
    return text


def _clean_title(text: str) -> str:
    title = text.strip().strip("\"'").rstrip(".,;:")
    lowered = title.lower()
    for lead in ("the ", "my ", "a "):
        if lowered.startswith(lead):
            title = title[len(lead) :].strip()
            lowered = title.lower()
            break
    changed = True
    while changed and title:
        changed = False
        lowered = title.lower()
        for tail in _TRAILING:
            if lowered.endswith(tail):
                title = title[: -len(tail)].rstrip()
                changed = True
                break
    return title.strip()


def _words(text: str) -> set[str]:
    words: set[str] = set()
    token: list[str] = []
    for char in text.lower():
        if char.isalnum():
            token.append(char)
            continue
        if token:
            word = "".join(token)
            token = []
            if len(word) > 2 and word not in _SKIP:
                words.add(word)
    if token:
        word = "".join(token)
        if len(word) > 2 and word not in _SKIP:
            words.add(word)
    return words
