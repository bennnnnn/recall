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

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sympy import FiniteSet, Interval, S, Symbol, degree, expand, simplify, solve, solveset
from sympy.calculus.util import continuous_domain, function_range

from app.modules.math.drawing.plot_question import Written, read_plot_question
from app.modules.math.drawing.plot_reading import same_number
from app.modules.math.drawing.plot_x import named_values

_X, _Y = Symbol("x"), Symbol("y")
_SOLIDS = frozenset({"cylinder", "cone", "frustum", "sphere", "hemisphere"})
# "about the x-axis", "around the line y = -1": the axis named as what the region turns
# about, not as one of its edges.
_ABOUT_AXIS = re.compile(
    r"\b(?:about|around)\s+(?:the\s+)?(?:[xy][-\s]?axis\b|(?:line\s+)?[xy]\s?=\s?[-+]?[\w./]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _Swept:
    """A curve as its distance from the axis line in the run along it: each branch it may
    be once turned round, and, turned round, the curve as written (its letter and formula)."""

    branches: tuple[Any, ...]
    run: Symbol
    written: tuple[Symbol, Any] | None = None


def _distance_and_run(written: Written, axis: tuple[str, Any]) -> _Swept | None:
    """A curve or level line the question names as its distance from the axis line, in
    terms of the run along it: about a line y = c, y = f(x) (or f(x) = …, or y = 3) as it is
    and x = g(y) turned round to y = f(x); about a line x = c, x = g(y) as it is and
    y = f(x) turned round, each real branch kept (``_one_branch`` picks). A line across the
    axis ("x = 3" about the x-axis) ends the region: None; so does one in other letters
    ("y = rx/h"), as no number of it can be checked."""
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
    if own == run:
        return _Swept((expr - at,), run)
    if expr.is_number:
        return None  # a level line across the axis: an end
    # y = f(x) as x = g(y), or the other way, over the reals: x = √y is y = x² for x ≥ 0.
    real_own, real_run = Symbol(str(own), real=True), Symbol(str(run), real=True)
    try:
        found = solve(expr.subs(own, real_own) - real_run, real_own)
    except (NotImplementedError, ValueError, TypeError):
        found = []
    branches = tuple(b.subs(real_run, run) - at for b in found if b.free_symbols <= {real_run})
    return _Swept(branches, run, (own, expr))


def _on(branch: Any, swept: _Swept, at: Any, places: Sequence[float]) -> bool:
    """The branch is the curve as written at each of ``places`` along the run."""
    if swept.written is None:
        return True
    own, expr = swept.written
    for place in places:
        try:
            value = complex(expr.subs(own, (branch + at).subs(swept.run, place)))
        except (TypeError, ValueError):
            return False
        if abs(value.imag) > 1e-9 or abs(value.real - place) > 1e-9 * max(1.0, abs(place)):
            return False
    return True


def _one_branch(swept: _Swept, at: Any, ends: Sequence[Any]) -> Any | None:
    """The one distance a curve turned round is over the region: the branches that are the
    curve as written between the region's ends; several at one distance either side of the
    axis (x = √(4 - y²) about the x-axis: ±√(4 - x²)) sweep one solid. None when no single
    distance is left."""
    numbers = sorted(float(end) for end in ends)
    places = [numbers[0] + (numbers[-1] - numbers[0]) * k / 4 for k in range(5)] if numbers else []
    kept = [b for b in swept.branches if _on(b, swept, at, places)]
    if not kept:
        return None
    first = kept[0]
    if all(simplify(b - first) == 0 or simplify(b + first) == 0 for b in kept):
        return first
    return None


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
        if len(set(ends)) < 2:
            return False  # two ends not said: the region may run on, neither can be checked
        at_an_end = any(same_number(meets, end) for end in ends)
        return bool(at_an_end if shape == "cone" else not at_an_end)
    if shape in {"sphere", "hemisphere"}:
        # An arc of a circle whose centre is on the axis: d² + (run - c)² = R², so d² + run²
        # is a line in the run (the semicircle y = √(4 - (x - 2)²) about the x-axis too).
        swept = expand(simplify(distance**2) + run**2)
        if not (swept.is_polynomial(run) and degree(swept, run) <= 1):
            return False
        return _whole_or_half(shape, swept, run, ends)
    return True


def _whole_or_half(shape: str, swept: Any, run: Symbol, ends: Sequence[Any]) -> bool:
    """A sphere's arc runs the whole diameter along the axis, a hemisphere's half of it, as
    the region's ends say: x = √(4 - y²) from the y-axis about the x-axis is x in [0, 2], a
    hemisphere, not a sphere."""
    centre = float(swept.coeff(run, 1)) / 2
    squared = float(swept.subs(run, 0)) + centre**2
    numbers = [float(end) for end in ends]
    if squared <= 0 or len(set(numbers)) < 2:
        return False
    radius, low, high = math.sqrt(squared), min(numbers), max(numbers)
    near = 1e-6 * max(1.0, radius)
    if shape == "sphere":
        return low <= centre - radius + near and high >= centre + radius - near
    halves = ((centre, centre + radius), (centre - radius, centre))
    return any(abs(low - a) <= near and abs(high - b) <= near for a, b in halves)


def _implied_ends(swept: _Swept, at: Any) -> list[Any]:
    """Where the curve as written lives along the run, when the question states no ends:
    y = √(4 - x²) for x in [-2, 2]; x = √(4 - y²) turned round for x in [0, 2] (its values).
    Unbounded (y = 2x): none."""
    try:
        if swept.written is None:
            curve = swept.branches[0] + at
            found = continuous_domain(curve, swept.run, S.Reals)
        else:
            own, expr = swept.written
            found = function_range(expr, own, continuous_domain(expr, own, S.Reals))
    except (NotImplementedError, ValueError, TypeError):
        return []
    if not isinstance(found, Interval) or not (found.start.is_finite and found.end.is_finite):
        return []
    return [found.start, found.end]


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
    # An interval naming no letter is of y for a curve written x = g(y) ("x = y + 1 on [0, 2]").
    sideways = any(w.name == "x" and w.expr.free_symbols for w in question.formulas)
    letters = {"y", ""} if sideways else {"y"}
    stated = [i for i in question.intervals if i.of in letters]
    rest = _ABOUT_AXIS.sub(" ", text)
    lines, _points = named_values(rest, "y", frozenset({"x", "y"}))
    if re.search(r"\bx-axis\b", rest, re.IGNORECASE):
        lines.append(0)
    pairs = [y for _x, y in question.pairs]  # "from (0, 0) to (3, 6)"
    return [*lines, *pairs, *(end for i in stated for end in (i.low, i.high))]


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
    # The question as the drawing reads it: a follow-up ("now sketch the solid") is read
    # with the message that writes the curve and the axis.
    question = read_plot_question(texts)
    axis = question.revolution_axis
    if axis is None:
        return True
    text = question.words
    run = _X if axis[0] == "y" else _Y
    ends = _ends(text, question, axis, run)
    found: dict[str, tuple[Any, list[Any]]] = {}
    for written in question.formulas:
        swept = _distance_and_run(written, axis)
        if swept is None:
            continue
        implied = _implied_ends(swept, axis[1]) if len(set(ends)) < 2 else []
        distance = _one_branch(swept, axis[1], ends or implied)
        if distance is None:
            return False  # a curve it cannot check: no solid, never a default
        if distance != 0:
            found.setdefault(str(simplify(distance)), (distance, implied))
    if not found:
        return True
    if len(found) > 1:
        return False  # hollow: a washer, never a cone, cylinder or sphere
    distance, implied = next(iter(found.values()))
    if len(set(ends)) < 2 and implied:
        ends = [*ends, *implied]  # where the curve itself ends (a semicircle's diameter)
    if len(set(ends)) == 1 and _axis_bounds(text, axis) and not distance.is_number:
        # One end stated: the curve's meeting with the axis edge is the other.
        roots = solveset(distance, run, domain=S.Reals)
        ends += list(roots) if isinstance(roots, FiniteSet) else []
    return _sweeps(shape, distance, run, ends)
