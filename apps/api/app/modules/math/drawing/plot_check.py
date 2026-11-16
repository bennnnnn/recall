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
import re
from typing import Any

from app.modules.math.drawing.curve_features import snapped, zeros
from app.modules.math.drawing.plot_question import PlotQuestion
from app.modules.math.drawing.plot_reading import number as value
from app.modules.math.drawing.plot_reading import same_number
from app.modules.math.drawing.plot_scene import DrawnCurve, Place, Scene
from app.modules.math.drawing.plot_x import Interval
from app.modules.math.drawing.real_curve import RealFunction, X

# Places are looked for this far out, or three times the farthest value the question writes.
_REACH, _FARTHEST = 10.0, 500.0


def stated_interval(low: Any, high: Any, question: PlotQuestion) -> Interval | None:
    """The question's own interval of x equal to [low, high], its ends as it writes them and
    held or left out as it says: one interval it says of x ("[0, 3]", "from x = 0 to
    x = 2", "0 < x ≤ 2"), or two lines it names ("the lines x = -1/2 and x = 3"). Two
    numbers said of something else ("check that your answer is between 2 and 3") are none."""
    for interval in question.intervals:
        if same_number(interval.low, low) and same_number(interval.high, high):
            return interval
    a = next((edge for edge in question.edges if same_number(edge, low)), None)
    b = next((edge for edge in question.edges if same_number(edge, high)), None)
    return Interval(a, b) if a is not None and b is not None and float(a) < float(b) else None


def stated_end(number: Any, question: PlotQuestion, meet: float) -> Any | None:
    """The question's own value equal to ``number`` that ends a region whose other end is
    ``meet``, a place the edges meet: a line it names ("x = 2", "x ≥ 0", the y-axis), or an
    end of an interval of x it writes that holds the meet (u5-037's ∫ from -3 to 3 cut at 0).
    An end of an interval elsewhere is none: b03's 3, of "between 2 and 3" said of the
    answer, shaded [0, 3]."""
    edge = next((edge for edge in question.edges if same_number(edge, number)), None)
    if edge is not None:
        return edge
    for interval in question.intervals:
        if float(interval.low) <= meet <= float(interval.high):
            ends = (interval.low, interval.high)
            end = next((end for end in ends if same_number(end, number)), None)
            if end is not None:
                return end
    return None


def reach(question: PlotQuestion) -> float:
    """How far out places are looked for: 10, or three times the farthest value the question
    says of x. A number said of something else ("(12 marks)", "after 100 seconds") moves
    nothing: it drew sin x on [-38.9, 5.9]."""
    far = [abs(float(v)) for v in question.x_values if math.isfinite(float(v))]
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


# The places a question asks a tangent or a point to stand at, by the words that ask.
_ASKED_PLACES = (
    (re.compile(r"\b(?:max|min|turning|stationary|vertex|extrem|critical)"), "turns"),
    (re.compile(r"\binflection"), "inflections"),
    (re.compile(r"\b(?:intercept|root|zero|cross)"), "roots"),
    (re.compile(r"\b(?:meet|intersect|cross)"), "crossings"),
)


def places_of(curve: DrawnCurve, scene: Scene, question: PlotQuestion) -> list[Any]:
    """The x's a tangent, a normal or a marked point may stand at on ``curve``: the x the
    question asks about ("at x = 1", "at the point (1, 1)"), the server's own places of the
    kind it names ("at its local maximum", "where it crosses the axis"), and where the slope
    is one it states ("a slope of -3", "parallel to y = 2x + 1"). An end of the interval it
    sketches on is none (the tangent "at x = 1 ... on [-2, 2]" drew at 2)."""
    xs: list[Any] = [*question.x_points, *(x for x, _y in question.pairs)]
    found = {
        "turns": curve.turns,
        "inflections": curve.inflections,
        "roots": curve.roots,
        "crossings": crossings(curve, scene),
    }
    for pattern, kind in _ASKED_PLACES:
        if pattern.search(question.words):
            xs += [place.x for place in found[kind]]
    own = curve.single
    if own is not None:
        low, high = curve.search
        for slope in {float(v) for v in question.slopes}:
            difference = RealFunction(own.derivative(1) - slope)
            xs += [snapped(x, [], difference.expr) for x in zeros(difference.values, low, high)]
    return xs


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
