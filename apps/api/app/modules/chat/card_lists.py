# ruff: noqa: RUF001 -- the module reads î, ĵ and k̂ as a card writes them.
"""A card that is a list of values: each piece a number standing as a value, never maths.

"(-9.043478260869565 î + 8.695652173913043 ĵ) m/s, 12.546951… m/s, 43.9° north of west"
held a vector's two components, its size and its direction, and no reading of one value took
it, so the card kept the model's sixteen digits (owner, 2026-11-25). Such a card's numbers
are each written by the rule (``card_numbers``). A piece that is maths, a symbol times a
number or a power ("2x + 3", "x^2"), is no list of values: the card is left as written.
"""

from __future__ import annotations

import re

from app.services.answer_check import plain_text

# A unit vector, a bracket round a vector, and what separates the card's values.
_UNIT_VECTOR = re.compile(r"\\hat\s*\{?\s*[ijk]\s*\}?|[îĵ]|k\u0302")
_BRACKETS = re.compile(r"\\left|\\right|[()\[\]]")
_SEPARATORS = re.compile(r",|;|\bor\b|\band\b")
# One value: a number, or a vector's signed components, then its unit or words ("north of
# west"), with no sign, power or bracket among them.
_VALUE = re.compile(
    r"[-+±−]?\s*\d+(?:\.\d+)?(?:\s*[-+−]\s*\d+(?:\.\d+)?)*"
    r"(?:\s*[A-Za-zµμΩ°%/·²³⁻¹]+(?:\s+[A-Za-z°]+)*)?"
)


def listed_values(value: str) -> bool:
    """``value`` is a list of values, each a number or a vector's components, at least one
    of them a vector or a second value."""
    text = _BRACKETS.sub(" ", plain_text(_UNIT_VECTOR.sub(" ", value)))
    pieces = [piece.strip() for piece in _SEPARATORS.split(text) if piece.strip()]
    if not pieces or not all(_VALUE.fullmatch(piece) for piece in pieces):
        return False
    return len(pieces) > 1 or _UNIT_VECTOR.search(value) is not None
