"""The lines and points a graph marks on its curves, each worked out by the server.

A tangent's slope is SymPy's derivative at the place, its normal the perpendicular through
the same point (a vertical line where the tangent is flat), worked out as the solver's card
works it (``tangent_line``); none where the curve has no one tangent (a corner, a cusp, a
jump). Asymptotes are the ones SymPy
and the samples agree on, drawn dashed. A labelled point carries the server's coordinates:
a turning point, an inflection point, a crossing, the end of a stated interval, a point
the question writes, or the points of a curve nearest a point the question writes.
"""

from __future__ import annotations

import math
from typing import Any

from sympy import Expr, Float, oo, radsimp, sqrt

from app.modules.math.drawing.curve_breaks import FAR, end_lines
from app.modules.math.drawing.curve_features import snapped, turning_points
from app.modules.math.drawing.plot_check import crossings, named_place
from app.modules.math.drawing.plot_items import Asymptotes, KeyPoints, Nearest, Point, Touching
from app.modules.math.drawing.plot_labels import equation_text, line_text, number_text, point_text
from app.modules.math.drawing.plot_pieces import end_value
from app.modules.math.drawing.plot_question import PlotQuestion
from app.modules.math.drawing.plot_reading import number, same_number
from app.modules.math.drawing.plot_scene import (
    DrawnCurve,
    DrawnLine,
    DrawnPoint,
    Place,
    Scene,
)
from app.modules.math.drawing.real_curve import RealFunction, X, defined_at
from app.modules.math.solve.graph_sampling import side
from app.modules.math.tangent_line import touching_line

# A tangent and an asymptote are drawn in their curve's colour, so a legend row names the
# lines of one curve only (u5-006: three tangents in one colour beside one row, y = 2x); a
# normal in one no curve uses, apart from the tangent at the same point.


def _exact_y(fn: RealFunction, x: Any) -> Any:
    exact = fn.exact_at(x) if isinstance(x, Expr) and not x.is_Float else None
    return radsimp(exact) if exact is not None else fn.at(float(x))


def point_of(place: Place, fn: RealFunction | None, color: int, label: bool = True) -> DrawnPoint:
    y = _exact_y(fn, place.x) if fn is not None else place.y
    if not math.isfinite(float(y)):
        y = place.y  # the value it settles on at an end it leaves out
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


def _smooth_at(fn: RealFunction, x0: float) -> bool:
    """The curve has one tangent at ``x0``: it is defined and continuous there, and its
    slope is the same from both sides. |x - 2| at 2 (a corner), x^(2/3) at 0 (a cusp), a
    jump between pieces and a hole have none (c01, c02, c03, c04, c07 of the review)."""
    here = fn.at(x0)
    if not math.isfinite(here):
        return False
    sides = [side(fn.values, x0, direction) for direction in (-1, 1)]
    near = 1e-6 * (1.0 + abs(here))
    if any(s.kind != "finite" or abs(s.value - here) > near for s in sides):
        return False

    def rise(xs: Any) -> Any:
        return (fn.values(xs) - here) / (xs - x0)

    slopes = [side(rise, x0, direction) for direction in (-1, 1)]
    if any(s.kind != "finite" for s in slopes):
        return False
    return abs(slopes[0].value - slopes[1].value) <= 1e-3 * (1.0 + abs(slopes[1].value))


def touching(item: Touching, question: PlotQuestion, scene: Scene) -> None:
    curve = scene.curves.get(item.to)
    if curve is None or curve.shape is None or curve.whole is None:
        return
    at = named_place(item.at, curve, scene, question)
    span = curve.span_at(float(at)) if at is not None else None
    if at is None or span is None or not _smooth_at(curve.whole, float(at)):
        return
    found = _value_and_slope(span.fn, at)
    if found is None:
        return
    y0, slope = found
    normal = item.item == "normal"
    line_slope, offset = touching_line(at, y0, slope, normal, radsimp)
    color = scene.mark_color() if normal else curve.color
    if line_slope is None:
        line = DrawnLine(vertical=at, label=equation_text("x", at), color=color, held=(float(at),))
    else:
        held = (float(line_slope), float(offset))
        line = DrawnLine(line_slope, offset, label=line_text(line_slope, offset), color=color)
        line.held = held
        scene.equal = scene.equal or normal
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
                DrawnLine(
                    vertical=found.x,
                    role="asymptote",
                    label=label,
                    color=curve.color,
                    held=(float(found.x),),
                )
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
                color=curve.color,
                held=(float(slope), float(offset)),
            )
        )
        scene.asymptote_sides |= _sides_approached(fn, slope, offset)


