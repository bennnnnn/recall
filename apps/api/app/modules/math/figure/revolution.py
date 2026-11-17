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

from sympy import FiniteSet, S, Symbol, degree, expand, simplify, solve, solveset

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


# A curve the check cannot turn into one distance from the axis (y = x² about the y-axis:
# x = ±√y): the solid is not checked, so not drawn.
_UNCHECKED = "unchecked"


def _distance_and_run(written: Written, axis: tuple[str, Any]) -> tuple[Any, Symbol] | str | None:
    """A curve or level line the question names as its distance from the axis line, in
    terms of the run along it: about a line y = c, y = f(x) (or f(x) = …, or y = 3) as it is
    and x = g(y) turned round to y = f(x); about a line x = c, x = g(y) as it is and
    y = f(x) turned round. A line across the axis ("x = 3" about the x-axis) ends the region:
    None. One that cannot be turned round to a single curve: ``_UNCHECKED``. One in other
    letters ("y = rx/h"): None, as no number of it can be checked."""
    letter, at = axis
    run = _X if letter == "y" else _Y
    if written.name == "x":
        own = _Y  # x = g(y)
    elif written.defines:
        own = _X  # y = f(x), f(x) = …
    else:
        return None
    expr = written.expr
    if not expr.free_symbols <= {own}:
        return None
    if own != run:  # a level line across the axis, or a curve to turn round
        if expr.is_number:
            return None
        # y = f(x) as x = g(y), or the other way: the curve's own letter in the run's.
        try:
            branches = [b for b in solve(expr - run, own) if b.free_symbols <= {run}]
        except (NotImplementedError, ValueError, TypeError):
            return _UNCHECKED
        if len(branches) != 1:
            return _UNCHECKED
        expr = branches[0]
    return expr - at, run


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
            return False  # where the region ends is not said: neither can be checked
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


def _ends(text: str, question: Any, axis: tuple[str, Any], run: Symbol) -> list[Any]:
    """The values of the run the question bounds the region at, along the run's own
    letter: x = 3 and "from x = 0 to x = 2" about a line y = c; y = 0, y = 2 and "from
    y = 0 to y = 4" about a line x = c (a y-axis region read with x's ends was a cone)."""
    if run == _X:
        # Its lines, intervals of x, points and coordinates: "from (0, 0) to (3, 6)".
        return list(question.x_values)
    stated = [i for i in question.intervals if i.of == "y"]
    rest = _ABOUT_AXIS.sub(" ", text)
    lines, _points = named_values(rest, "y", frozenset({"x", "y"}))
    if re.search(r"\bx-axis\b", rest, re.IGNORECASE):
        lines.append(0)
    return [*lines, *(end for i in stated for end in (i.low, i.high))]


def revolves_into(shape: str, texts: Sequence[str]) -> bool:
    """``shape`` is the solid the question's own curve sweeps about its axis, when the
    question revolves a region bounded by curves it names. A region between two of them
    (neither the axis) sweeps a hollow solid, which no plain solid is: a washer between
    y = x and y = x² is no cone, nor is one between y = 2x and y = x. When the axis is one
    of the region's edges, the curve's meeting with it ends the region too: y = 2x, y = 0
    and x = 3 about the x-axis is a cone. A curve it cannot check (y = x² about the y-axis)
    draws no solid. True when the question names no curve."""
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
        if swept == _UNCHECKED:
            return False
        if isinstance(swept, tuple) and swept[0] != 0:
            found.setdefault(str(simplify(swept[0])), swept)
    if not found:
        return True
    if len(found) > 1:
        return False  # hollow: a washer, never a cone, cylinder or sphere
    distance, run = next(iter(found.values()))
    ends = _ends(text, question, axis, run)
    if len(set(ends)) < 2 and _axis_bounds(text, axis) and not distance.is_number:
        # One end stated: the curve's meeting with the axis edge is the other.
        roots = solveset(distance, run, domain=S.Reals)
        ends += list(roots) if isinstance(roots, FiniteSet) else []
    return _sweeps(shape, distance, run, ends)
