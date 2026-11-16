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

from collections.abc import Sequence
from typing import Any

from sympy import Symbol, degree, expand, simplify

from app.modules.math.drawing.plot_question import Written, read_plot_question
from app.modules.math.drawing.plot_reading import plain, same_number
from app.modules.math.drawing.plot_x import revolution_axis

_X, _Y = Symbol("x"), Symbol("y")
_SOLIDS = frozenset({"cylinder", "cone", "frustum", "sphere", "hemisphere"})


def _distance_and_run(written: Written, axis: tuple[str, Any]) -> tuple[Any, Symbol] | None:
    """A curve the question names as its distance from the axis line, in terms of the run
    along it: y = f(x) (or f(x) = …) about a line y = c, x = g(y) about a line x = c; None
    for a curve written the other way, or in another letter."""
    letter, at = axis
    if letter == "y" and written.defines and written.name != "x":
        run = _X
    elif letter == "x" and written.name == "x":
        run = _Y
    else:
        return None
    if not written.expr.free_symbols or not written.expr.free_symbols <= {run}:
        return None
    return written.expr - at, run


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
        # An arc of a circle whose centre is on the axis: d² + (run - c)² = R², so d² + run²
        # is a line in the run (the semicircle y = √(4 - (x - 2)²) about the x-axis too).
        swept = expand(simplify(distance**2) + run**2)
        return bool(swept.is_polynomial(run)) and degree(swept, run) <= 1
    return True


def revolves_into(shape: str, texts: Sequence[str]) -> bool:
    """``shape`` is the solid the question's own curves sweep about its axis, when the
    question revolves a region bounded by curves it names: every one of them must sweep
    it (a washer between y = x and y = x² is no cone). True when it names none."""
    if shape not in _SOLIDS or not texts:
        return True
    axis = revolution_axis(plain(texts[0]))
    if axis is None:
        return True
    question = read_plot_question(texts)
    curves = [
        found
        for written in question.formulas
        if (found := _distance_and_run(written, axis)) is not None
    ]
    if not curves:
        return True
    # The region's ends as the question writes them ("from y = 0 to y = 4" too).
    ends = question.x_values
    return all(_sweeps(shape, distance, run, ends) for distance, run in curves)