def _sides_approached(fn: RealFunction, slope: Any, offset: Any) -> set[int]:
    sides: set[int] = set()
    for direction in (1, -1):
        far = direction * FAR[-1]
        y = fn.at(far)
        if math.isfinite(y) and abs(y - (float(slope) * far + float(offset))) < 1e-2:
            sides.add(direction)
    return sides


def _ends(curve: DrawnCurve) -> list[Place]:
    if curve.shape is None or not curve.stated_domain:
        return []
    span = curve.shape.spans[0]
    ends = ((span.low, span.low_closed, 1), (span.high, span.high_closed, -1))
    # An end the curve runs off to infinity at, or has no value at, is no point (ln x at 0).
    places: list[Place] = []
    for end, closed, inward in ends:
        y = end_value(span, end, closed, inward) if end not in (-oo, oo) else None
        if y is not None:
            held = (
                closed and math.isfinite(span.fn.at(float(end))) and defined_at(span.fn.expr, end)
            )
            places.append(Place(end, _exact_y(span.fn, end) if held else y))
    return places


def key_points(item: KeyPoints, scene: Scene) -> None:
    curve = scene.curves.get(item.of)
    if curve is None or curve.shape is None:
        return
    places: list[tuple[Place, str]] = []
    if "extrema" in item.show:
        places += [(p, "turns") for p in curve.turns]
        curve.marked.add("turns")
    if "inflections" in item.show:
        places += [(p, "inflections") for p in curve.inflections]
        curve.marked.add("inflections")
    if "intercepts" in item.show:
        places += [(p, "roots") for p in curve.roots]
        places += [(curve.y_intercept, "")] if curve.y_intercept else []
        curve.marked.add("roots")
    if "ends" in item.show:
        places += [(p, "") for p in _ends(curve)]
    meets = crossings(curve, scene) if "crossings" in item.show else []
    for place, kind, meet in [*((p, k, False) for p, k in places), *((p, "", True) for p in meets)]:
        span = curve.span_holding(float(place.x))
        # A place the formula has no value at is no point on it (x^x's 1 at 0).
        if span is not None and defined_at(span.fn.expr, place.x):
            point = point_of(place, span.fn, curve.color)
            point.meet, point.kinds = meet, frozenset({kind} - {""})
            scene.add_point(point)


def _written_pair(a: Any, b: Any, question: PlotQuestion) -> bool:
    return any(same_number(p, a) and same_number(q, b) for p, q in question.pairs)


def point(item: Point, question: PlotQuestion, scene: Scene) -> None:
    if item.at is not None:
        a, b = number(item.at[0]), number(item.at[1])
        if a is not None and b is not None and _written_pair(a, b, question):
            scene.add_point(
                DrawnPoint(float(a), float(b), point_text(a, b), color=scene.mark_color())
            )
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
    a, b = number(item.to[0]), number(item.to[1])
    if curve is None or fn is None or a is None or b is None or not _written_pair(a, b, question):
        return
    distance = RealFunction((X - a) ** 2 + (fn.expr - b) ** 2)
    lows = [x for x in turning_points(distance.values, *curve.search) if _lowest(distance, x)]
    if not lows:
        return
    best = min(distance.at(x) for x in lows)
    # One colour for the point and every segment to it: equally near ones alike.
    color = scene.mark_color()
    target = DrawnPoint(float(a), float(b), point_text(a, b), color=color)
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
        scene.marks.append(
            DrawnLine(role="segment", ends=ends, label=length, color=color, held=held)
        )
    scene.equal = True
