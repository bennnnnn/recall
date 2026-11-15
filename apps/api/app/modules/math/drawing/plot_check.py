"""What a graph's items are checked against: the question's values and the curves' places.

Curves come first (``plot_curves``) and are the picture's main object. Every other item
points at a curve or line by name and is checked against it (``plot_marks``,
``plot_regions``): an item that fails is left out, and the rest are drawn. A value an item
writes (where a tangent touches, a region's bounds) must be one the question states or one
the server finds on the curves (``places_of``); the server's own value is the one drawn and
labelled.
"""

from __future__ import annotations

import math
from typing import Any

from sympy import Symbol

from app.modules.math.drawing.curve_features import snapped, zeros
from app.modules.math.drawing.plot_pieces import value
from app.modules.math.drawing.plot_question import PlotQuestion
from app.modules.math.drawing.plot_scene import DrawnCurve, Place, Scene
from app.modules.math.drawing.real_curve import RealFunction, X

_X = Symbol("x")
# Places are looked for this far out, or three times the farthest value the question writes.
_REACH, _FARTHEST = 10.0, 500.0


def stated(number: Any, question: PlotQuestion) -> Any | None:
    """The question's own value of x equal to ``number``, or None."""
    for written in question.x_values:
        try:
            if abs(float(written) - float(number)) < 1e-9 * max(1.0, abs(float(number))):
                return written
        except (TypeError, ValueError):
            continue
    return None


def reach(question: PlotQuestion) -> float:
    far = [abs(float(v)) for v in question.values if math.isfinite(float(v))]
    return min(_FARTHEST, max([_REACH, *(3 * v for v in far)]))


def edge_function(name: str, scene: Scene) -> RealFunction | None:
    """A region's or a crossing's edge as one formula of x: a curve, a line or the x-axis."""
    if name in {"x-axis", "y=0", "y = 0"}:
        return RealFunction(X * 0)
    curve = scene.curves.get(name)
    if curve is not None:
        return curve.whole
    line = scene.lines.get(name)
    if line is not None and line.vertical is None:
        return RealFunction(line.slope * X + line.offset)
    return None


def crossings(curve: DrawnCurve, scene: Scene) -> list[Place]:
    """Where ``curve`` meets each other curve and line the picture draws."""
    own = curve.single
    if own is None:
        return []
    found: list[Place] = []
    low, high = curve.search
    others = [n for n in [*scene.curves, *scene.lines] if n != curve.name]
    for other in others:
        edge = edge_function(other, scene)
        if edge is None:
            line = scene.lines.get(other)
            if line is not None and line.vertical is not None:
                found.append(Place(line.vertical, own.at(float(line.vertical))))
            continue
        difference = RealFunction(own.expr - edge.expr)
        for x in zeros(difference.values, low, high):
            exact = snapped(x, [], difference.expr)
            found.append(Place(exact, own.exact_at(exact) if exact.is_Rational else own.at(x)))
    return [p for p in found if math.isfinite(float(p.y))]


def places_of(curve: DrawnCurve, scene: Scene, question: PlotQuestion) -> list[Any]:
    """The x's an item may name on ``curve``: the question's values, and where the server
    finds the curve crossing, turning or bending, meeting another curve or line, or with a
    slope the question states (a tangent "with a slope of -3", "y = -8x + k")."""
    xs: list[Any] = [*question.x_values]
    xs += [p.x for p in [*curve.roots, *curve.turns, *curve.inflections, *crossings(curve, scene)]]
    own = curve.single
    if own is not None:
        low, high = curve.search
        slopes = {float(v) for v in question.values} | _written_slopes(question)
        for slope in slopes:
            difference = RealFunction(own.derivative(1) - slope)
            xs += [snapped(x, [], difference.expr) for x in zeros(difference.values, low, high)]
    return xs


def _written_slopes(question: PlotQuestion) -> set[float]:
    """The slopes of the lines the question writes, "y = -8x + k" included."""
    found: set[float] = set()
    for written in question.formulas:
        slope = written.expr.diff(_X)
        if written.name != "x" and slope.is_number and slope != 0:
            found.add(float(slope))
    return found


def named_place(text: str, curve: DrawnCurve, scene: Scene, question: PlotQuestion) -> Any | None:
    """The server's own x for the value an item writes, when it is one ``places_of`` holds."""
    written = value(text)
    if written is None:
        return None
    for x in places_of(curve, scene, question):
        try:
            if abs(float(x) - float(written)) < 1e-3 * max(1.0, abs(float(x))):
                return x
        except (TypeError, ValueError):
            continue
    return None
