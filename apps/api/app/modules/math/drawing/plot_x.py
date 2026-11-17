"""What a question says of x (or y): its intervals, the lines it names, and the points it
asks about.

A region, rectangles, an average or a curve's domain stand on an interval the question says
of x ("[0, 3]", "from x = 0 to x = 2", "∫ from -π/2 to π/2", "0 ≤ x ≤ 2"), never on two
numbers said of something else ("check that your answer is between 2 and 3"). "x = 2" names
a line ("bounded by ... and x = 2", "the line x = 3") unless it is said of a point ("the
gradient at x = 3", "where y = 4"), which is where a tangent or a marked point may stand.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sympy import Rational

from app.modules.math.drawing.plot_reading import LOWER, UPPER, conditions, number, parts

_VALUE = r"[-+]?[\w./()*^]{1,12}"
# "[1, 2]" or "[-2, 2]": an interval the question writes.
BRACKETS = re.compile(r"\[\s*([^\[\],]{1,16}),\s*([^\[\],]{1,16})\]")
# An interval in words: "from -π/2 to π/2", "from x = 0 to x = 2", "between x = 1 and x = 2".
_FROM_TO = re.compile(
    rf"\b(?P<word>from|between)\s(?P<named>[a-z]\s?=\s?)?(?P<low>{_VALUE})\s(?:to|and)\s"
    rf"(?P<named_high>[a-z]\s?=\s?)?(?P<high>{_VALUE})"
)
# Words before "between A and B" that say it of a value, not of x: "is between 2 and 3".
# A region "lying between 1 and 3" lies between values of x.
_SAID_OF_A_VALUE = frozenset("is are answer result value estimate was".split())
# "x = ±1": a value and its negative.
_PLUS_MINUS = r"\u00b1\s?|\\pm\s?|\+/?-\s?"
# A list after "x =": "x = 1 and -2", "x = 1, 2 or 3".
_NUMBER_VALUE = r"[-+]?(?:\d|pi\b)[\w./()*^]{0,11}"
_LISTED = rf"\s?(?:,|\band\b|\bor\b)\s?(?:and\s)?{_NUMBER_VALUE}(?=[\s,.;)]|$)"
_LISTED_VALUE = re.compile(rf"(?:,|\band\b|\bor\b)\s?(?:and\s)?({_NUMBER_VALUE})")
# What joins two values said alike: "x = 1 and x = -2", "x = 1, x = 2".
_LIST_JOIN = re.compile(r"\s?(?:,|and|or|,\s?and)?\s?")
# After these words "x = 2" (or "y = 4") names a point, not a line.
_POINT_WORDS = frozenset("at when where whenever if for of point then".split())
_LINE_WORDS = frozenset("the line lines vertical horizontal".split())
_PIECE_WORDS = re.compile(r"\b(?:if|when|otherwise)\b")
_ABOUT = re.compile(r"\b(?:about|around)\s+", re.IGNORECASE)
_AXIS_LINE = re.compile(
    rf"\s*(?:the\s+)?(?:(?P<axis>[xy])[-\s]?axis\b|(?:line\s+)?(?P<name>[xy])\s?=\s?(?P<at>{_VALUE}))",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Interval:
    """An interval of x the question writes, with whether it holds each end."""

    low: Any
    high: Any
    low_closed: bool = True
    high_closed: bool = True
    # The letter it is said of when the question names it ("from y = 0 to y = 4": "y").
    of: str = ""

    def of_x(self, variables: frozenset[str]) -> bool:
        """Said of x: of no letter, or of the question's own variable (x, or t for v(t));
        "where u runs from u = 1 to u = 4" is of no curve's across."""
        return not self.of or self.of in variables


_BRACKET_LETTER = re.compile(r"(?<![A-Za-z])([a-z])\s*(?:\u2208|\bin\b|\bis\s+in\b)\s*$")


def _bracket_of(text: str, at: int) -> str:
    found = _BRACKET_LETTER.search(text[:at])
    return found.group(1) if found else ""


def _words_before(text: str, at: int) -> list[str]:
    return [w.strip(",;:().").lower() for w in text[:at].split()]


