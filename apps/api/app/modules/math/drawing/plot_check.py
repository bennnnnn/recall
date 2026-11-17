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
from collections.abc import Sequence
from typing import Any

from sympy import Rational, Symbol

from app.modules.math.drawing.curve_features import snapped, zeros
from app.modules.math.drawing.plot_question import PlotQuestion
from app.modules.math.drawing.plot_reading import number as value
from app.modules.math.drawing.plot_reading import same_number
from app.modules.math.drawing.plot_scene import DrawnCurve, Place, Scene
from app.modules.math.drawing.plot_x import Interval
from app.modules.math.drawing.real_curve import RealFunction, X
from app.modules.math.tool_check import same_value

_WRITTEN_X = Symbol("x")
# A value an item writes names a place the server found to this share of its size.
_NAMED_PLACE = 1e-3
# Places are looked for this far out, or three times the farthest value the question writes.
_REACH, _FARTHEST = 10.0, 500.0


def stated_interval(
    low: Any, high: Any, question: PlotQuestion, along: str = "x"
) -> Interval | None:
    """The question's own interval of x equal to [low, high], its ends as it writes them and
    held or left out as it says: one interval it says of x ("[0, 3]", "from x = 0 to
    x = 2", "0 < x ≤ 2"), or two lines it names ("the lines x = -1/2 and x = 3"). Two
    numbers said of something else ("check that your answer is between 2 and 3") are none.
    ``along`` "y": an interval it says of y ("from y = 0 to y = 4"), and only that one; an
    interval of y is none of x."""
    own = question.x_intervals if along != "y" else [i for i in question.intervals if i.of == "y"]
    for interval in own:
        if same_number(interval.low, low) and same_number(interval.high, high):
            return interval
    if along == "y":
        return None
    a = next((edge for edge in question.edges if same_number(edge, low)), None)
    b = next((edge for edge in question.edges if same_number(edge, high)), None)
    return Interval(a, b) if a is not None and b is not None and float(a) < float(b) else None


def region_intervals(question: PlotQuestion) -> list[Interval]:
    """The intervals of x the question states that a region may stand on: each one it
    writes, but for a formula's own domain ("f(x) = x² for -3 ≤ x ≤ 3"), which bounds the
    curve, not an area under it, unless the clause that states it asks for that area ("the
    area enclosed by the x-axis and f(x) = 12 - 3x² on [-4, 3]")."""
    tasked = [interval for interval, _said, task in question.ties if task]
    domains = [
        (lows[0], highs[0])
        for clause in question.clauses
        for domain in clause.domains
        if len(lows := [c.value for c in domain.conditions if c.op in {">", ">="}]) == 1
        and len(highs := [c.value for c in domain.conditions if c.op in {"<", "<="}]) == 1
    ]
    return [
        interval
        for interval in question.x_intervals
        if (
            interval in tasked
            or not any(
                same_number(interval.low, a) and same_number(interval.high, b) for a, b in domains
            )
        )
    ]


def on_a_stated_interval(
    low: float, high: float, question: PlotQuestion, edges: Sequence[Any]
) -> bool:
    """A region from ``low`` to ``high`` between ``edges`` stands on the interval the
    question states for it, when it states one: inside it and reaching at least one of its
    ends (u5-037's ∫ from -3 to 3 shaded as [-3, 0] and [0, 3]). u5-051's "from x = -4 to
    x = 3" shaded between the roots ±2 alone, a picture of the reply's wrong 32 and not the
    question's 71. An interval is the region's when its clause writes every curve edging
    the region, or no formula at all: "the integral of x³ from 3 to 4" says nothing of the
    area between x² and 2x, nor "the area under y = x from 2 to 5" of the one between y = x
    and y = x². A region the edges' meeting bounds is held to it too."""
    own = region_intervals(question)
    stated = [
        interval
        for interval, said, _task in question.ties
        if interval in own and _said_of(said, edges)
    ]
    near = 1e-6 * max(1.0, abs(low), abs(high))
    for interval in stated:
        a, b = float(interval.low), float(interval.high)
        inside = a - near <= low and high <= b + near
        if inside and (abs(low - a) <= near or abs(high - b) <= near):
            return True
    return not stated


def _said_of(said: Sequence[Any], edges: Sequence[Any]) -> bool:
    # An edge is a formula of the real x; the question's are of x as written.
    curves = [edge.xreplace({X: _WRITTEN_X}) for edge in edges if edge.free_symbols]
    return not said or all(any(same_value(one, edge) for one in said) for edge in curves)


