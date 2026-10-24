"""A message that lists numbers: "Monthly rainfall in Addis Ababa: Jan 15, Feb 30, …".

Qwen3.7 Flash, the free plan's everyday model, answered that message "Hey bini! How's it
going?" four times in four (2026-10-24): a list with no question read to it as an opener.
Told what the message is, it answered about the numbers, but named November (6 mm) the
driest month once in five and summed the year wrong when asked for a total. So the highest
and lowest are read here, from the message, and the reply only words them.

The note is conditional ("if the message or the conversation asks for something, do that"),
because no reading of the words can tell every request apart from a list ("Summarize: rent
1200, …", "… is that too much", a list typed in answer to the last reply's question, another
language): a list the model is asked about stays the model's to answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.chat.prompt_constants.routing import is_personal_disclosure_turn
from app.modules.chat.prompt_constants.teaching import is_standing_preference

# "Jan 15", "rent: 1,200", "Q1 10k", "Dec 5 mm", "savings = -$300", "2024 7%".
_PAIR = re.compile(
    r"(?P<label>[^\W\d_][\w .&'/()-]{0,40}?|(?:19|20)\d\d)\s*[:=]?\s*"
    r"(?P<sign>[-+]?)(?P<currency>[$€£]?)(?P<number>\d{1,15}(?:,\d{3})*(?:\.\d+)?)\s*"
    r"(?P<unit>%|[^\W\d_]{1,8}\.?)?"
)
# Items: a comma that is not a thousands separator, a semicolon, a line, a closing "and".
_ITEMS = re.compile(r",(?!\d{3}(?!\d))|;|\n|\s+and\s+")
# A request in English: the other rules' turn (the note's "if it asks for something" covers
# the rest).
_ASKS = re.compile(
    r"\b(?:make|plot|graph|chart|draw|show|calculate|compute|work\s+out|find|add|sum|total|"
    r"average|mean|sort|rank|compare|convert|remind|remember|forget|save|put|give|tell|explain|"
    r"analy[sz]e|summari[sz]e|help|can|could|would|should|please|pls|what|how|why|which|when|"
    r"where|who)\b",
    re.IGNORECASE,
)
# "My brother is 30": a sentence, not a label.
_CLAUSE = re.compile(r"(?:^|\s)(?:is|are|was|were|am|i'?m|have|has|had|got)$", re.IGNORECASE)
# A number of its own inside a label: "transport 100 for 2 people" is no "label value".
# "Week 1", "Q1" and "grade 9" keep theirs.
_NUMBER_IN_LABEL = re.compile(r"(?:^|\s)\d{2,}(?:\s|$)")
# A loan or a card, two of its terms or more: the money reader's to work, not a series to
# compare. One is a label ("Apr 85" is April).
_MONEY_TERMS = frozenset(
    {
        "rate",
        "interest",
        "interest rate",
        "apr",
        "term",
        "years",
        "months",
        "payment",
        "monthly payment",
        "balance",
        "principal",
        "down payment",
    }
)
# "Dentist 3pm, gym 7pm" are times of day, not amounts.
_CLOCK_UNITS = frozenset({"am", "pm", "a.m", "p.m", "o'clock"})
# "10k" beside "900": compared as 10,000. "m" and "b" stay units (metres, bytes).
_SCALE = {"k": 1e3, "thousand": 1e3, "million": 1e6, "mn": 1e6, "bn": 1e9, "billion": 1e9}
_YEAR = re.compile(r"(?:19|20)\d\d")
_DIGIT = re.compile(r"\d")
# A question mark in Latin, CJK (fullwidth) and Arabic text.
_QUESTION_MARKS = ("?", "\uff1f", "\u061f")
_MAX_CHARS = 2000
_MIN_PAIRS = 3

SHARED_NUMBERS_HINT = (
    "The user's message lists values. It is not a greeting: never greet them or ask how they "
    "are. If the message or the conversation asks for something, do that. Otherwise say in one "
    "or two short sentences what the values show, then offer one next step that fits, such as "
    "a chart; do not add them up or average them unless asked."
)


@dataclass(frozen=True)
class SharedValue:
    label: str
    value: float  # for comparing, "10k" as 10,000
    written: str  # the number as the user wrote it: "1,200", "-$300", "10k"
    unit: str  # "mm", "%", or "" (one item may carry the unit for all: "Nov 6, Dec 5 mm")


def _pair(item: str) -> SharedValue | None:
    """One "label number unit" item, or the item after a title's colon ("…: Jan 15")."""
    text = item.strip().rstrip(".")
    for candidate in (text, text.rpartition(":")[2].strip()):
        match = _PAIR.fullmatch(candidate)
        if match is None:
            continue
        label = match["label"].strip()
        if _CLAUSE.search(label) or (not _YEAR.fullmatch(label) and _NUMBER_IN_LABEL.search(label)):
            continue
        unit = (match["unit"] or "").rstrip(".")
        number = match["number"]
        value = float(number.replace(",", "")) * (-1 if match["sign"] == "-" else 1)
        written = f"{match['sign']}{match['currency']}{number}"
        if unit.lower() in _SCALE:
            return SharedValue(label, value * _SCALE[unit.lower()], written + unit, "")
        return SharedValue(label, value, written, unit)
    return None


