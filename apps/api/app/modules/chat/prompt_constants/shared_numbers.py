"""A message that only shares numbers: "Monthly rainfall in Addis Ababa: Jan 15, Feb 30, …".

Qwen3.7 Flash, the free plan's everyday model, answered that message "Hey bini! How's it
going?" four times in four (2026-10-24): a list that asks nothing read to it as an opener.
Told what the message is, it answered about the numbers, but named November (6 mm) the
driest month once in five and summed the year wrong when asked for a total. So the highest
and lowest are read here, from the message, and the reply only words them.

A message that asks anything (a question mark, a request word) is the other rules' to
answer: a miss costs a plainer reply, a false hit tells the model a request asks nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# "Jan 15", "rent: 1,200", "Q1 10k", "Dec 5 mm", "savings = $300", "2024 7%".
_PAIR = re.compile(
    r"(?P<label>[^\W\d_][\w .&'/()-]{0,40}?|(?:19|20)\d\d)\s*[:=]?\s*"
    r"(?P<number>[-+]?[$€£]?\d{1,12}(?:,\d{3})*(?:\.\d+)?)\s*(?P<unit>%|[^\W\d_]{1,8}\.?)?"
)
# Items: a comma that is not a thousands separator, a semicolon, a line, a closing "and".
_ITEMS = re.compile(r",(?!\d{3}(?!\d))|;|\n|\s+and\s+")
_ASKS = re.compile(
    r"\b(?:make|plot|graph|chart|draw|show|calculate|compute|work\s+out|find|add|sum|total|"
    r"average|mean|sort|rank|compare|convert|remind|remember|forget|save|put|give|tell|explain|"
    r"analy[sz]e|help|can|could|would|should|please|pls|what|how|why|which|when|where|who)\b",
    re.IGNORECASE,
)
# "My brother is 30": a sentence, not a label.
_CLAUSE = re.compile(r"(?:^|\s)(?:is|are|was|were|am|i'?m|have|has|had|got)$", re.IGNORECASE)
# "10k" beside "900": compared as 10,000. "m" and "b" stay units (metres, bytes).
_SCALE = {"k": 1e3, "thousand": 1e3, "million": 1e6, "mn": 1e6, "bn": 1e9, "billion": 1e9}
SHARED_NUMBERS_HINT = (
    "The user's message only shares numbers and asks nothing. It is not a greeting: do not "
    "greet them or ask how they are. Reply about what they shared in one or two short sentences."
)
_YEAR = re.compile(r"(?:19|20)\d\d")
_MAX_CHARS = 2000
_MIN_PAIRS = 3


@dataclass(frozen=True)
class SharedValue:
    label: str
    value: float  # for comparing, "10k" as 10,000
    written: str  # the number as the user wrote it: "1,200", "$300", "10k"
    unit: str  # "mm", "%", or "" (one item may carry the unit for all: "Nov 6, Dec 5 mm")


def _pair(item: str) -> SharedValue | None:
    """One "label number unit" item, or the item after a title's colon ("…: Jan 15")."""
    text = item.strip().rstrip(".")
    for candidate in (text, text.rpartition(":")[2].strip()):
        match = _PAIR.fullmatch(candidate)
        if match is None or _CLAUSE.search(match["label"].strip()):
            continue
        unit = (match["unit"] or "").rstrip(".")
        label, number = match["label"].strip(), match["number"]
        value = float(number.lstrip("+$€£").replace(",", ""))
        if unit.lower() in _SCALE:
            return SharedValue(label, value * _SCALE[unit.lower()], number + unit, "")
        return SharedValue(label, value, number, unit)
    return None


def shared_numbers(text: str) -> list[SharedValue] | None:
    """The values a message that only shares them lists, in order, or None.

    Three or more, in one unit (an item may leave it off: "Nov 6, Dec 5 mm"), every item
    but one a value (a title line may stand alone), and nothing asked.
    """
    if len(text) > _MAX_CHARS or "?" in text or _ASKS.search(text):
        return None
    items = [item for item in _ITEMS.split(text) if item.strip()]
    values = [read for item in items if (read := _pair(item)) is not None]
    if len(values) < _MIN_PAIRS or len(values) < len(items) - 1:
        return None
    if len({value.unit.lower() for value in values if value.unit}) > 1:
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
    """The note for a message that only shares numbers, with their highest and lowest."""
    values = shared_numbers(text or "")
    if values is None:
        return None
    numbers = [value.value for value in values]
    return (
        f"{SHARED_NUMBERS_HINT} Its highest is {_named(values, max(numbers))} and its lowest is "
        f"{_named(values, min(numbers))}, read from their message: use these, and add up, "
        "average or compute nothing else. Then offer one next step that fits, such as a chart."
    )
