"""The coverage contract a bounded learning roadmap follows: one line per day, week or month.

"A 30 day Python plan" is a line for every day (#1495). A plan named in weeks, months or
years goes by the finest unit that stays short: "an 8 week plan to learn guitar" came back as
56 day lines and "Spanish in 3 months" as 138 lines (2026-11-07), where a line per week reads
on a phone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.turn_reading.teaching import programming_tag
from app.services.text_normalize import collapse_ws

_NUMBERS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "twelve": 12,
}
_DAYS_IN = {"day": 1.0, "week": 7.0, "month": 365 / 12, "year": 365.0}
# The plan's length: "70 days", "8-week", "in 3 months", "a year"; never a frequency
# ("4 days a week", "2 days per week").
_DURATION = re.compile(
    r"\b(\d{1,3}|" + "|".join(_NUMBERS) + r")[\s-]?(day|week|month|year)s?\b"
    r"(?!\s+(?:a|an|per|each|every)\s+(?:day|week|month|year)\b)",
    re.IGNORECASE,
)
# "4 days a week", "3 times a week", "an hour a day": the word before "a week" says how often.
_HOW_OFTEN = frozenset(
    {"day", "days", "hour", "hours", "minute", "minutes", "mins", "time", "times", "sessions"}
)
# A named day count up to this many keeps a line per day (#1495).
_MAX_DAYS = 90
# Otherwise: days up to three weeks, weeks up to six months, months up to two years.
_DAY_LINES_UP_TO = 21
_WEEK_LINES_UP_TO = 26
_MONTH_LINES_UP_TO = 24


@dataclass(frozen=True)
class _Coverage:
    unit: str  # "day", "week" or "month"
    count: int

    @property
    def adjective(self) -> str:
        return {"day": "daily", "week": "weekly", "month": "monthly"}[self.unit]


def _length(text: str) -> re.Match[str] | None:
    """The first duration that is the plan's length: "a week" after "4 days" is how often."""
    for match in _DURATION.finditer(text):
        before = text[: match.start()].split()
        if match.group(1).lower() in ("a", "an") and before and before[-1].lower() in _HOW_OFTEN:
            continue
        return match
    return None


def _coverage(text: str) -> _Coverage | None:
    """How many lines the plan gets, and of which unit."""
    match = _length(collapse_ws(text))
    if match is None:
        return None
    amount, unit = match.group(1).lower(), match.group(2).lower()
    count = _NUMBERS[amount] if amount in _NUMBERS else int(amount)
    if unit == "day" and 2 <= count <= _MAX_DAYS:
        return _Coverage("day", count)
    days = count * _DAYS_IN[unit]
    if days < 2:
        return None
    if days <= _DAY_LINES_UP_TO:
        return _Coverage("day", round(days))
    if (weeks := round(days / 7)) <= _WEEK_LINES_UP_TO:
        return _Coverage("week", weeks)
    if (months := round(days / _DAYS_IN["month"])) <= _MONTH_LINES_UP_TO:
        return _Coverage("month", months)
    return None


def learning_plan_contract(text: str) -> str:
    """Return an exact label contract for a bounded roadmap, in the unit that fits it."""
    coverage = _coverage(text)
    if coverage is None:
        return ""
    unit, count, adjective = coverage.unit, coverage.count, coverage.adjective
    label = unit.capitalize()
    labels = " | ".join(f"{label} {n}" for n in range(1, count + 1))
    programming_rule = ""
    # Production experience is a software engineer's: a Spanish or calculus plan ended on
    # "Production experience takes longer than this roadmap" too.
    closing = "`### Checkpoints and milestones` and `### Daily routine`."
    tag = programming_tag(text)
    if tag:
        checkpoints = sorted({max(1, round(count * fraction / 5)) for fraction in range(1, 6)})
        locations = ", ".join(f"{label} {n}" for n in checkpoints)
        programming_rule = (
            f"\n- Include exactly five short runnable ```{tag} code blocks total, placed after "
            f"{locations}. Inline snippets do not count."
        )
        closing = (
            "`### Checkpoints and milestones`, `### Daily routine`, and "
            "`### Production-experience note`. Under the last heading, write the exact sentence "
            "`Production experience takes longer than this roadmap.` before briefly explaining why."
        )
    # A week or a month is one line: the plan never spells out the days inside it.
    whole = "" if unit == "day" else f"- Never list the days inside a {unit}.\n"
    return (
        f"HARD {adjective.upper()}-COVERAGE CONTRACT FOR THIS {count}-{unit.upper()} PLAN:\n"
        f"- The {adjective} breakdown must contain exactly {count} separate Markdown lines, "
        f"one per {unit}.\n"
        f"- Every line must begin with one bold {unit} label in this shape: "
        f"`- **{label} N — Topic:** Learn → Practice/build → Done when ...`.\n"
        f"- Do not combine {unit}s, skip a number, or use a {unit} range in the {adjective} "
        "breakdown.\n"
        f"{whole}"
        f"- Required labels, in order: {labels}.\n"
        f"- Keep every {unit} line compact so {label} {count} and all closing sections fit.\n"
        f"- After the {adjective} lines, include these exact headings: {closing}{programming_rule}"
    )
