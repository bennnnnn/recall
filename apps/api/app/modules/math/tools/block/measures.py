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
from app.services.question_parts import labelled_parts
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
# How a card names each value it holds: a measure's symbol, the gcd's and lcm's commands.
_CARD_NAME = {
    **{quantity: symbol for quantity, (symbol, _power) in _SYMBOLS.items()},
    "gcd": r"\gcd",
    "lcm": r"\operatorname{lcm}",
}
_CARD_PARTS = re.compile(r",\s*\\quad\s*")
# Where a card part's name ends: its first "=", "≈" or "\\approx".
_PART_SEPARATOR = re.compile(r"=|\\approx|\u2248")
_ARGUMENTS = re.compile(r"\([^()]*\)$")


def _names_every(card: str, asked: Sequence[str]) -> bool:
    """``card`` holds one named value for each quantity asked: "A = 15 m², P = 16 m"."""
    heads = set()
    for part in _CARD_PARTS.split(card):
        head = _part_head(part)
        if head is not None:
            heads.add(_ARGUMENTS.sub("", head).strip())
    return len(heads) >= len(asked) and all(_CARD_NAME.get(name) in heads for name in asked)


def _part_head(part: str) -> str | None:
    """A card part's name: the text before its first separator with a name in front, on one
    line. Read in one pass; a pattern with spaces on both sides of a lazy name backtracked in
    cubic time on a long run of spaces (the CI regex gate)."""
    rest = part.lstrip()
    for separator in _PART_SEPARATOR.finditer(rest):
        head = rest[: separator.start()].rstrip()
        if "\n" in head:
            return None
        if head:
            return head
    return None


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
    if len(asked) < 2 or block.canonical_answer is None or labelled_parts(request) >= 2:
        # No card to complete: a drawing, measures angles alone cannot fix, or a question
        # in parts, whose every part gets its own card.
        return block
    if _several_shapes(request):
        # Each measure may be of another shape, with its own dimensions.
        return None
    picture = _picture(block)
    if not _operands_read(request, intent):
        # Each ask has its own operands ("the area of a circle with radius 3 and the
        # circumference of one with radius 5"): one reading answers neither.
        return None
    if _names_every(block.canonical_answer, asked):
        return block  # its own card already holds each, with its own working
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


# The shapes a question may name. "square" before a unit or "root" is no shape.
_SHAPE = (
    r"(?:circles?|semicircles?|sectors?|squares?(?!\s+(?:units?|roots?|cm|mm|m|km|in|ft|yd|"
    r"inch\w*|feet|foot|yards?|miles?|met\w*|centimet\w*|kilomet\w*|millimet\w*)\b)|"
    r"rectangles?|triangles?|trapezoids?|trapezi(?:a|ums?)|parallelograms?|rhomb(?:us|i)|"
    r"kites?|polygons?|"
    r"pentagons?|hexagons?|octagons?|ellipses?|spheres?|hemispheres?|cubes?|cuboids?|"
    r"cylinders?|cones?|prisms?|pyramids?)"
)
_SHAPE_NOUN = re.compile(rf"\b{_SHAPE}\b", re.IGNORECASE)
_PART = r"(?:base|face|end|cross[- ]?section)s?"
# A shape that is part of another, with its dimensions, is no second shape: "a sector of a
# circle", "a cylinder whose base is a circle"; nor one naming another's part or kind: "a
# pyramid with a square base", "a square-based pyramid", "a square prism".
_PART_OF_THE_LAST = re.compile(
    rf"(?:\b{_SHAPE}\s+of|\b{_PART}\s+(?:is|are))\s+(?:a|an|the)\s+(?:[a-z-]+\s+){{0,2}}$",
    re.IGNORECASE,
)
_NAMING_THE_NEXT = re.compile(rf"(?:\s+|-)(?:based\b|{_SHAPE}\b|{_PART}\b)", re.IGNORECASE)
# A shape the question brings in: "a circle", "an equilateral triangle", "a right cone".
_BROUGHT_IN = re.compile(r"\b(?:a|an)\s+(?:[a-z-]+\s+){0,2}$", re.IGNORECASE)


_PLURALS = {"rhombi": "rhombus", "trapezia": "trapezium"}


def _kind(noun: str) -> str:
    word = noun.lower()
    return _PLURALS.get(word) or (
        word[:-1] if word.endswith("s") and not word.endswith("us") else word
    )


def _several_shapes(text: str) -> bool:
    """The question brings in two shapes, or names two kinds, neither part of the other: its
    measures may each be of another, with its own dimensions, which one reading cannot tell
    apart ("the area of a circle with diameter 6 and the circumference of a circle with
    radius 6" carded A ≈ 113.1 for 28.27, 2026-11-14 review)."""
    shapes = [
        match
        for match in _SHAPE_NOUN.finditer(text)
        if not _PART_OF_THE_LAST.search(text, 0, match.start())
        and not _NAMING_THE_NEXT.match(text, match.end())
    ]
    brought_in = [match for match in shapes if _BROUGHT_IN.search(text, 0, match.start())]
    return len(brought_in) >= 2 or len({_kind(match.group(0)) for match in shapes}) >= 2


# A number as the question writes it: "3", "2.5", ".5".
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?|(?<![\w\d])\.\d+")


def _operands_read(text: str, intent: MathIntent) -> bool:
    """Every number the question writes is one its reading was given: a dimension or an
    operand the intent read from it, never a measure worked out from them. "The area of a
    circle of radius 2 and the circumference of a circle of radius 4" passed when 4 was
    held as the first circle's diameter, and carded C ≈ 12.57 for 25.13 (2026-11-14)."""
    given = intent.model_dump(exclude_defaults=True)
    held = _numbers_in(given)
    if intent.given_diameter and intent.radius:
        held.append(2 * intent.radius)  # a diameter given is read as its radius
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
