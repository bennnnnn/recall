"""The lines and points a graph marks on its curves, each worked out by the server.

A tangent's slope is SymPy's derivative at the place, its normal the perpendicular through
the same point (a vertical line where the tangent is flat). Asymptotes are the ones SymPy
and the samples agree on, drawn dashed. A labelled point carries the server's coordinates:
a turning point, an inflection point, a crossing, the end of a stated interval, a point
the question writes, or the points of a curve nearest a point the question writes.
"""

from __future__ import annotations

import math
from typing import Any

from sympy import Expr, Float, radsimp, sqrt

from app.modules.math.drawing.curve_breaks import end_lines
from app.modules.math.drawing.curve_features import snapped, turning_points
from app.modules.math.drawing.plot_check import crossings, named_place
from app.modules.math.drawing.plot_items import Asymptotes, KeyPoints, Nearest, Point, Touching
from app.modules.math.drawing.plot_labels import equation_text, line_text, number_text, point_text
from app.modules.math.drawing.plot_pieces import value
from app.modules.math.drawing.plot_question import PlotQuestion
from app.modules.math.drawing.plot_scene import DrawnCurve, DrawnLine, DrawnPoint, Place, Scene
from app.modules.math.drawing.real_curve import RealFunction, X

_TOUCH_COLOR = 3
_NORMAL_COLOR = 2


def _exact_y(fn: RealFunction, x: Any) -> Any:
    exact = fn.exact_at(x) if isinstance(x, Expr) and not x.is_Float else None
    return radsimp(exact) if exact is not None else fn.at(float(x))


def point_of(place: Place, fn: RealFunction | None, color: int, label: bool = True) -> DrawnPoint:
    y = _exact_y(fn, place.x) if fn is not None else place.y
    x_shown, y_shown = place.x, y
    text = point_text(x_shown, y_shown) if label else ""
    return DrawnPoint(float(place.x), float(y), text, color=color, held=(float(place.x), float(y)))


def _value_and_slope(fn: RealFunction, at: Any) -> tuple[Any, Any] | None:
    """The curve's value and slope at ``at``: exact from SymPy at an exact place, else the
    decimals the samples give."""
    if not at.is_Float:
        y0, slope = fn.exact_at(at), fn.slope_at(at)
        if y0 is not None and slope is not None and slope.is_finite:
            return radsimp(y0), radsimp(slope)
    y0, slope = fn.at(float(at)), fn.at(float(at), 1)
    if not (math.isfinite(y0) and math.isfinite(slope)):
        return None
    return Float(y0, 12), Float(slope, 12)


def touching(item: Touching, question: PlotQuestion, scene: Scene) -> None:
    curve = scene.curves.get(item.to)
    if curve is None or curve.shape is None:
        return
    at = named_place(item.at, curve, scene, question)
    span = curve.span_at(float(at)) if at is not None else None
    found = _value_and_slope(span.fn, at) if span is not None else None
    if at is None or found is None:
        return
    y0, slope = found
    if item.item == "tangent":
        offset = radsimp(y0 - slope * at)
        line = DrawnLine(slope, offset, label=line_text(slope, offset), color=_TOUCH_COLOR)
        line.held = (float(slope), float(offset))
    elif slope == 0:
        line = DrawnLine(vertical=at, label=equation_text("x", at), color=_NORMAL_COLOR)
        line.held = (float(at),)
    else:
        normal = radsimp(-1 / slope)
        offset = radsimp(y0 - normal * at)
        line = DrawnLine(normal, offset, label=line_text(normal, offset), color=_NORMAL_COLOR)
        line.held = (float(normal), float(offset))
        scene.equal = True
    scene.marks.append(line)
    contact = (float(at), float(y0))
    scene.add_point(DrawnPoint(*contact, point_text(at, y0), color=line.color, held=contact))


def asymptotes(item: Asymptotes, scene: Scene) -> None:
    curve = scene.curves.get(item.of)
    if curve is None or curve.shape is None:
        return
    for found in curve.breaks:
        if found.asymptote:
            label = equation_text("x", found.x) if not found.x.is_Float else ""
            scene.marks.append(
                DrawnLine(vertical=found.x, role="asymptote", label=label, held=(float(found.x),))
            )
    fn = curve.single
    if fn is None or curve.stated_domain:
        return
    for slope, offset in end_lines(fn):
        scene.marks.append(
            DrawnLine(
                slope,
                offset,
                role="asymptote",
                label=line_text(slope, offset),
                held=(float(slope), float(offset)),
            )
        )
        scene.asymptote_sides |= _sides_approached(fn, slope, offset)