def intervals(text: str, variables: frozenset[str]) -> list[Interval]:
    """The intervals of x ``text`` writes: in brackets, in words, and as a double comparison
    in one clause ("0 ≤ x ≤ 2π", "-5 < x ≤ -2", its strictness kept)."""
    found: list[Interval] = []
    # A bracket is of the letter written right before it: "y ∈ [0, 4]", "for y in [0, 4]".
    pairs = [
        (m.group(1), m.group(2), _bracket_of(text, m.start())) for m in BRACKETS.finditer(text)
    ]
    for match in _FROM_TO.finditer(text):
        before = _words_before(text, match.start())[-3:]
        said_of_value = match.group("word") == "between" and not match.group("named")
        if said_of_value and _SAID_OF_A_VALUE & set(before):
            continue
        # The letter either end names: "from y = 0 to y = 4", "from 0 to y = 4".
        named = (match.group("named") or match.group("named_high") or "").strip(" =")
        pairs.append((match.group("low"), match.group("high"), named))
    for low, high, of in pairs:
        a, b = number(low), number(high)
        if a is not None and b is not None and a != b:
            a, b = (a, b) if float(a) < float(b) else (b, a)
            found.append(Interval(a, b, of=of))
    for part in parts(text):
        # Each letter's own comparisons, tagged with it: "0 ≤ y ≤ 4" of y (for x = √y, though
        # y is no letter of its formula), "0 ≤ t ≤ 5" of t, "0 ≤ x ≤ 3" of x.
        for letter in sorted(variables | {"y"}):
            sided = [c for c in conditions(part, frozenset({letter})) if c.value.is_number]
            lows = [c for c in sided if c.op in LOWER]
            highs = [c for c in sided if c.op in UPPER]
            if len(lows) != 1 or len(highs) != 1:
                continue
            low, high = lows[0], highs[0]
            if float(low.value) < float(high.value):
                # Of x when x is named ("0 ≤ x ≤ 3"): never read as y for x = g(y).
                of = letter
                closed = (low.op == ">=", high.op == "<=")
                found.append(Interval(low.value, high.value, *closed, of=of))
    return found


def named_values(text: str, letter: str, variables: frozenset[str]) -> tuple[list[Any], list[Any]]:
    """The values ``text`` gives ``letter`` (x, y, or the variable t a curve is written in),
    as lines it names and as points it is said of: "the lines x = -1/2 and x = 3" and
    "x ≥ 0" (outside a piece) and the y-axis are lines; "at x = 3", "where y = 4" are
    points, and so is each value listed after one ("where x = 1 and x = -2", "at x = 1, -2").
    """
    lines: list[Any] = []
    points: list[Any] = []
    said: list[Any] | None = None
    last = 0
    for match in re.finditer(rf"\b{letter}\s?=\s?({_PLUS_MINUS})?({_VALUE})((?:{_LISTED})*)", text):
        if text[match.start() - 1 : match.start()] in {"(", "'"}:
            continue  # f(x = ...) is no line
        values = [match.group(2), *re.findall(_LISTED_VALUE, match.group(3))]
        found = [v for v in (number(w.rstrip(")")) for w in values) if v is not None]
        if match.group(1):
            found += [-v for v in found]  # "x = ±1" is 1 and -1
        if not found:
            continue
        before = [w for w in _words_before(text, match.start()) if w not in _LINE_WORDS]
        if said is not None and _LIST_JOIN.fullmatch(text[last : match.start()]):
            kind = said  # "where x = 1 and x = -2": the second is said as the first
        else:
            kind = points if before and before[-1] in _POINT_WORDS else lines
        kind += found
        said, last = kind, match.end()
    if letter == "x":
        for part in parts(text):
            if _PIECE_WORDS.search(part.lower()):
                continue
            sided = [c for c in conditions(part, variables) if c.op in LOWER | UPPER]
            if len(sided) == 1 and sided[0].value.is_number:
                lines.append(sided[0].value)
        if "y-axis" in text.lower():
            lines.append(Rational(0))
    return lines, points


def axis_line(text: str) -> tuple[str, Any] | None:
    """The axis line ``text`` begins with: ("y", 0) for "the x-axis" or "y = 0", ("x", 0)
    for "the y-axis", ("y", -1) for "the line y = -1"."""
    found = _AXIS_LINE.match(text)
    if found is None:
        return None
    if found.group("axis"):
        return ("y" if found.group("axis").lower() == "x" else "x"), Rational(0)
    at = number(found.group("at").rstrip(")"))
    return None if at is None else (found.group("name").lower(), at)


def revolution_axis(text: str) -> tuple[str, Any] | None:
    """The axis a region turns about: the line named right after "about" or "around"."""
    for found in _ABOUT.finditer(text):
        axis = axis_line(text[found.end() :])
        if axis is not None:
            return axis
    return None