def stated_end(number: Any, question: PlotQuestion, meet: float) -> Any | None:
    """The question's own value equal to ``number`` that ends a region whose other end is
    ``meet``, a place the edges meet: a line it names ("x = 2", "x ≥ 0", the y-axis), or an
    end of an interval of x it writes that holds the meet (u5-037's ∫ from -3 to 3 cut at 0).
    An end of an interval elsewhere is none: b03's 3, of "between 2 and 3" said of the
    answer, shaded [0, 3]."""
    edge = next((edge for edge in question.edges if same_number(edge, number)), None)
    if edge is not None:
        return edge
    for interval in question.x_intervals:
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


# The places a question asks a tangent or a point to stand at, by the words that ask: whole
# words, so "minutes", "the square root" and "across" ask for none.
_ASKED_PLACES = (
    (
        re.compile(
            r"\b(?:max(?:imum|ima)?|min(?:imum|ima)?|turning|stationary|vert(?:ex|ices)"
            r"|extrem(?:um|a|es?)|critical)\b"
        ),
        "turns",
    ),
    (re.compile(r"\binflections?\b"), "inflections"),
    (
        re.compile(
            r"\b(?:x-)?intercepts?\b|(?<!square )(?<!cube )\broots?\b|\bzeros?\b|\bx-axis\b"
        ),
        "roots",
    ),
    (re.compile(r"\b(?:meets?|intersect\w*|cross(?:es|ing)?)\b"), "crossings"),
    (re.compile(r"\by-(?:axis|intercepts?)\b|\bintercepts\b"), "y-axis"),
    (re.compile(r"\borigin\b"), "origin"),
)


def asked_places(question: PlotQuestion) -> list[str]:
    """The kinds of place the question's words ask for: "turns", "roots", "crossings"…"""
    return [kind for pattern, kind in _ASKED_PLACES if pattern.search(question.words)]


def places_of(curve: DrawnCurve, scene: Scene, question: PlotQuestion) -> list[Any]:
    """The x's a tangent, a normal or a marked point may stand at on ``curve``: the x the
    question asks about ("at x = 1", "at the point (1, 1)"), the server's own places of the
    kind it names ("at its local maximum", "where it crosses the x-axis", "where it meets
    the y-axis", "at the origin", each where the curve has it), and where the slope is one
    it states ("a slope of -3", "parallel to y = 2x + 1"). A point off the curve a tangent
    is said to pass through or be drawn from gives the places whose tangent reaches it
    ("the tangent to y = x² + 1 that passes through the origin" touches at ±1); a point
    stated for another reason ("mark the origin") gives none. An end of the interval it
    sketches on is none (the tangent "at x = 1 ... on [-2, 2]" drew at 2)."""
    own = curve.single
    on = [(p, q) for p, q in question.pairs if own is not None and _on(own, p, q)]
    xs: list[Any] = [*question.x_points, *(p for p, _q in on)]
    found = {
        "turns": curve.turns,
        "inflections": curve.inflections,
        "roots": curve.roots,
        "crossings": crossings(curve, scene),
        "y-axis": _at_zero(curve, origin=False),
        "origin": _at_zero(curve, origin=True),
    }
    for kind in asked_places(question):
        xs += [place.x for place in found[kind]]
    if own is not None:
        low, high = curve.search
        for slope in {float(v) for v in question.slopes}:
            difference = RealFunction(own.derivative(1) - slope)
            xs += [snapped(x, [], difference.expr) for x in zeros(difference.values, low, high)]
        for p, q in question.tangent_points:
            if not _on(own, p, q):
                # The tangent at a reaches (p, q): f(a) + f'(a)(p - a) = q.
                miss = RealFunction(own.expr + own.derivative(1) * (p - X) - q)
                xs += [snapped(x, [], miss.expr) for x in zeros(miss.values, low, high)]
    return xs


def _on(fn: RealFunction, x: Any, y: Any) -> bool:
    value = fn.at(float(x))
    return math.isfinite(value) and abs(value - float(y)) <= 1e-9 * (1 + abs(float(y)))


def _at_zero(curve: DrawnCurve, origin: bool) -> list[Place]:
    """Where ``curve`` meets the y-axis, or passes through the origin, when it does."""
    own = curve.single
    low, high = curve.search
    if own is None or not low <= 0 <= high:
        return []
    y = own.at(0.0)
    if not math.isfinite(y) or (origin and abs(y) > 1e-9):
        return []
    exact = own.exact_at(Rational(0))
    return [Place(Rational(0), exact if exact is not None else y)]


def named_place(text: str, curve: DrawnCurve, scene: Scene, question: PlotQuestion) -> Any | None:
    """The server's own x for the value an item writes, when it is one ``places_of`` holds."""
    written = value(text)
    if written is None:
        return None
    return next(
        (x for x in places_of(curve, scene, question) if same_number(written, x, _NAMED_PLACE)),
        None,
    )