def shared_numbers(text: str) -> list[SharedValue] | None:
    """The values a message lists, in order, or None.

    Three or more, in one unit (an item may leave it off: "Nov 6, Dec 5 mm"), every item
    but one a value (a title line with no number may stand alone), with no question mark
    or English request word. Not a loan's terms, times of day, a list of years, or a
    sentence about people ("my brother is 30").
    """
    if (
        len(text) > _MAX_CHARS
        or any(mark in text for mark in _QUESTION_MARKS)
        or _ASKS.search(text)
    ):
        return None
    items = [item for item in _ITEMS.split(text) if item.strip()]
    values = [read for item in items if (read := _pair(item)) is not None]
    if len(values) < _MIN_PAIRS or len(values) < len(items) - 1:
        return None
    # The one item that is not a value is a title; one with a number ("transport 100 for 2
    # people") would leave its value out of the highest and lowest.
    if len(values) < len(items) and any(
        _pair(item) is None and _DIGIT.search(item) for item in items
    ):
        return None
    units = {value.unit.lower() for value in values if value.unit}
    if len(units) > 1 or units & _CLOCK_UNITS:
        return None
    if sum(value.label.lower() in _MONEY_TERMS for value in values) >= 2:
        return None
    # "Born 1990, married 2015, moved 2020" are dates, not amounts to compare.
    if all(_YEAR.fullmatch(value.written) for value in values):
        return None
    return values


def _named(values: list[SharedValue], end: float) -> str:
    """'Aug (290 mm)': the labels at that end, and its value with the series' unit."""
    at_end = [value for value in values if value.value == end]
    unit = next((value.unit for value in values if value.unit), "")
    shown = f"{at_end[0].written} {unit}" if unit and unit != "%" else at_end[0].written + unit
    return " and ".join(value.label for value in at_end) + f" ({shown})"


def shared_numbers_hint(text: str | None) -> str | None:
    """The note for a message that lists values, with their highest and lowest.

    Not for a personal disclosure ("My expenses: rent $1,500, …"): its own note says how
    to acknowledge it, and stays the one nearest the user's turn.
    """
    if not text or (is_personal_disclosure_turn(text) and not is_standing_preference(text)):
        return None
    try:
        values = shared_numbers(text)
    # It runs on every turn's prompt: a message it misreads gets no note, never an error.
    except Exception:
        return None
    if values is None:
        return None
    numbers = [value.value for value in values]
    return (
        f"{SHARED_NUMBERS_HINT} Read from their message: the highest is "
        f"{_named(values, max(numbers))} and the lowest is {_named(values, min(numbers))}."
    )
