"""Every label and value in a chart's reading is the user's own, paired as they paired them.

The read copies; it never works anything out. A chart is drawn only when each category it
names is written in the user's message, each number is a number written there, and each
number belongs to its category the way the message writes it: all "Jan 10, Feb 12" (the
number after its label) or all "10 in Jan, 12 in Feb" (the number before it), never a mix,
never one number twice. A histogram's values are the whole run of numbers the user listed,
in order, none left out and none added. Anything else draws nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.charts.request import ChartRequest

# A number as people type one in data: "1,200", "-3.5", "45%", "$12".
_NUMBER = re.compile(
    r"(?<![\w.])(?P<minus>-|\u2212)?\$?(?P<digits>\d{1,3}(?:,\d{3})+|\d+)"
    r"(?P<frac>\.\d+)?%?(?![\w])"
)
# What may stand between the numbers of a histogram's list.
_LIST_GAP = re.compile(r"^(?:\s*[,;/|]\s*|\s+|\s*,?\s*and\s+)$", re.IGNORECASE)
# What counts as a label's own spelling: case and runs of spaces aside.
_SPACES = re.compile(r"\s+")


@dataclass(frozen=True)
class _Number:
    start: int
    end: int
    value: float


def number_value(text: str) -> float | None:
    """A value as written ("1,200", "45%", "-3.5"), or None when it is not one number."""
    match = _NUMBER.fullmatch(text.strip())
    if match is None:
        return None
    return _value(match)


def _value(match: re.Match[str]) -> float:
    number = float(match.group("digits").replace(",", "") + (match.group("frac") or ""))
    return -number if match.group("minus") else number


def _numbers(text: str) -> list[_Number]:
    return [_Number(m.start(), m.end(), _value(m)) for m in _NUMBER.finditer(text)]


def _occurrences(text: str, label: str) -> list[tuple[int, int]]:
    """Where the label is written, as a whole word or phrase, case aside."""
    words = [re.escape(word) for word in label.split()]
    if not words:
        return []
    pattern = re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", re.IGNORECASE)
    return [(m.start(), m.end()) for m in pattern.finditer(text)]


def grounded_points(request: ChartRequest, text: str) -> list[tuple[str, float]] | None:
    """The chart's (label, value) pairs when every one is the user's, else None."""
    points = request.points
    labels = [_SPACES.sub(" ", point.label).strip() for point in points]
    values = [number_value(point.value) for point in points]
    if len(points) < 2 or any(v is None for v in values) or not all(labels):
        return None
    if len({label.lower() for label in labels}) != len(labels):
        return None
    spans = {label: _occurrences(text, label) for label in labels}
    if any(not found for found in spans.values()):
        return None
    # A number inside a label ("2019", "Q1") is the label's, not a value.
    taken = [span for found in spans.values() for span in found]
    numbers = [n for n in _numbers(text) if not any(s <= n.start < e for s, e in taken)]
    for after in (True, False):
        paired = _pair(labels, values, spans, numbers, after=after)
        if paired is not None:
            return paired
    return None


def _pair(
    labels: list[str],
    values: list[float | None],
    spans: dict[str, list[tuple[int, int]]],
    numbers: list[_Number],
    *,
    after: bool,
) -> list[tuple[str, float]] | None:
    """Each label with the number written next to it on one side, every pair agreeing with
    the reading, no number used twice; None when any does not."""
    edges = sorted(edge for found in spans.values() for span in found for edge in span)
    used: set[int] = set()
    pairs: list[tuple[str, float]] = []
    for label, value in zip(labels, values, strict=True):
        match = None
        for start, end in spans[label]:
            neighbour = _neighbour(numbers, edges, start, end, after=after)
            if neighbour is not None and neighbour.value == value and neighbour.start not in used:
                match = neighbour
                break
        if match is None or value is None:
            return None
        used.add(match.start)
        pairs.append((label, value))
    return pairs


def _neighbour(
    numbers: list[_Number], edges: list[int], start: int, end: int, *, after: bool
) -> _Number | None:
    """The first number after the label (or the last before it), with no other label
    between them."""
    if after:
        found = next((n for n in numbers if n.start >= end), None)
        if found is None or any(end < edge <= found.start for edge in edges):
            return None
        return found
    found = next((n for n in reversed(numbers) if n.end <= start), None)
    if found is None or any(found.end <= edge < start for edge in edges):
        return None
    return found


def grounded_values(request: ChartRequest, text: str) -> list[float] | None:
    """A histogram's values when they are exactly a list of numbers the user wrote: the
    whole list, in order. A value missing or added draws a wrong histogram, so none."""
    values = [number_value(value) for value in request.values]
    if len(values) < 5 or any(v is None for v in values):
        return None
    numbers = _numbers(text)
    for run in _runs(text, numbers):
        if [n.value for n in run] == values:
            return [n.value for n in run]
    return None


def _runs(text: str, numbers: list[_Number]) -> list[list[_Number]]:
    """The lists of numbers the text writes: numbers with only commas, spaces or "and"
    between them."""
    runs: list[list[_Number]] = []
    for number in numbers:
        if runs and _LIST_GAP.match(text[runs[-1][-1].end : number.start]):
            runs[-1].append(number)
        else:
            runs.append([number])
    return runs


def grounded_title(name: str, text: str) -> str | None:
    """An axis title the user wrote ("sales", "month"), else None: the axis goes untitled."""
    cleaned = _SPACES.sub(" ", name).strip()
    return cleaned if cleaned and _occurrences(text, cleaned) else None
