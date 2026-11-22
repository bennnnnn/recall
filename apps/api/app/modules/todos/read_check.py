"""The model's reading of a reminder request, held to the user's words and timed by the server.

``model_read`` returns a candidate: the task, the day and the clock as the user said them,
each with a quote. Nothing in it is saved as written:

- every quote must be in one of the user's own lines (a reply's words never are);
- the task must share its words with the user's lines (a task nobody named is dropped);
- the day, the clock, a time from now, a lead time ("an hour before") and a repeat are read
  from those quotes by the app's own reader of a when (``spoken_when``), never taken from the
  model's numbers; only a date the reader has no words for ("the 23rd", "next week's
  Thursday") is taken as the model wrote it, and only when its quote is the user's;
- an hour with no am or pm is settled by the rule (``bare_hour``), unless the user's words
  say which half ("pm", "in the afternoon", "dinner");
- a day with no clock is 9 AM, or the hour of the part of the day they said ("tonight" is
  8 PM); a clock with no day is the next one.

What is left missing is asked once: the task, or when, when nothing says it. A question the
last reply already asked is never asked again: an answer that still says no when is taken as
tomorrow at 9 AM, which the card shows for the user to confirm or change.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import cast

from app.modules.todos.bare_hour import settle_bare
from app.modules.todos.model_read import ReminderReading
from app.modules.todos.recurrence import RecurrenceRule
from app.modules.todos.schemas import TODO_TEXT_MAX_CHARS
from app.modules.todos.spoken_add import SpokenAdd, due_for_add, due_is_past, fix_typos
from app.modules.todos.spoken_when import find_repeat, find_when
from app.services.text_normalize import straighten_apostrophes

ASK_TASK = "What should I remind you about?"
ASK_WHEN = "When should I remind you?"
PASSED = "That time already passed. When should I remind you?"

# The hour a part of the day stands for when no clock was said, and a day alone.
_PART_HOURS = (
    (re.compile(r"\b(?:tonight|night|bedtime)\b", re.I), 20),
    (re.compile(r"\bevening\b", re.I), 18),
    (re.compile(r"\bafternoon\b", re.I), 15),
    (re.compile(r"\b(?:lunch|lunchtime|midday)\b", re.I), 12),
    (re.compile(r"\bmorning\b", re.I), 9),
)
_DAY_ALONE_HOUR = 9
# Words that say which half of the day a bare hour is.
_PM_WORDS = re.compile(
    r"\b(?:p\.?m\.?|afternoon|evening|night|tonight|dinner|supper|after work|after school)\b",
    re.I,
)
_AM_WORDS = re.compile(r"\b(?:a\.?m\.?|morning|breakfast|before work|before school)\b", re.I)
_CLOCK_DIGITS = re.compile(r"(?<!\d)(\d{1,2})(?::([0-5]\d))?(?!\d)")
_BEFORE_WORDS = re.compile(r"\b(?:before|earlier|ahead|early|prior)\b.*$", re.I)
_WORD = re.compile(r"[^\W\d_]{3,}")
_NOT_TASK_WORDS = frozenset(
    "the and for with about remind reminder reminders please can you could would tomorrow "
    "today tonight tmrw this that then them they she her his him my our your its it's at on "
    "in to of me set make sure don't dont forget ping".split()
)
_PRONOUN_TASK = re.compile(r"\b(?:it|that|this|them|those|these)\b", re.I)
# A date the model wrote: a year at most ahead.
_MAX_DAYS_AHEAD = 366


@dataclass(frozen=True)
class CheckedRequest:
    """What the server makes of the reading: the card's adds, or the one question to ask."""

    adds: tuple[SpokenAdd, ...] = ()
    ask: str | None = None


def _plain(text: str) -> str:
    straight = straighten_apostrophes(text.casefold())
    return " ".join(re.sub(r"[^\w':]+", " ", straight).split())


def grounded(quote: str, user_lines: Sequence[str]) -> bool:
    """The quote is the user's own words: in one of their lines, up to case and marks."""
    said = _plain(quote)
    return bool(said) and any(said in _plain(line) for line in user_lines)


def _stem(word: str) -> str:
    return word.casefold()[:4]


