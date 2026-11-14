"""A shape question that asks for several measures gets them all on one card, or no card.

"Find the circumference and area of a circle of radius 3" carried ≈ 18.85 alone, the area
left in the working; "the diameter and area" carried the area with a length's unit; a
triangle's "area and perimeter" carried the perimeter (2026-11-13 audit, MATH-04). Each
shape's block works one measure for its card, and the picture it draws holds them all, so
the card is written here from that picture's own values, each measure named, in the order
asked. A measure the picture does not hold leaves the turn with no card: a card that stands
for half the question is worse than none.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from app.modules.math.match.asked_quantities import asked_quantities
from app.modules.math.schemas import MathIntent
from app.modules.math.solve.geometry import format_geometry_decimal
from app.modules.math.tools.block.answer_text import format_quantity
from app.services.solving import VerifiedMathBlock

SHAPE_KINDS = frozenset(
    {
        "rectangle",
        "square",
        "triangle",
        "right_triangle",
        "circle",
        "triangle_sides",
        "trapezoid",
        "parallelogram",
        "sector",
    }
)
# Each measure's symbol, and the power its unit takes.
_SYMBOLS = {
    "area": ("A", 2),
    "perimeter": ("P", 1),
    "circumference": ("C", 1),
    "diameter": ("d", 1),
    "radius": ("r", 1),
    "diagonal": ("d", 1),
    "hypotenuse": ("c", 1),
    "arc_length": ("L", 1),
    "volume": ("V", 3),
    "surface_area": ("S", 2),
}
_POWERS = {1: "", 2: "²", 3: "³"}
# The kinds whose own block cards every value asked of it (both of a solid's measures, the
# gcd and the lcm), and how each value is named on that card.
_CARDED_BY_BLOCK = frozenset({"solid", "number_theory"})
_CARD_NAME = {"volume": "V", "surface_area": "S", "gcd": r"\gcd", "lcm": r"\operatorname{lcm}"}


# A circle's or sector's area, circumference and arc are multiples of π: never exact as a
# decimal, however few places the picture stores them to.
_OF_PI = {
    "circle": frozenset({"area", "circumference"}),
    "sector": frozenset({"area", "arc_length"}),
}


def measure_part(quantity: str, value: float, unit: str, *, rounded: bool = False) -> str:
    """``A \\approx 28.27\\ \\mathrm{units}^{2}``: one measure, its symbol and its unit."""
    symbol, power = _SYMBOLS[quantity]
    shown = format_geometry_decimal(value)
    exact = not rounded and math.isclose(float(shown), value, abs_tol=1e-9)
    relation = "=" if exact else r"\approx"
    return f"{symbol} {relation} {format_quantity(shown, f'{unit}{_POWERS[power]}')}"


def measures_card(
    parts: Sequence[tuple[str, float, str]], *, of_pi: frozenset[str] = frozenset()
) -> str:
    return r",\quad ".join(
        measure_part(quantity, value, unit, rounded=quantity in of_pi and value != 0)
        for quantity, value, unit in parts
    )


def with_every_measure(intent: MathIntent, block: VerifiedMathBlock) -> VerifiedMathBlock | None:
    """``block`` with a card holding every measure the question asks for; ``block`` as it
    is when it asks for one; None when the block's picture lacks one asked."""
    request = intent._request_text or ""
    asked = asked_quantities(request)
    if len(asked) < 2 or block.canonical_answer is None:
        # No card to complete: a drawing, or measures angles alone cannot fix.
        return block
    picture = _picture(block)
    if not _operands_read(request, intent, picture):
        # Each ask has its own operands ("the area of a circle with radius 3 and the
        # circumference of one with radius 5"): one reading answers neither.
        return None
    if intent.kind in _CARDED_BY_BLOCK:
        # These blocks card every value they read: one asked beyond them is not on it.
        named = {_CARD_NAME[quantity] for quantity in asked if quantity in _CARD_NAME}
        card = block.canonical_answer or ""
        whole = len(named) == len(asked) and all(
            f"{name} " in card or f"{name}(" in card for name in named
        )
        return block if whole else None
    if intent.kind not in SHAPE_KINDS or picture is None:
        # A reading that cards one measure stands for a question asking several of none.
        return None
    values = [picture.get(quantity) for quantity in asked]
    numbers = [float(value) for value in values if isinstance(value, int | float)]
    if len(numbers) != len(values):
        return None
    unit = str(picture.get("unit") or intent.unit)
    card = measures_card(
        [(quantity, number, unit) for quantity, number in zip(asked, numbers, strict=True)],
        of_pi=_OF_PI.get(intent.kind, frozenset()),
    )
    said = [line for line in block.text.split("\n") if not line.startswith("Verified result:")]
    return replace(
        block,
        text="\n".join([*said, f"Verified result: {card}"]),
        canonical_answer=card,
        display_answer=card,
        # The working a block writes is for its one measure: the model writes the rest
        # around the card, and each value is held to its own name (``fence_conflict``).
        allow_direct=False,
        direct_reply=None,
        worked_reply=None,
        asked=(),
    )


# A number as the question writes it: "3", "2.5", ".5".
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?|(?<![\w\d])\.\d+")


def _operands_read(text: str, intent: MathIntent, picture: dict[str, Any] | None) -> bool:
    """Every number the question writes is one its reading holds: a dimension of the shape
    it drew, or an operand of its intent."""
    held = [*_numbers_in(intent.model_dump()), *_numbers_in(picture or {})]
    return all(
        any(math.isclose(float(written), value, rel_tol=1e-6, abs_tol=1e-9) for value in held)
        for written in _NUMBER.findall(text)
    )


def _numbers_in(fields: Any) -> list[float]:
    if isinstance(fields, bool):
        return []
    if isinstance(fields, int | float):
        return [float(fields)]
    if isinstance(fields, str):
        try:
            return [float(fields)]
        except ValueError:
            return []
    if isinstance(fields, dict):
        return [number for value in fields.values() for number in _numbers_in(value)]
    if isinstance(fields, list | tuple):
        return [number for value in fields for number in _numbers_in(value)]
    return []


def _picture(block: VerifiedMathBlock) -> dict[str, Any] | None:
    fences = [block.canonical_fence, *block.canonical_fences]
    return next(
        (
            fence
            for fence in fences
            if isinstance(fence, dict) and fence.get("type") not in {None, "answer"}
        ),
        None,
    )
