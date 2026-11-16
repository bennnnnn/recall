"""A tangent or a normal to a curve at a point, and a line written as y = mx + c.

The solver's tangent card (``tools.school.curve_points``) and a graph's tangent and normal
(``drawing.plot_marks``) work the line out here, and both write it in the order a textbook
does: the x term first, then the constant, with no 1x and no + 0.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def _same(value: Any) -> Any:
    return value


def touching_line(
    x1: Any, y1: Any, slope: Any, normal: bool, tidy: Callable[[Any], Any] = _same
) -> tuple[Any | None, Any]:
    """The line through (x1, y1) with the tangent's ``slope``, or perpendicular to it: its
    slope and constant, each ``tidy``'d; (None, x1) for a normal that is vertical (the
    tangent is flat)."""
    if normal:
        if slope == 0:
            return None, x1
        slope = tidy(-1 / slope)
    return slope, tidy(y1 - slope * x1)


def slope_intercept(
    slope: Any,
    intercept: Any,
    term: Callable[[Any], str],
    number: Callable[[Any], str],
    minus: str = "-",
) -> str:
    """``y = mx + c`` in that order: ``term`` writes the x term for a slope, ``number`` a
    constant, ``minus`` the sign before a negative one."""
    if slope == 0:
        return f"y = {number(intercept)}"
    if intercept == 0:
        return f"y = {term(slope)}"
    sign = minus if intercept.is_negative else "+"
    return f"y = {term(slope)} {sign} {number(abs(intercept))}"