def _sides_approached(fn: RealFunction, slope: Any, offset: Any) -> set[int]:
    sides: set[int] = set()
    for direction in (1, -1):
        far = direction * 1e6
        y = fn.at(far)
        if math.isfinite(y) and abs(y - (float(slope) * far + float(offset))) < 1e-2:
            sides.add(direction)
    return sides


def _ends(curve: DrawnCurve) -> list[Place]:
    if curve.shape is None or not curve.stated_domain:
        return []
    span = curve.shape.spans[0]
    return [
        Place(span.low, _exact_y(span.fn, span.low)),
        Place(span.high, _exact_y(span.fn, span.high)),
    ]


def key_points(item: KeyPoints, scene: Scene) -> None:
    curve = scene.curves.get(item.of)
    if curve is None or curve.shape is None:
        return
    places: list[Place] = []
    if "extrema" in item.show:
        places += curve.turns
    if "inflections" in item.show:
        places += curve.inflections
    if "intercepts" in item.show:
        places += curve.roots + ([curve.y_intercept] if curve.y_intercept else [])
    if "ends" in item.show:
        places += _ends(curve)
    if "crossings" in item.show:
        places += crossings(curve, scene)
    for place in places:
        span = curve.span_at(float(place.x))
        if span is not None:
            scene.add_point(point_of(place, span.fn, curve.color))


def _written_pair(a: Any, b: Any, question: PlotQuestion) -> bool:
    return any(
        abs(float(a) - float(p)) < 1e-12 and abs(float(b) - float(q)) < 1e-12
        for p, q in question.pairs
    )


def point(item: Point, question: PlotQuestion, scene: Scene) -> None:
    if item.at is not None:
        a, b = value(item.at[0]), value(item.at[1])
        if a is not None and b is not None and _written_pair(a, b, question):
            scene.add_point(DrawnPoint(float(a), float(b), point_text(a, b), color=2))
        return
    curve = scene.curves.get(item.on)
    if curve is None or curve.shape is None:
        return
    at = named_place(item.x, curve, scene, question)
    span = curve.span_at(float(at)) if at is not None else None
    if at is not None and span is not None and math.isfinite(span.fn.at(float(at))):
        scene.add_point(point_of(Place(at, 0), span.fn, curve.color))


def _lowest(distance: RealFunction, x: float) -> bool:
    """A least distance, not a greatest: lower than the distances either side."""
    step = 1e-4 * max(1.0, abs(x))
    return distance.at(x) <= min(distance.at(x - step), distance.at(x + step))


def nearest(item: Nearest, question: PlotQuestion, scene: Scene) -> None:
    """The curve's points nearest the question's point, each joined to it and the length
    labelled: both, when two are equally near."""
    curve = scene.curves.get(item.on)
    fn = curve.single if curve is not None else None
    a, b = value(item.to[0]), value(item.to[1])
    if curve is None or fn is None or a is None or b is None or not _written_pair(a, b, question):
        return
    distance = RealFunction((X - a) ** 2 + (fn.expr - b) ** 2)
    lows = [x for x in turning_points(distance.values, *curve.search) if _lowest(distance, x)]
    if not lows:
        return
    best = min(distance.at(x) for x in lows)
    target = DrawnPoint(float(a), float(b), point_text(a, b), color=2)
    scene.add_point(target)
    for x in lows:
        if distance.at(x) > best * (1 + 1e-9) + 1e-12:
            continue
        exact = snapped(x, [], distance.derivative(1))
        place = point_of(Place(exact, 0), fn, curve.color)
        scene.add_point(place)
        squared = distance.exact_at(exact) if not exact.is_Float else None
        length = (
            number_text(radsimp(sqrt(squared)))
            if squared is not None
            else "≈ " + number_text(Float(math.sqrt(distance.at(x)), 12))
        )
        ends = ((place.x, place.y), (target.x, target.y))
        held = (math.sqrt(distance.at(x)),)
        scene.marks.append(DrawnLine(role="segment", ends=ends, label=length, color=2, held=held))
    scene.equal = True