def task_title(reading: ReminderReading, user_lines: Sequence[str]) -> str | None:
    """The card's title: the model's task when its quote is the user's and its words are
    theirs (one word of its own at most, "Call" or "Study"); None otherwise."""
    task = " ".join(reading.task.split())
    if not task or not grounded(reading.task_quote, user_lines):
        return None
    said = {_stem(word) for line in user_lines for word in _WORD.findall(line)}
    words = [w for w in _WORD.findall(task) if w.casefold() not in _NOT_TASK_WORDS]
    if not words or (_PRONOUN_TASK.search(task) and len(words) <= 2):
        # "Write it down": what "it" is was said elsewhere, and the card would not say it.
        return None
    own = sum(1 for word in words if _stem(word) in said)
    if own == 0 or len(words) - own > max(1, len(words) // 3):
        return None
    return (task[:1].upper() + task[1:])[:TODO_TEXT_MAX_CHARS]


def _quoted(quote: str, user_lines: Sequence[str]) -> str:
    """The quote, typos read ("tmrw"), when it is the user's; "" otherwise."""
    return fix_typos(quote) if grounded(quote, user_lines) else ""


# "in like 20 mins", "in about an hour": the hedge says nothing of the time.
_HEDGES = re.compile(r"\b(?:like|about|around|roughly|maybe|approx(?:imately)?|just|~)\s+", re.I)


def _minutes_in(quote: str) -> int | None:
    """ "in 2 hours", "an hour", "15 minutes before": the minutes the words say."""
    words = _HEDGES.sub("", _BEFORE_WORDS.sub("", quote)).strip()
    if not words:
        return None
    lead = "" if re.match(r"^(?:in|after)\b", words, re.I) else "in "
    return find_when(f"{lead}{words}").after_minutes


def _model_date(reading: ReminderReading, today: date) -> str | None:
    """The model's YYYY-MM-DD as the reader's "MM-DD", within a year from today."""
    try:
        day = date.fromisoformat(reading.date)
    except ValueError:
        return None
    if not 0 <= (day - today).days <= _MAX_DAYS_AHEAD:
        return None
    return f"{day.month:02d}-{day.day:02d}"


@dataclass
class _When:
    day: str | None = None
    hour: int | None = None
    minute: int = 0
    bare: tuple[int, int] | None = None
    after: int | None = None


def _part_hour(text: str) -> int | None:
    return next((hour for pattern, hour in _PART_HOURS if pattern.search(text)), None)


def _clock_of(time_text: str, model_time: str) -> tuple[int | None, tuple[int, int] | None, int]:
    """(24-hour hour, bare 12-hour clock, minute) the time quote says by digits the model's
    time names too: "five-ish" is no clock, "at 5ish" with time "5" is a bare 5."""
    said = _CLOCK_DIGITS.search(time_text)
    named = _CLOCK_DIGITS.search(model_time)
    if said is None or named is None or said.group(1) != named.group(1):
        return None, None, 0
    hour, minute = int(said.group(1)), int(said.group(2) or 0)
    if 13 <= hour <= 23:
        return hour, None, minute
    if 1 <= hour <= 12:
        return None, (hour, minute), minute
    return None, None, 0


def _when(reading: ReminderReading, user_lines: Sequence[str], today: date) -> _When:
    """The day and clock the quotes say, read by the app's own reader."""
    day_text = _quoted(reading.day_quote, user_lines)
    time_text = _quoted(reading.time_quote, user_lines)
    found = _When()
    in_text = _quoted(reading.in_quote, user_lines)
    if in_text:
        found.after = _minutes_in(in_text)
    # The day from the day's words and the clock from the clock's: "at 6pm" quoted as the day
    # of "make it 7 instead" is the old card's time, not the new one (the day's words give
    # the clock only when the clock has none of its own, "tmrw at 5pm").
    found.day = find_when(day_text).day if day_text else None
    if found.day is None and day_text:
        found.day = _model_date(reading, today)
    spoken = find_when(time_text) if time_text else find_when(day_text)
    if spoken.hour is None and spoken.bare is None and time_text and _part_hour(day_text):
        # "tonight" + "at 8": the part of the day settles the clock's half.
        spoken = find_when(f"{day_text} {time_text}")
    if spoken.hour is not None:
        found.hour, found.minute = spoken.hour, spoken.minute or 0
    elif spoken.bare is not None:
        found.bare = spoken.bare
    elif time_text:
        found.hour, found.bare, found.minute = _clock_of(time_text, reading.time)
    if found.hour is None and found.bare is None:
        part = _part_hour(f"{time_text} {day_text}")
        if part is not None:
            found.hour = part
    return found


def _half(reading: ReminderReading, user_lines: Sequence[str]) -> int | None:
    """12 or 0 when the user's words say which half a bare hour is in; None otherwise."""
    words = " ".join(
        _quoted(quote, user_lines)
        for quote in (
            reading.half_quote,
            reading.time_quote,
            reading.day_quote,
            reading.repeat_quote,
        )
    ).strip()
    if not words:
        return None
    if _PM_WORDS.search(words):
        return 12
    if _AM_WORDS.search(words):
        return 0
    return None


def _repeat(reading: ReminderReading, user_lines: Sequence[str]) -> RecurrenceRule | None:
    """The repeat the user's words say: its own quote, or the when's ("at 9 every night")."""
    for quote in (reading.repeat_quote, reading.time_quote, reading.day_quote):
        words = _quoted(quote, user_lines)
        found = find_repeat(words) if words else None
        if found is not None:
            return cast(RecurrenceRule, found[0])
    return None


def _when_from_an_older_line(reading: ReminderReading, user_lines: Sequence[str]) -> bool:
    """The last message says when, and the reading's clock or day is quoted from another."""
    if not user_lines:
        return False
    latest = user_lines[-1]
    said = find_when(fix_typos(latest))
    if not (said.spans or _CLOCK_DIGITS.search(latest)):
        return False
    quotes = [q for q in (reading.time_quote, reading.day_quote, reading.in_quote) if q.strip()]
    if not quotes or any(grounded(quote, [latest]) for quote in quotes):
        return False
    # "pm, … 5 is fine" after "tmrw at 5": the latest line says the same 5.
    hours = {match.group(1) for match in _CLOCK_DIGITS.finditer(latest)}
    older = {match.group(1) for quote in quotes for match in _CLOCK_DIGITS.finditer(quote)}
    return not older or not older & hours


def check_reading(
    reading: ReminderReading | None,
    user_lines: Sequence[str],
    *,
    user_timezone: str | None,
    now: datetime | None = None,
    asked_before: bool = False,
) -> CheckedRequest | None:
    """The card the reading makes once every value is the user's, or the one question left;
    None for no request. ``user_lines``: the user's messages in the chat, this one included.
    ``asked_before``: the last reply asked for this reminder's details already."""
    if reading is None or reading.request == "none":
        return None
    from app.services import time_context as time_context_service

    tz = time_context_service.resolve_timezone(user_timezone)
    local = now.astimezone(tz) if now is not None else datetime.now(tz)
    title = task_title(reading, user_lines)
    if title is None:
        return None if asked_before else CheckedRequest(ask=ASK_TASK)
    if _when_from_an_older_line(reading, user_lines):
        # "make it 7 instead" after "at 6pm": the latest when is the request's (a read that
        # quoted the 6pm is not taken; the word rules' re-time stands).
        return None
    when = _when(reading, user_lines, local.date())
    repeat = _repeat(reading, user_lines)
    if when.after is not None and when.day is None and when.hour is None and when.bare is None:
        return CheckedRequest(adds=(SpokenAdd(title, None, None, None, None, when.after),))
    if when.day is None and when.hour is None and when.bare is None:
        if not asked_before and repeat is None:
            return CheckedRequest(ask=ASK_WHEN)
        when.day = "tomorrow" if repeat is None else "today"
        when.hour = _DAY_ALONE_HOUR
    half = _half(reading, user_lines)
    if when.bare is not None and half is not None:
        when.hour, when.minute, when.bare = when.bare[0] % 12 + half, when.bare[1], None
    if when.hour is None and when.bare is None:
        when.hour = _DAY_ALONE_HOUR
    add = SpokenAdd(
        title=title,
        day=when.day,
        repeat=repeat,
        hour=when.hour,
        minute=when.minute if when.hour is not None else None,
        bare=when.bare,
    )
    add = settle_bare(add, user_timezone=user_timezone, now=local)
    if add.day is None and add.hour is not None:
        add = _next_clock(add, user_timezone, local)
    return _timed(add, reading, user_lines, user_timezone, local)


def _next_clock(add: SpokenAdd, user_timezone: str | None, now: datetime) -> SpokenAdd:
    """A clock with no day is the next one: today, or tomorrow once it passed."""
    today = replace(add, day="today")
    due = due_for_add(today, user_timezone=user_timezone, now=now)
    if due is not None and due_is_past(due, user_timezone=user_timezone, now=now):
        return replace(add, day="tomorrow")
    return today


def _timed(
    add: SpokenAdd,
    reading: ReminderReading,
    user_lines: Sequence[str],
    user_timezone: str | None,
    now: datetime,
) -> CheckedRequest:
    """The add at its instant, a lead time taken off ("an hour before"); a one-off that
    passed asks again."""
    due = due_for_add(add, user_timezone=user_timezone, now=now)
    if due is None:
        return CheckedRequest(ask=ASK_WHEN)
    before_text = _quoted(reading.before_quote, user_lines)
    before = _minutes_in(before_text) if before_text else None
    if before is not None:
        due -= timedelta(minutes=before)
        add = replace(add, day=f"{due.month:02d}-{due.day:02d}", hour=due.hour, minute=due.minute)
    if add.repeat is None and due_is_past(due, user_timezone=user_timezone, now=now):
        return CheckedRequest(ask=PASSED)
    return CheckedRequest(adds=(add,))
