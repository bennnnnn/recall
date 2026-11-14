"""The value a question gives π: "use 3.14", "take π = 22/7", "(π ≈ 3.142)".

A school question that says which π to use expects its answer worked with that value:
"the area of the quarter circle of radius 8 cm (use 3.14)" is 50.24 cm², and a card
worked with π itself said 201.06 for the whole circle (2026-11-13). The statement was
read only when it named π, so "use 3.14" passed as no statement at all. A number the
question tells the student to use that lies within a hundredth of π is π's value, named
or not. A value π is set to that is not near it ("π = 3") is a statement this reader
cannot use, and the solvers that work with π decline it.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from fractions import Fraction

_PI = r"(?:\u03c0|\\pi\b|\bpi\b)"
# 3.14, .5, 22/7 or \frac{22}{7} as a keyboard writes it.
_VALUE = (
    r"(?:\\[dt]?frac\s*\{\s*(?P<tex_top>\d+)\s*\}\s*\{\s*(?P<tex_bottom>\d+)\s*\}"
    r"|(?P<top>\d+)\s*/\s*(?P<bottom>\d+)|(?P<decimal>\d*\.\d+|\d+))"
)
_SIGN = r"(?:=|\u2248|~|\\approx)"
# A few words link π to its value: "π being taken as", "π is approximated as", "π by".
_LINK = r"(?:\s+[a-z]+){0,3}?"
_VERB = r"(?:use|using|take|taking|with|where|let|if)"
# "take π = 22/7", "π ≈ 3.142", "(use π as 3.14)", "π being taken as 3.14": π, its value.
_NAMED = re.compile(
    rf"\(?\s*(?:\b{_VERB}\s+)?(?:the\s+value\s+of\s+)?{_PI}{_LINK}\s*{_SIGN}?\s*{_VALUE}\s*\)?",
    re.IGNORECASE,
)
# "let 3.14 be π", "3.142 for π": the value first.
_VALUE_FIRST = re.compile(rf"\(?\s*(?:\blet\s+)?{_VALUE}(?:\s+[a-z]+){{1,2}}\s+{_PI}\s*\)?", re.I)
# "use 3.14", "(use 22/7)", "taking 3.142 for π": an instruction with the value alone.
_TOLD = re.compile(
    rf"\(?\s*\b(?:use|using|take|taking)\s+(?:the\s+value\s+)?{_VALUE}"
    rf"(?:\s+(?:for|as)\s+(?:the\s+value\s+of\s+)?{_PI})?\s*\)?",
    re.IGNORECASE,
)
# π set to something the patterns above do not read: "use π" alone, "π = ?", "pi as a fraction".
_SET_UNREAD = re.compile(
    rf"{_PI}\s*(?:=|\u2248|as\b|to\s+be\b)|\b(?:use|using|take|taking)\s+{_PI}", re.IGNORECASE
)
# A value this close to π is π's (3.14, 3.142, 3.1416, 22/7, 355/113).
_NEAR_PI = 0.01


@dataclass(frozen=True)
class StatedPi:
    """π's value as the question gives it, and where the question says so.

    ``value`` is None when the question sets π to something no solver here uses.
    """

    value: Fraction | None
    start: int
    end: int


def _value(match: re.Match[str]) -> Fraction | None:
    groups = match.groupdict()
    if groups["tex_top"] is not None:
        top, bottom = groups["tex_top"], groups["tex_bottom"]
    elif groups["top"] is not None:
        top, bottom = groups["top"], groups["bottom"]
    else:
        return Fraction(groups["decimal"])
    return Fraction(int(top), int(bottom)) if int(bottom) else None


def _near_pi(value: Fraction | None) -> bool:
    return value is not None and abs(float(value) - math.pi) <= _NEAR_PI


def stated_pi(text: str) -> StatedPi | None:
    """The question's one statement of π's value, or None when it makes none."""
    found: list[StatedPi] = []
    for match in _NAMED.finditer(text):
        value = _value(match)
        found.append(StatedPi(value if _near_pi(value) else None, match.start(), match.end()))
    for match in (*_TOLD.finditer(text), *_VALUE_FIRST.finditer(text)):
        value = _value(match)
        overlaps = any(s.start < match.end() and match.start() < s.end for s in found)
        # "use 5 cm of string" tells no π; a value near π told to be used is π's.
        if _near_pi(value) and not overlaps:
            found.append(StatedPi(value, match.start(), match.end()))
    if not found:
        unread = _SET_UNREAD.search(text)
        return None if unread is None else StatedPi(None, unread.start(), unread.end())
    values = {statement.value for statement in found}
    first = min(found, key=lambda statement: statement.start)
    if len(values) > 1:
        # Two different values for π: neither is the question's one.
        return StatedPi(None, first.start, first.end)
    return first
