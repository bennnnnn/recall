"""Whether a solid the figure read names is the solid a written curve turns into.

A question that revolves a region bounded by a curve it writes ("x = √y about the y-axis")
makes the solid that curve sweeps: a cylinder only from a curve at one distance from the
axis, a cone from a line through it, a frustum from another line, a sphere or a hemisphere
from a circle's arc about a centre on the axis. The axis may be any line y = c or x = c:
each distance is measured from it. u5-083's x = √y about the y-axis was drawn as a
cylinder of height 4; it is a paraboloid, which no figure here draws, so none is drawn.
A question that writes no curve ("a sphere of radius r") is left to the figure's own checks.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from sympy import FiniteSet, S, Symbol, degree, expand, simplify, solveset

from app.modules.math.drawing.plot_question import Written, read_plot_question
from app.modules.math.drawing.plot_reading import plain, same_number
from app.modules.math.drawing.plot_x import named_values, revolution_axis

_X, _Y = Symbol("x"), Symbol("y")
_SOLIDS = frozenset({"cylinder", "cone", "frustum", "sphere", "hemisphere"})
# "about the x-axis", "around the line y = -1": the axis named as what the region turns
# about, not as one of its edges.
_ABOUT_AXIS = re.compile(
    r"\b(?:about|around)\s+(?:the\s+)?(?:[xy][-\s]?axis\b|(?:line\s+)?[xy]\s?=\s?[-+]?[\w./]+)",
    re.IGNORECASE,
)


def _distance_and_run(written: Written, axis: tuple[str, Any]) -> tuple[Any, Symbol] | None:
    """A curve or level line the question names as its distance from the axis line, in
    terms of the run along it: y = f(x) (or f(x) = …, or y = 3) about a line y = c, x = g(y)
    about a line x = c; None for one written the other way ("x = 3" ends a region turned
    about the x-axis), or in another letter."""
    letter, at = axis
    if letter == "y" and written.defines and written.name != "x":
        run = _X
    elif letter == "x" and written.name == "x":
        run = _Y
    else:
        return None
    if not written.expr.free_symbols <= {run}:
        return None
    return written.expr - at, run


def _sweeps(shape: str, distance: Any, run: Symbol, ends: Sequence[Any]) -> bool:
    """The solid ``distance`` (a function of ``run``) sweeps out is ``shape``; ``ends``,
    the values of the run the region ends at, tell a cone (the line meets the axis at one)
    from a frustum (it meets it at none)."""
    if shape == "cylinder":
        return bool(distance.is_number) and distance != 0
    if shape in {"cone", "frustum"}:
        if distance.is_number or not distance.is_polynomial(run) or degree(distance, run) != 1:
            return False
        meets = -distance.subs(run, 0) / distance.diff(run)
        if not ends:
            return True  # where the region ends is not said: either may be meant
        at_an_end = any(same_number(meets, end) for end in ends)
        return bool(at_an_end if shape == "cone" else not at_an_end)
    if shape in {"sphere", "hemisphere"}:
        # An arc of a circle whose centre is on the axis: d² + (run - c)² = R², so d² + run²
        # is a line in the run (the semicircle y = √(4 - (x - 2)²) about the x-axis too).
        swept = expand(simplify(distance**2) + run**2)
        return bool(swept.is_polynomial(run) and degree(swept, run) <= 1)
    return True


def _axis_bounds(text: str, axis: tuple[str, Any]) -> bool:
    """The region's own edges include the axis it turns about: "bounded by y = 2x, y = 0
    and x = 3 ... about the x-axis", or the axis named again outside "about the x-axis"."""
    letter, at = axis
    rest = _ABOUT_AXIS.sub(" ", text)
    if at == 0 and re.search(rf"\b{'x' if letter == 'y' else 'y'}-axis\b", rest, re.IGNORECASE):
        return True
    lines, _points = named_values(rest, letter, frozenset({"x", "y"}))
    return any(same_number(line, at) for line in lines)


def revolves_into(shape: str, texts: Sequence[str]) -> bool:
    """``shape`` is the solid the question's own curve sweeps about its axis, when the
    question revolves a region bounded by curves it names. A region between two of them
    (neither the axis) sweeps a hollow solid, which no plain solid is: a washer between
    y = x and y = x² is no cone, nor is one between y = 2x and y = x. When the axis is one
    of the region's edges, the curve's meeting with it ends the region too: y = 2x, y = 0
    and x = 3 about the x-axis is a cone. True when the question names no curve."""
    if shape not in _SOLIDS or not texts:
        return True
    text = plain(texts[0])
    axis = revolution_axis(text)
    if axis is None:
        return True
    question = read_plot_question(texts)
    found: dict[str, tuple[Any, Symbol]] = {}
    for written in question.formulas:
        swept = _distance_and_run(written, axis)
        if swept is not None and swept[0] != 0:
            found.setdefault(str(simplify(swept[0])), swept)
    if not found:
        return True
    if len(found) > 1:
        return False  # hollow: a washer, never a cone, cylinder or sphere
    distance, run = next(iter(found.values()))
    # The region's ends as the question writes them ("from y = 0 to y = 4" too).
    ends = list(question.x_values)
    if len(set(ends)) < 2 and _axis_bounds(text, axis) and not distance.is_number:
        # One end stated: the curve's meeting with the axis edge is the other.
        roots = solveset(distance, run, domain=S.Reals)
        ends += list(roots) if isinstance(roots, FiniteSet) else []
    return _sweeps(shape, distance, run, ends)
