"""Apply a clear done, reopen, delete, or move from the user's own words.

The model often confirms those changes without a reminder fence, or labels
"mark done" as a delete. The words the user typed decide the change. A later
extractor must not run again and rewrite the row.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
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
_PRONOUNS = frozenset({"it", "this", "that"})
_FILLERS = frozenset({"for", "to", "at", "on", "the", "a", "an"})
_DONE_TAILS = (" as completed", " as complete", " as done", " completed", " complete", " done")
_TRAILING = (" reminders", " reminder", " todos", " todo", " tasks", " task", " call")
_REPEAT_MARKS: tuple[tuple[str, RecurrenceRule], ...] = (
    ("weekday", "weekdays"),
    ("everyday", "daily"),
    ("every day", "daily"),
    ("daily", "daily"),
    ("every week", "weekly"),
    ("weekly", "weekly"),
    ("every month", "monthly"),
    ("monthly", "monthly"),
)
_ADJUST_LEADS = ("make ", "change ", "set ", "put ", "move ")
_READ_OPENINGS = (
    "what reminders do i have",
    "what are my reminders",
    "what are my todos",
    "whats on my schedule",
    "what is on my schedule",
    "what is scheduled",
    "whats scheduled",
    "what do i have scheduled",
    "what do i have on my schedule",
    "do i have any reminders",
    "do i have reminders",
    "show my reminders",
    "show my schedule",
    "show me my reminders",
    "show me my schedule",
    "list my reminders",
    "list my todos",
    "list my schedule",
    "read my reminders",
    "read my schedule",
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
    use_latest: bool = False
    keep_date: bool = False
    hour: int | None = None
    minute: int | None = None
    topic: str | None = None
    needs_time: bool = False


def user_stated_reminder_change(user_text: str | None) -> bool:
    """True when this turn already says which reminder to change."""
    return parse_spoken_reminder_change(user_text) is not None


def asks_to_read_reminders(user_text: str | None) -> bool:
    """True when they asked what is saved, not to change it."""
    text = _prepare(user_text).lower().replace("'", "").replace("\u2019", "")
    if not text or text.startswith(("add ", "remind ", "make ", "delete ", "move ")):
        return False
    return any(text.startswith(opening) for opening in _READ_OPENINGS)


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
            parsed = _parse_move(rest, user_timezone=user_timezone, now=now)
            if parsed is not None:
                return parsed
            continue
        if action == "complete":
            rest = _strip_done_tail(rest)
        hint = _clean_title(rest)
        if _words(hint) & _BULK:
            return None
        if _is_only_pronoun(hint):
            return SpokenReminderChange(action=action, title_hint="", use_latest=True)
        if not _words(hint):
            return None
        return SpokenReminderChange(action=action, title_hint=hint)
    return _parse_adjust(text, user_timezone=user_timezone, now=now)


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
    use_latest = _is_only_pronoun(hint)
    if not _words(hint) and not use_latest:
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
        title_hint="" if use_latest else hint,
        due_at=due,
        repeat=_repeat(after[at_rel:].lower()),
        use_latest=use_latest,
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


def resolve_spoken_target(items: Sequence[_Named], change: SpokenReminderChange) -> _Named | None:
    """The named reminder, or the latest one when they said it/this/that."""
    if change.use_latest or not _words(change.title_hint):
        return latest_reminder(items, change.action)
    return match_spoken_reminder(items, change.title_hint, action=change.action)


def latest_reminder(items: Sequence[_Named], action: SpokenAction) -> _Named | None:
    pool = _pool(items, action)
    if not pool:
        return None
    return max(pool, key=_recency)


def _recency(item: _Named) -> tuple[datetime, datetime]:
    return (_moment(getattr(item, "updated_at", None)), _moment(getattr(item, "created_at", None)))


def _moment(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    return datetime.min.replace(tzinfo=UTC)


def _parse_adjust(
    text: str,
    *,
    user_timezone: str | None,
    now: datetime | None,
) -> SpokenReminderChange | None:
    """'Make it daily', 'make it 8:00 AM', or 'put it in Health'."""
    lowered = text.lower()
    body = ""
    for lead in _ADJUST_LEADS:
        if lowered.startswith(lead):
            body = text[len(lead) :].strip()
            break
    if not body or _is_fresh_reminder(body):
        return None
    clock = _clock_in_change(body)
    day = _marked_day(body)
    repeat = _repeat(body.lower())
    topic = None
    if clock is None and repeat is None and day is None:
        topic = _topic_name(body)
    hint, use_latest = _subject(body, clock=clock, day=day, repeat=repeat, topic=topic)
    if day is not None and clock is not None:
        due = _due_on_day(day[0], clock[0], clock[1], user_timezone=user_timezone, now=now)
        if due is None:
            return None
        return SpokenReminderChange(
            action="set_due",
            title_hint=hint,
            due_at=due,
            repeat=repeat,
            use_latest=use_latest,
        )
    if day is not None:
        return SpokenReminderChange(
            action="set_due",
            title_hint=hint,
            use_latest=use_latest,
            needs_time=True,
        )
    if clock is not None:
        return SpokenReminderChange(
            action="set_due",
            title_hint=hint,
            repeat=repeat,
            use_latest=use_latest,
            keep_date=True,
            hour=clock[0],
            minute=clock[1],
        )
    if repeat is not None:
        return SpokenReminderChange(
            action="set_due",
            title_hint=hint,
            repeat=repeat,
            use_latest=use_latest,
        )
    if topic is not None:
        return SpokenReminderChange(
            action="set_due",
            title_hint=hint,
            use_latest=use_latest,
            topic=topic,
        )
    return None


def _is_fresh_reminder(body: str) -> bool:
    lowered = body.lower()
    return lowered.startswith(
        ("a reminder", "a todo", "a to-do", "a task", "an alarm", "reminder ")
    )


def _subject(
    body: str,
    *,
    clock: tuple[int, int, int] | None,
    day: tuple[str, int] | None,
    repeat: RecurrenceRule | None,
    topic: str | None,
) -> tuple[str, bool]:
    cut = len(body)
    lowered = body.lower()
    if repeat is not None:
        for mark, rule in _REPEAT_MARKS:
            if rule != repeat:
                continue
            at = lowered.find(mark)
            if at >= 0:
                cut = min(cut, at)
    if clock is not None:
        cut = min(cut, clock[2])
    if day is not None:
        cut = min(cut, day[1])
    if topic is not None:
        for mark in (" in the ", " in ", " under the ", " under ", "category", "topic"):
            at = lowered.find(mark)
            if at >= 0:
                cut = min(cut, at)
    hint = _clean_title(_strip_fillers(body[:cut]))
    if _is_only_pronoun(hint) or not _words(hint):
        return "", True
    return hint, False


def _due_on_day(
    day_name: str,
    hour: int,
    minute: int,
    *,
    user_timezone: str | None,
    now: datetime | None,
) -> datetime | None:
    from app.modules.todos.reminder_fences import _due_date_for_day
    from app.services import time_context as time_context_service

    tz = time_context_service.resolve_timezone(user_timezone)
    when = now.astimezone(tz) if now is not None else _now(tz)
    day = _due_date_for_day(day_name, when)
    if day is None:
        return None
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)


def _clock_in_change(text: str) -> tuple[int, int, int] | None:
    from app.modules.todos.reminder_fences import _parse_clock

    for index, char in enumerate(text):
        if not char.isdigit():
            continue
        parsed = _parse_clock(text, index)
        if parsed is not None:
            return parsed[0], parsed[1], index
    return _bare_hour_in(text)


def _bare_hour_in(text: str) -> tuple[int, int, int] | None:
    """A trailing hour with no am/pm. 1-11 means PM, matching a new reminder."""
    for index, char in enumerate(text):
        if not char.isdigit() or (index > 0 and text[index - 1].isalpha()):
            continue
        end = index
        hour = 0
        digits = 0
        while end < len(text) and text[end].isdigit() and digits < 2:
            hour = hour * 10 + (ord(text[end]) - 48)
            end += 1
            digits += 1
        if digits == 0 or (end < len(text) and text[end] == ":"):
            continue
        if text[end:].strip(" ."):
            continue
        if hour == 0 or hour > 23:
            continue
        if 1 <= hour <= 11:
            hour += 12
        return hour, 0, index
    return None


def _marked_day(text: str) -> tuple[str, int] | None:
    from app.modules.todos.reminder_fences import _DAY_NAMES

    lowered = text.lower()
    for mark in (" to ", " on ", " for "):
        start = 0
        while start < len(lowered):
            at = lowered.find(mark, start)
            if at < 0:
                break
            rest_at = at + len(mark)
            while rest_at < len(lowered) and lowered[rest_at] == " ":
                rest_at += 1
            end = rest_at
            while end < len(lowered) and lowered[end].isalpha():
                end += 1
            name = lowered[rest_at:end]
            if name in _DAY_NAMES:
                return name, rest_at
            start = at + len(mark)
    return None


def _topic_name(body: str) -> str | None:
    lowered = body.lower()
    for mark in ("category to ", "topic to ", " in the ", " in ", " under the ", " under ", " to "):
        at = lowered.rfind(mark)
        if at < 0:
            continue
        name = body[at + len(mark) :].strip().strip(".,!?").strip()
        if name.lower().endswith(" category"):
            name = name[: -len(" category")].strip()
        if _ok_topic(name):
            return name
    return None


def _ok_topic(name: str) -> bool:
    from app.modules.todos.reminder_fences import _DAY_NAMES

    if not name or len(name) > 40:
        return False
    words = name.split()
    if not 1 <= len(words) <= 3 or not all(word.isalpha() for word in words):
        return False
    lowered = name.lower()
    if lowered in _DAY_NAMES or lowered in _PRONOUNS:
        return False
    if lowered in {"morning", "afternoon", "evening", "night", "daily", "weekly", "monthly"}:
        return False
    return "everyday" not in lowered and "week" not in lowered


def _strip_fillers(text: str) -> str:
    parts = text.split()
    while parts and parts[-1].strip(".,!?").lower() in _FILLERS:
        parts.pop()
    while parts and parts[0].strip(".,!?").lower() in _FILLERS:
        parts.pop(0)
    return " ".join(parts)


def _is_only_pronoun(text: str) -> bool:
    parts = [
        part
        for part in (word.strip(".,!?").lower() for word in text.split())
        if part and part not in _FILLERS
    ]
    return len(parts) == 1 and parts[0] in _PRONOUNS
