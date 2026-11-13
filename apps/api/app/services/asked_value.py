"""The one value a reply's Answer gives for the quantity its card answers.

A card answers one quantity: an area, a perimeter, a height, a molar mass. A reply states
others beside it: the givens ("With r = 6 cm, the perimeter is 21.42 cm", "from y = 0 m the
ball rises to h ≈ 20.4 m", "Using C = 12.01 g/mol, M = 44.01 g/mol"), the whole of which the
asked part is a share ("A_{circle} = 201.06, so A_{quarter} = 50.27"), a second case ("for
1 mol, m = 58.44 g; for 0.5 mol, m = 29.22 g"). A card is held to a reply only where that
is unambiguous: the Answer section writes exactly one value against the asked quantity's
exact symbol (a subscript is part of it: A_{circle} is not A, v_i is not v) or its name.
Anything else, no Answer heading included, leaves the card as main's reading of the reply
leaves it (``stated_verdict``).

Built after the quarter circle's Answer, "A = 50.24 cm²", stood under a checked ≈ 201.06
(2026-11-13), and two reviews of the first nets that read the first or the last value.
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
    statement_text,
)
from app.services.answer_fence import answer_header_and_value
from app.services.glyphs import SUBSCRIPT_DIGITS

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
# A symbol and what it is set to: "A ≈", "h_{\max} =", "M_{\text{CO}_2} =", "M(CO2) =".
_SYMBOL = re.compile(
    r"(?<![A-Za-z0-9_\\])(?P<symbol>\\?[A-Za-z]+"
    r"(?:_\{(?:[^{}]|\{[^{}]*\})*\}|_[A-Za-z0-9]+|\([^()=]*\))?)\s*(?:=|\u2248)"
)
_WRAPPER = re.compile(r"\\(?:text|mathrm|operatorname|rm)\s*\{([^{}]*)\}")
# A clause ends at a stop, a semicolon, a bracket, a line's end or a comma before words.
_CLAUSE_END = re.compile(r"[.!?;](?=\s|$)|,\s+(?=[A-Za-z])|\(|\n")


def _plain(symbol: str) -> str:
    """``M_{\\text{CO}_2}``, ``M(CO₂)`` and ``MCO2`` are one symbol; ``A_{circle}`` is not A."""
    text = _WRAPPER.sub(r"\1", symbol).translate(SUBSCRIPT_DIGITS)
    return re.sub(r"[\\{}_()\s]", "", text)


def _value_after(text: str, start: int) -> list[Number]:
    """The value a relation sets, read to the end of its clause: the last of a chain
    ("A = 22/7 * 7² = 154"), never a value in the next clause."""
    clause = _CLAUSE_END.split(text[start:], maxsplit=1)[0]
    return read_value(VALUE_SEPARATORS.split(_RELATION.split(clause)[-1], maxsplit=1)[0]) or []


def _is_name(asked: str) -> bool:
    """ "area", "arc length": a name in words; "A", "pH", "h_{\\max}", "\\lambda" are symbols."""
    return len(asked) > 2 and asked.replace(" ", "").isalpha() and asked.islower()


def _candidates(answer: str, asked: Sequence[str]) -> list[Number]:
    symbols = {_plain(name) for name in asked if not _is_name(name)}
    found = [
        number
        for match in _SYMBOL.finditer(answer)
        if _plain(match.group("symbol")) in symbols
        for number in _value_after(answer, match.end())
    ]
    for name in filter(_is_name, asked):
        words = rf"\b{re.escape(name)}(?:\s+[a-z']+){{0,5}}?\s*(?:=|\u2248|\bis\b|\bequals\b)"
        for match in re.finditer(words, answer, re.IGNORECASE):
            found.extend(_value_after(answer, match.end()))
    return found


def _card_value(answer_body: str) -> str:
    """A rounded card's value: the decimal after ≈ (``16\\pi \\approx 50.27``)."""
    _headers, value = answer_header_and_value(answer_body)
    return value.rpartition("\\approx")[2] if "\\approx" in value else value


def asked_verdict(prose: str, answer_body: str, asked: Sequence[str]) -> Verdict | None:
    """How the one value the Answer section gives for the asked quantity relates to the
    card; None when it gives none, gives several, or the reply has no Answer heading."""
    verified = read_verified_value(_card_value(answer_body))
    _body, region = answer_sections(prose)
    if verified is None or not asked or region is None:
        return None
    candidates = _candidates(statement_text(region), asked)
    if len({number.value for number in candidates}) != 1:
        return None
    grade = match_values(candidates[:1], verified.numbers)
    if grade == "incomparable":
        return "absent"
    return "conflict" if grade == "different" else grade
