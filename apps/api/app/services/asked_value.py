"""The value a reply gives for the quantity its card answers.

A card answers one quantity: an area, a perimeter, a height, a molar mass. A reply states
others beside it: the givens ("With r = 6 cm, the perimeter is 21.42 cm", "from y = 0 m the
ball rises to h ≈ 20.4 m", "Using C = 12.01 g/mol, M = 44.01 g/mol") and the quantities on
the way ("The quadrant is 154 cm², so the shape's area is 462 cm²"). Reading the first or
the last value of an Answer took a given for the answer and kept a card the reply's own
area contradicted (2026-11-13). This reads the value written against the asked quantity's
symbol or name, in the Answer section, or in the working when there is none; when nothing
names it, ``stated_verdict`` reads the Answer as before.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.services.answer_check import (
    VALUE_SEPARATORS,
    Number,
    Verdict,
    answer_sections,
    match_values,
    read_value,
    read_verified_value,
    sentences,
    statement_text,
)

# Each geometry quantity's symbol and the words a reply names it by.
QUANTITY_NAMES: dict[str, tuple[str, ...]] = {
    "area": ("A", "area"),
    "perimeter": ("P", "perimeter"),
    "circumference": ("C", "circumference"),
    "arc_length": ("L", "arc length", "arc", "curved edge"),
    "diameter": ("d", "diameter"),
    "diagonal": ("d", "diagonal"),
    "hypotenuse": ("c", "hypotenuse"),
    "volume": ("V", "volume"),
    "surface_area": ("S", "SA", "surface area"),
}
_RELATION = re.compile(r"=|\u2248")
# A clause ends at a stop, a semicolon, a bracket or a comma before words ("50.24 cm², about
# 50 cm²", "25π/2 cm² (with r = 5)").
_CLAUSE_END = re.compile(r"[.!?;](?=\s|$)|,\s+(?=[A-Za-z])|\(")


def _pattern(asked: str) -> re.Pattern[str]:
    """A symbol before = or ≈ ("A ≈", "h_{max} =", "\\lambda ="), or a name a few words
    before its value ("the semicircle's area is", "the area left is")."""
    if asked.startswith("\\") or (" " not in asked and len(asked) <= 2):
        symbol, subscript = re.escape(asked), r"(?:_\{?[^\s=]*\}?)?"
        return re.compile(
            rf"(?<![A-Za-z0-9_]){symbol}(?![A-Za-z]){subscript}\s*(?:{_RELATION.pattern})"
        )
    words = r"(?:\s+[a-z']+){0,5}?"
    return re.compile(
        rf"\b{re.escape(asked)}{words}\s*(?:{_RELATION.pattern}|\bis\b|\bequals\b)", re.I
    )


def _values_after(sentence: str, patterns: Sequence[re.Pattern[str]]) -> list[Number]:
    found: list[Number] = []
    for pattern in patterns:
        for match in pattern.finditer(sentence):
            clause = _CLAUSE_END.split(sentence[match.end() :], maxsplit=1)[0]
            value = VALUE_SEPARATORS.split(_RELATION.split(clause)[-1], maxsplit=1)[0]
            found.extend(read_value(value) or [])
    return found


def _named(text: str, patterns: Sequence[re.Pattern[str]], *, first: bool) -> list[Number]:
    """The values of the first (an Answer's) or last (the working's) sentence that names
    the asked quantity: "v ≈ 19.8 m/s" is the Answer, "the ball starts at v = 0" after it is
    not."""
    named = [values for values in (_values_after(s, patterns) for s in sentences(text)) if values]
    return (named[0] if first else named[-1]) if named else []


def asked_verdict(prose: str, answer_body: str, asked: Sequence[str]) -> Verdict | None:
    """How the reply's value for the asked quantity relates to the card; None when the
    reply names the quantity nowhere it states a value."""
    verified = read_verified_value(answer_body)
    if verified is None or not asked:
        return None
    patterns = [_pattern(name) for name in asked]
    body, region = answer_sections(prose)
    if region is not None:
        values = _named(statement_text(region), patterns, first=True)
    else:
        values = _named(statement_text(body), patterns, first=False)
    if not values:
        return None
    grade = match_values(values, verified.numbers)
    if grade == "incomparable":
        return "absent"
    return "conflict" if grade == "different" else grade
