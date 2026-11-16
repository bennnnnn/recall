"""Whether a solid the figure read names is the solid a written curve turns into.

A question that revolves a region bounded by a curve it writes ("x = √y about the y-axis")
makes the solid that curve sweeps: a cylinder only from a curve at one distance from the
axis, a cone from a line through it, a frustum from another line, a sphere or a hemisphere
from a circle's arc about its centre. u5-083's x = √y about the y-axis was drawn as a
cylinder of height 4; it is a paraboloid, which no figure here draws, so none is drawn.
A question that writes no curve ("a sphere of radius r") is left to the figure's own checks.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sympy import Symbol, degree, simplify

from app.modules.math.drawing.plot_question import read_plot_question
from app.modules.math.drawing.plot_reading import plain, same_number
from app.modules.math.drawing.plot_x import revolution_axis

_X, _Y = Symbol("x"), Symbol("y")
_SOLIDS = frozenset({"cylinder", "cone", "frustum", "sphere", "hemisphere"})


def _distance_and_run(name: str, expr: Any, axis: str) -> tuple[Any, Symbol] | None:
    """The curve as its distance from the axis in terms of the run along it: y = f(x)
    about the x-axis, x = g(y) about the y-axis; None for a curve written the other way."""
    run = _X if axis == "y" else _Y
    if name not in {"y", "x", ""} or (name == "y") != (axis == "y"):
        return None
    if not expr.free_symbols <= {run}:
        return None
    return expr, run


def _sweeps(shape: str, distance: Any, run: Symbol, ends: Sequence[Any]) -> bool:
    """The solid ``distance`` (a function of ``run``) sweeps out is ``shape``; ``ends``,
    the values of the run the question bounds the region at, tell a cone (the line meets
    the axis at one) from a frustum (it meets it at none)."""
    if shape == "cylinder":
        return bool(distance.is_number) and distance != 0
    if shape in {"cone", "frustum"}:
        if distance.is_number or not distance.is_polynomial(run) or degree(distance, run) != 1:
            return False
        meets = -distance.subs(run, 0) / distance.diff(run)
        if not ends:
            return True  # where the region ends is not said: either may be meant
        at_an_end = any(same_number(meets, end) for end in ends)
        return at_an_end if shape == "cone" else not at_an_end
    if shape in {"sphere", "hemisphere"}:
        return bool(simplify(distance**2 + run**2).is_number)
    return True


def revolves_into(shape: str, texts: Sequence[str]) -> bool:
    """``shape`` is the solid the question's own curve sweeps about its axis, when the
    question revolves a curve it writes; True when it writes none or turns about no axis."""
    if shape not in _SOLIDS or not texts:
        return True
    axis = revolution_axis(plain(texts[0]))
    if axis is None or axis[1] != 0:
        return True
    question = read_plot_question(texts)
    curves = [
        found
        for written in question.formulas
        if written.expr.free_symbols
        and (found := _distance_and_run(written.name, written.expr, axis[0])) is not None
    ]
    if not curves:
        return True
    # The region's ends as the question writes them ("from y = 0 to y = 4" too).
    ends = question.x_values
    return any(_sweeps(shape, distance, run, ends) for distance, run in curves)
