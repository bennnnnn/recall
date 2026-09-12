"""Whole-request guards for already verified rectangle measurements."""

from __future__ import annotations

import math
import re

from app.services.math_text_match.units import solid_length_unit, strip_geometry_length_units
from app.services.math_tools.block.common import VerifiedMathBlock

_DECIMAL = r"(?:[0-9]{1,12}(?:\.[0-9]{1,12})?|\.[0-9]{1,12})"
_DIMENSIONS = re.compile(rf"({_DECIMAL})\s*(?:by|x|\u00d7|\*)\s*({_DECIMAL})")


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) else None


def can_direct_rectangle(
    verified: VerifiedMathBlock, user_text: str, fences: list[dict[str, object]]
) -> bool:
    """Every requested dimension, unit and quantity must match the one diagram.

    This intentionally recognizes a small complete phrase, not extra glue words
    in the generic direct-answer matcher. Extra operations, shapes, teaching,
    malformed dimensions and unit changes retain the model path.
    """
    if len(user_text) > 1000 or len(fences) != 1 or fences[0].get("type") != "rectangle":
        return False
    request = " ".join(user_text.lower().split()).rstrip(".?")
    if request.startswith("please "):
        request = request[7:]
    for prefix in ("find ", "calculate ", "compute ", "determine ", "what is ", "what's "):
        if request.startswith(prefix):
            request = request[len(prefix) :]
            break
    if request.startswith("the "):
        request = request[4:]
    quantity, separator, request = request.partition(" of ")
    if not separator or quantity not in {"area", "perimeter", "diagonal"}:
        return False
    for article in ("a ", "the "):
        if request.startswith(article):
            request = request[len(article) :]
            break
    if not request.startswith("rectangle "):
        return False
    dimensions = request[10:]
    unit = solid_length_unit(dimensions)
    if unit is None:
        return False
    pair = _DIMENSIONS.fullmatch(strip_geometry_length_units(dimensions).strip())
    if pair is None:
        return False
    width, height = (float(value) for value in pair.groups())
    if not (0 < width <= 1_000_000 and 0 < height <= 1_000_000):
        return False
    geometry = fences[0]
    if (
        _finite_number(geometry.get("width")) != width
        or _finite_number(geometry.get("height")) != height
        or geometry.get("unit") != unit
        or geometry.get("show_angle") is not False
    ):
        return False
    for flag in ("area", "perimeter", "diagonal"):
        if geometry.get(f"show_{flag}") is not (flag == quantity):
            return False
    value = _finite_number(geometry.get(quantity))
    answer = (verified.canonical_answer or "").strip()
    if value is None or value <= 0 or not answer or len(answer) > 64:
        return False
    try:
        return float(answer) == value
    except ValueError:
        return False
