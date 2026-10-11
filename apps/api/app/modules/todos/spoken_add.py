"""Create a reminder from the user's words, including a clock that answers 'when?'.

A model 'Set:' line is not a save. A day without a clock is not a save. A
reply that is only '6' finishes the reminder they just described, on that day,
not earlier today.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from datetime import tzinfo as TzInfo
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.todos.schemas import RecurrenceRule

_NEED_A_TIME = "When should I remind you?"
_ALREADY_PASSED = "That time already passed. When should I remind you?"
_USER_CLOCK_RE = re.compile(
    r"\b(?:noon|midnight)\b"
    r"|\b\d{1,2}:\d{2}\b"
    r"|\b\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)\b"
    r"|\b\d{1,2}(?::\d{2})?\s+in\s+the\s+(?:morning|afternoon|evening)\b",
    re.IGNORECASE,
)
_CLAIM_LINE_RE = re.compile(
    r"^(?:added|set|moved|deleted|done|reopened|scheduled|saved|created|date removed)\s*:\s+\S",
    re.IGNORECASE,
)
_ADD_REQUEST_RE = re.compile(
    r"^\s*(?:please\s+)?(?:can you\s+)?(?:add|buy|get|pick up|remind me(?:\s+to)?)\b",
    re.IGNORECASE,
)
_ASKS_WHEN_RE = re.compile(r"\b(?:when|what time|which day)\b", re.IGNORECASE)
_TYPOS = {
    "tommorrow": "tomorrow",
    "tommorow": "tomorrow",
    "tomorow": "tomorrow",
    "tomorrrow": "tomorrow",
    "wekkly": "weekly",
    "wekly": "weekly",
    "weekely": "weekly",
}
_ADD_LEADS = (
    "please add a to-do ",
    "please add a todo ",
    "please add a reminder to ",
    "please add a reminder ",
    "add a to-do ",
    "add a todo ",
    "add a reminder to ",
    "add a reminder ",
    "add a task ",
    "add todo ",
    "add to ",
    "add ",
    "remind me to ",
    "remind me ",
)
_REPEATS: tuple[tuple[str, RecurrenceRule], ...] = (
    ("weekdays", "weekdays"),
    ("weekly", "weekly"),
    ("daily", "daily"),
    ("monthly", "monthly"),
)
_TRAILING_FILLER = frozenset({"for", "on"})


@dataclass(frozen=True)
class SpokenAdd:
    title: str
    day: str | None
    repeat: RecurrenceRule | None
    hour: int | None
    minute: int | None


def user_named_a_clock(user_text: str | None) -> bool:
    """True when this message states a time. A model-picked hour does not count."""
    return bool(user_text and _USER_CLOCK_RE.search(user_text))


def chat_add_needs_a_stated_time(user_text: str | None, due_at: datetime | None) -> bool:
    """A chat create with no user clock is not saved.

    Callers that omit the user text keep the previous fence behavior.
    """
    if user_text is None:
        return False
    if due_at is None:
        return True
    return not user_named_a_clock(user_text)


def reply_when_nothing_saved(text: str, user_text: str | None) -> str:
    """The model must not confirm a reminder the server did not save."""
    lines = text.splitlines()
    kept = [line for line in lines if not _CLAIM_LINE_RE.match(line.strip())]
    changed = len(kept) != len(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip() if changed else text
    needs_time = bool(
        user_text and _ADD_REQUEST_RE.search(user_text) and not user_named_a_clock(user_text)
    ) and not _ASKS_WHEN_RE.search(cleaned)
    if needs_time and (changed or not cleaned.strip()):
        return f"{cleaned}\n\n{_NEED_A_TIME}" if cleaned else _NEED_A_TIME
    if changed and not cleaned.strip():
        return "I didn't change your reminders."
    if not changed:
        return text
    return cleaned


def parse_clock_only(user_text: str | None) -> tuple[int, int] | None:
    """A reply that is only a clock, such as '6' or '6pm'. Other words are not one."""
    raw = (user_text or "").strip()
    while raw and raw[-1] in ".!?":
        raw = raw[:-1].rstrip()
    if raw.lower().startswith("at "):
        raw = raw[3:].strip()
    if not raw:
        return None
    from app.modules.todos.reminder_fences import _parse_clock

    parsed = _parse_clock(raw, 0)
    if parsed is not None and _clock_uses_the_whole_message(raw):
        return parsed
    return _bare_hour(raw)


def parse_spoken_add(user_text: str | None) -> SpokenAdd | None:
    """An add that names a task, and maybe a day, a repeat, and a clock."""
    text = _fix_typos((user_text or "").strip())
    while text and text[-1] in ".!?":
        text = text[:-1].rstrip()
    lowered = text.lower()
    if not lowered:
        return None
    body = ""
    for lead in _ADD_LEADS:
        if lowered.startswith(lead):
            body = text[len(lead) :].strip()
            break
    if not body:
        return None
    day, day_at = _find_day(body)
    repeat = _find_repeat(body)
    hour, minute = _clock_in(body)
    title = _title_before(body, day_at)
    if not title:
        return None
    return SpokenAdd(title=title[:500], day=day, repeat=repeat, hour=hour, minute=minute)


async def pending_add(session: AsyncSession, chat_id: UUID, current: str) -> SpokenAdd | None:
    """The add they just described, when this message is only the missing clock."""
    from app.repositories import messages as messages_repo

    rows = await messages_repo.list_recent(session, chat_id, limit=8)
    skipped_current = False
    for message in reversed(rows):
        if getattr(message, "role", None) != "user":
            continue
        body = (getattr(message, "content", None) or "").strip()
        if not skipped_current and body == current.strip():
            skipped_current = True
            continue
        if parse_clock_only(body) is not None:
            continue
        add = parse_spoken_add(body)
        if add is None or add.hour is not None or not add.day:
            return None
        return add
    return None


def due_for_add(
    add: SpokenAdd,
    *,
    user_timezone: str | None,
    now: datetime | None = None,
    hour: int | None = None,
    minute: int | None = None,
) -> datetime | None:
    """The instant they named. None when the day or the clock is missing."""
    clock_hour = add.hour if hour is None else hour
    clock_minute = add.minute if minute is None else minute
    if add.day is None or clock_hour is None or clock_minute is None:
        return None
    from app.modules.todos.reminder_fences import _due_date_for_day
    from app.services import time_context as time_context_service

    tz = time_context_service.resolve_timezone(user_timezone)
    when = now.astimezone(tz) if now is not None else _now(tz)
    day = _due_date_for_day(add.day, when)
    if day is None:
        return None
    return datetime(day.year, day.month, day.day, clock_hour, clock_minute, tzinfo=tz)


def due_is_past(
    due: datetime,
    *,
    user_timezone: str | None,
    now: datetime | None = None,
) -> bool:
    from app.services import time_context as time_context_service

    normalized = time_context_service.normalize_due_at(due, user_timezone)
    if normalized is None:
        return False
    current = now.astimezone(UTC) if now is not None else _now(UTC)
    return normalized <= current


def passed_time_reply() -> str:
    return _ALREADY_PASSED


def _now(tz: TzInfo) -> datetime:
    return datetime.now(tz)


def _fix_typos(text: str) -> str:
    parts: list[str] = []
    token: list[str] = []
    for char in text:
        if char.isalpha():
            token.append(char)
            continue
        if token:
            parts.append(_replace_token("".join(token)))
            token = []
        parts.append(char)
    if token:
        parts.append(_replace_token("".join(token)))
    return "".join(parts)


def _replace_token(token: str) -> str:
    fixed = _TYPOS.get(token.lower())
    return fixed if fixed is not None else token


def _find_day(body: str) -> tuple[str | None, int]:
    from app.modules.todos.reminder_fences import _DAY_NAMES

    lowered = body.lower()
    best: tuple[str, int] | None = None
    for name in _DAY_NAMES:
        at = _word_at(lowered, name)
        if at >= 0 and (best is None or at < best[1]):
            best = (name, at)
    if best is None:
        return None, -1
    return best


def _find_repeat(body: str) -> RecurrenceRule | None:
    lowered = body.lower()
    for word, rule in _REPEATS:
        if _word_at(lowered, word) >= 0:
            return rule
    return None


def _clock_in(body: str) -> tuple[int | None, int | None]:
    from app.modules.todos.reminder_fences import _parse_clock

    lowered = body.lower()
    at = lowered.rfind(" at ")
    if at < 0:
        return None, None
    parsed = _parse_clock(body, at + len(" at "))
    if parsed is None:
        return None, None
    return parsed


def _title_before(body: str, day_at: int) -> str:
    chunk = body[:day_at] if day_at >= 0 else body
    words = []
    for word in chunk.split():
        bare = word.strip("\"'.,;:").lower()
        if not bare or any(bare == name for name, _rule in _REPEATS):
            continue
        words.append(word.strip("\"'.,;:"))
    while words and words[-1].lower() in _TRAILING_FILLER:
        words.pop()
    return " ".join(words).strip()


def _word_at(haystack: str, word: str) -> int:
    start = 0
    while True:
        found = haystack.find(word, start)
        if found < 0:
            return -1
        before = found == 0 or not haystack[found - 1].isalpha()
        after_at = found + len(word)
        after = after_at >= len(haystack) or not haystack[after_at].isalpha()
        if before and after:
            return found
        start = found + 1


def _clock_uses_the_whole_message(text: str) -> bool:
    """True when nothing but a clock remains. '6pm tomorrow' is not clock-only."""
    from app.modules.todos.reminder_fences import _parse_clock

    parsed_at = 0
    # _parse_clock does not report where it stopped. A clock-only message has
    # no weekday or other word after the meridiem.
    if _parse_clock(text, 0) is None:
        return False
    lowered = text.lower()
    for mark in ("am", "pm", "a.m", "p.m"):
        at = lowered.find(mark)
        if at >= 0:
            parsed_at = at + len(mark)
            break
    rest = lowered[parsed_at:].strip(" .")
    return rest == ""


def _bare_hour(text: str) -> tuple[int, int] | None:
    """'6' and '6:30' mean that hour in the evening. '18' stays 18:00."""
    compact = text.replace(" ", "")
    if not compact or not compact[0].isdigit():
        return None
    hour = 0
    index = 0
    digits = 0
    while index < len(compact) and compact[index].isdigit() and digits < 2:
        hour = hour * 10 + (ord(compact[index]) - 48)
        index += 1
        digits += 1
    minute = 0
    if index < len(compact) and compact[index] == ":":
        index += 1
        if index + 1 >= len(compact) or not (
            compact[index].isdigit() and compact[index + 1].isdigit()
        ):
            return None
        minute = (ord(compact[index]) - 48) * 10 + (ord(compact[index + 1]) - 48)
        index += 2
    if index != len(compact) or minute > 59 or hour > 23:
        return None
    if hour < 12:
        hour += 12
    if hour == 24:
        return None
    return hour, minute
