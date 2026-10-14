"""Find the day and the clock in a spoken reminder, wherever they sit.

"remind me tomorrow at 6pm to call mom", "remind me tmrw 8am buy injera",
"reminder: renew my passport, oct 20 at 10am", "set a reminder saturday 11am -
meet abel". A clock without am/pm counts only beside a part of the day
("tonight at 9", "9 in the morning"); otherwise the app asks when.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_LEAD = r"\b(?:(?:on|for|by|this|coming)\s+){0,2}"
_DAY_RE = re.compile(
    _LEAD + r"(?P<next>next\s+)?(?P<day>today|tonight|tomorrow|" + "|".join(_WEEKDAYS) + r")\b",
    re.IGNORECASE,
)
# "fri 6pm", "sat 9am": a short day name counts only before a clock.
_SHORT_DAYS = {
    "mon": "monday",
    "tue": "tuesday",
    "tues": "tuesday",
    "wed": "wednesday",
    "thu": "thursday",
    "thur": "thursday",
    "thurs": "thursday",
    "fri": "friday",
    "sat": "saturday",
    "sun": "sunday",
}
_SHORT_DAY_RE = re.compile(
    _LEAD
    + r"(?P<next>next\s+)?(?P<day>"
    + "|".join(_SHORT_DAYS)
    + r")\b\.?(?=\s*(?:at\s+|@\s*)?\d)",
    re.IGNORECASE,
)
_REPEAT_RE = re.compile(
    r"\b(?:every\s*(?P<daily>day|night|morning|evening|afternoon)|(?P<daily2>daily|everyday|nightly)"
    r"|every\s+(?P<weekly>week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"|(?P<weekly2>weekly)|every\s+(?P<weekdays>weekday)|(?P<weekdays2>weekdays)"
    r"|every\s+(?P<monthly>month)|(?P<monthly2>monthly))\b",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    _LEAD + r"(?:(?P<mon>" + _MONTH + r")\.?\s+(?P<d1>\d{1,2})(?:st|nd|rd|th)?"
    r"|(?P<d2>\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<mon2>" + _MONTH + r"))\b",
    re.IGNORECASE,
)
_MERIDIEM_RE = re.compile(
    r"(?:\b(?:at|by)\s+|@\s*)?\b(?P<h>\d{1,2})(?::(?P<m>[0-5]\d))?\s*(?P<ap>[ap])\.?m\b\.?",
    re.IGNORECASE,
)
_NAMED_RE = re.compile(r"(?:\b(?:at|by)\s+)?\b(?P<n>noon|midday|midnight)\b", re.IGNORECASE)
_PART_RE = re.compile(
    r"\b(?P<h>\d{1,2})(?::(?P<m>[0-5]\d))?\s+in\s+the\s+(?P<part>morning|afternoon|evening)\b",
    re.IGNORECASE,
)
# "at 9" or "at 9:30": a clock only beside a part of the day.
_BARE_RE = re.compile(
    r"(?:\b(?:at|by)\s+|@\s*)(?P<h>\d{1,2})(?::(?P<m>[0-5]\d))?\b(?!\s*(?:%|[.,]\d))",
    re.IGNORECASE,
)
_EVENING = re.compile(r"\b(?:tonight|evening|night|afternoon)\b", re.IGNORECASE)
_MORNING = re.compile(r"\bmorning\b", re.IGNORECASE)


@dataclass
class SpokenWhen:
    """``day`` is today, tomorrow, a weekday, "next <weekday>", or "MM-DD"."""

    day: str | None = None
    hour: int | None = None
    minute: int | None = None
    spans: list[tuple[int, int]] = field(default_factory=list)


def find_when(text: str) -> SpokenWhen:
    found = SpokenWhen()
    _find_day(text, found)
    _find_clock(text, found)
    return found


def _find_day(text: str, found: SpokenWhen) -> None:
    date = _DATE_RE.search(text)
    day = _DAY_RE.search(text)
    if date is not None and (day is None or date.start() < day.start()):
        month = _MONTHS[(date.group("mon") or date.group("mon2"))[:3].lower()]
        number = int(date.group("d1") or date.group("d2"))
        if 1 <= number <= 31:
            found.day = f"{month:02d}-{number:02d}"
            found.spans.append(date.span())
            return
    if day is None:
        day = _SHORT_DAY_RE.search(text)
        if day is None:
            return
        name = _SHORT_DAYS[day.group("day").lower()]
        if day.group("next"):
            name = f"next {name}"
        found.day = name
        found.spans.append(day.span())
        return
    name = day.group("day").lower()
    if name == "tonight":
        name = "today"
    elif day.group("next") and name in _WEEKDAYS:
        name = f"next {name}"
    found.day = name
    found.spans.append(day.span())


def _find_clock(text: str, found: SpokenWhen) -> None:
    match = _MERIDIEM_RE.search(text)
    if match is not None:
        hour = int(match.group("h"))
        if 1 <= hour <= 12:
            pm = match.group("ap").lower() == "p"
            _set_clock(found, hour % 12 + (12 if pm else 0), match, text)
            return
    match = _NAMED_RE.search(text)
    if match is not None:
        _set_clock(found, 0 if match.group("n").lower() == "midnight" else 12, match, text)
        return
    match = _PART_RE.search(text)
    if match is not None:
        hour = int(match.group("h"))
        if 1 <= hour <= 12:
            evening = match.group("part").lower() != "morning"
            _set_clock(found, hour % 12 + (12 if evening else 0), match, text)
            return
    match = _BARE_RE.search(text)
    if match is None:
        return
    hour = int(match.group("h"))
    if 13 <= hour <= 23:
        _set_clock(found, hour, match, text)
    elif 1 <= hour <= 12 and _EVENING.search(text):
        _set_clock(found, hour % 12 + 12, match, text)
    elif 1 <= hour <= 12 and _MORNING.search(text):
        _set_clock(found, hour % 12, match, text)


def _set_clock(found: SpokenWhen, hour: int, match: re.Match[str], text: str) -> None:
    minute = match.groupdict().get("m")
    found.hour = hour
    found.minute = int(minute) if minute else 0
    found.spans.append(match.span())


def find_repeat(text: str) -> tuple[str, tuple[int, int]] | None:
    """ "every night" → daily, "every monday" → weekly, with where it was said."""
    match = _REPEAT_RE.search(text)
    if match is None:
        return None
    groups = match.groupdict()
    for rule in ("daily", "weekly", "weekdays", "monthly"):
        if groups.get(rule) or groups.get(f"{rule}2"):
            return rule, match.span()
    return None


def without_spans(text: str, spans: list[tuple[int, int]]) -> str:
    """The text with the day and the clock taken out."""
    kept: list[str] = []
    last = 0
    for start, end in sorted(spans):
        if start < last:
            continue
        kept.append(text[last:start])
        last = end
    kept.append(text[last:])
    return " ".join(" ".join(kept).split())
