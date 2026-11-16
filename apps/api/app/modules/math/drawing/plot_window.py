"""The window a graph is drawn in, fitted to what the graph is about.

It holds every place the picture shows: where each curve crosses an axis, turns and breaks,
every labelled point, region and stated line, where a tangent meets an axis nearby, and
room either side of an asymptote for the curve to run along it. It is never a fixed ±5 or
±10. A picture of an interval (a region, rectangles, a stated domain) shows that interval.
One scale on both axes (a normal, a distance) is the phone's to set, at the card's size.
"""

from __future__ import annotations

import math

import numpy as np
from sympy import oo

from app.modules.math.drawing.curve_features import turning_points, zeros
from app.modules.math.drawing.plot_pieces import Span, end_value
from app.modules.math.drawing.plot_scene import DrawnCurve, DrawnLine, Scene

_PAD = 0.12
# Room beside a vertical asymptote and along a horizontal or oblique one, as a share of the span.
_ASYMPTOTE_ROOM = 0.25
_END_ROOM = 0.6
_ASYMPTOTE_REACH = 4.0
# How far beside a pole the curve is shown from.
_POLE_STEP = 1.0
# ... and at most this share of a stated domain from its end.
_POLE_SHARE = 0.15
# A curve may run on past its places by this share of their height before it leaves.
_RUN_ON = 0.6
_LEAST_HEIGHT = 0.6
# The card is about this much wider than tall (343 by 220, less its margins).
_CARD_ASPECT = 1.65
Window = tuple[float, float, float, float]


def _finite(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(x, y) for x, y in points if math.isfinite(x) and math.isfinite(y)]


def curve_places(curve: DrawnCurve) -> list[tuple[float, float]]:
    if curve.sideways is not None:
        # x = g(y): where it turns and crosses the y-axis, and where it meets the x-axis.
        g, (low, high) = curve.sideways, curve.search
        ys = [*turning_points(g.values, low, high), *zeros(g.values, low, high), 0.0]
        return [(g.at(y), y) for y in ys if math.isfinite(g.at(y))]
    places = [p.at for p in [*curve.roots, *curve.turns]]
    if curve.y_intercept is not None:
        places.append(curve.y_intercept.at)
    if curve.shape is not None:
        for span in curve.shape.spans:
            for end, closed, inward in (
                (span.low, span.low_closed, 1),
                (span.high, span.high_closed, -1),
            ):
                y = end_value(span, end, closed, inward) if end not in (-oo, oo) else None
                if y is not None:
                    places.append((float(end), y))
                elif end not in (-oo, oo):
                    # An end the curve runs off to infinity at: a step in, as beside a pole
                    # (1/x on [0, 2] set y to 10⁷ there).
                    finite = span.low not in (-oo, oo) and span.high not in (-oo, oo)
                    width = float(span.high - span.low) if finite else _POLE_STEP / _POLE_SHARE
                    x = float(end) + inward * min(_POLE_STEP, _POLE_SHARE * width)
                    if span.low == -oo or float(span.low) <= x <= float(span.high):
                        places.append((x, span.fn.at(x)))
        places += [(float(x), float(y)) for x, y in curve.shape.dots]
    for found in curve.breaks:
        for side, direction in ((found.left, -1), (found.right, 1)):
            if side.kind == "finite":
                places.append((float(found.x), side.value))
            elif side.kind == "infinite":
                # Each side of a pole a step out: 1/(x - 1) shows both its branches.
                x = float(found.x) + direction * _POLE_STEP
                beside = curve.span_at(x)
                if beside is not None:
                    places.append((x, beside.fn.at(x)))
    return places


def line_points(line: DrawnLine) -> list[tuple[float, float]]:
    """Where a line must show: a segment's ends, a stated x = a, a stated or turning y = c."""
    if line.ends is not None:
        return list(line.ends)
    if line.vertical is not None and line.role != "asymptote":
        return [(float(line.vertical), 0.0)]
    if line.role in {"line", "axis"} and line.slope is not None and line.slope == 0:
        return [(0.0, float(line.offset))]
    return []


def _box(places: list[tuple[float, float]]) -> Window:
    xs, ys = [p[0] for p in places], [p[1] for p in places]
    return min(xs), max(xs), min(ys), max(ys)


def _line_crossings(scene: Scene, box: Window) -> list[tuple[float, float]]:
    """Where a tangent or normal meets an axis, when that is near what the picture shows."""
    x_lo, x_hi, y_lo, y_hi = box
    room_x, room_y = 1.5 * max(x_hi - x_lo, 1.0), 1.5 * max(y_hi - y_lo, 1.0)
    found: list[tuple[float, float]] = []
    for line in scene.marks:
        if line.role != "line" or line.vertical is not None or line.slope is None:
            continue
        slope, offset = float(line.slope), float(line.offset)
        candidates = [(0.0, offset)] + ([(-offset / slope, 0.0)] if slope else [])
        found += [
            (x, y) for x, y in candidates
            if x_lo - room_x <= x <= x_hi + room_x and y_lo - room_y <= y <= y_hi + room_y
        ]  # fmt: skip
    return found


def _with_axis(low: float, high: float) -> tuple[float, float]:
    span = max(high - low, 1e-9)
    if low > 0 and low < 0.5 * span:
        low = 0.0
    if high < 0 and -high < 0.5 * span:
        high = 0.0
    return low, high


def _padded(low: float, high: float, minimum: float) -> tuple[float, float]:
    span = high - low
    if span < 1e-9:
        return low - minimum, high + minimum
    return low - _PAD * span, high + _PAD * span


def _x_window(scene: Scene, places: list[tuple[float, float]]) -> tuple[float, float]:
    x_lo, x_hi = _box(places)[:2]
    # A curve drawn on a stated domain shows all of it, to the end it runs off at
    # (1/x on [0, 2] showed only [0.88, 2.12]).
    for curve in scene.curves.values():
        if curve.stated_domain and curve.shape is not None:
            for piece in curve.shape.spans:
                ends = [float(end) for end in (piece.low, piece.high) if end not in (-oo, oo)]
                x_lo, x_hi = min([x_lo, *ends]), max([x_hi, *ends])
    x_lo, x_hi = _with_axis(x_lo, x_hi)
    span = max(x_hi - x_lo, 1.0)
    # Never past where breaks were looked for: tan x's asymptotes were found to ±10 and the
    # window ran to ±15.6, poles drawn with no asymptote beside them.
    searched = [c.search for c in scene.curves.values()] or [(x_lo, x_hi)]
    far_lo, far_hi = min(lo for lo, _ in searched), max(hi for _, hi in searched)
    for line in scene.marks:
        if line.role == "asymptote" and line.vertical is not None:
            x = float(line.vertical)
            if _runs_beside(scene, x - 0.05 * span):
                x_lo = min(x_lo, max(far_lo, x - _ASYMPTOTE_ROOM * span))
            if _runs_beside(scene, x + 0.05 * span):
                x_hi = max(x_hi, min(far_hi, x + _ASYMPTOTE_ROOM * span))
    # Room to run along a horizontal or oblique asymptote, and to come near it: √(x² + 1)'s
    # places all lie within 1 of 0, where it is nowhere near y = ±x (d05).
    along = _END_ROOM * max(span, _ASYMPTOTE_REACH)
    if 1 in scene.asymptote_sides:
        x_hi += along
    if -1 in scene.asymptote_sides:
        x_lo -= along
    x_lo, x_hi = _padded(x_lo, x_hi, 2.0)
    if any(line.role == "asymptote" and line.vertical is not None for line in scene.marks):
        x_lo, x_hi = max(x_lo, far_lo), min(x_hi, far_hi)
    return x_lo, x_hi


def _runs_beside(scene: Scene, x: float) -> bool:
    """A curve has a value at ``x``: the side of an asymptote it runs along."""
    for curve in scene.curves.values():
        span = curve.span_at(x)
        if span is not None and math.isfinite(span.fn.at(x)):
            return True
    return False


def of_interest(scene: Scene, places: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """A picture of an interval (a region, rectangles, a stated domain) shows that interval:
    the curve's crossings far outside it are not what it is about."""
    xs = [x for region in scene.regions for x, _ in region.points] + [
        x for curve in scene.curves.values() if curve.stated_domain for x in curve.search
    ]
    if not xs or any(curve.sideways is not None for curve in scene.curves.values()):
        return places
    low, high = min(xs), max(xs)
    room = 0.1 * (high - low)
    return [(x, y) for x, y in places if low - room <= x <= high + room]


def _curve_values(curve: DrawnCurve, x_lo: float, x_hi: float) -> list[float]:
    if curve.shape is None:
        return []
    values: list[float] = []
    for span in curve.shape.spans:
        low, high = span_range(span, x_lo, x_hi)
        if low < high:
            ys = span.fn.values(np.linspace(low, high, 200))
            values += [float(y) for y in ys if math.isfinite(y)]
    return values


def _y_window(
    scene: Scene, places: list[tuple[float, float]], x_lo: float, x_hi: float
) -> tuple[float, float]:
    inside = [y for x, y in places if x_lo <= x <= x_hi] or [y for _, y in places]
    y_lo, y_hi = min(inside), max(inside)
    values = [y for curve in scene.curves.values() for y in _curve_values(curve, x_lo, x_hi)]
    # A curve with places at one height (|ln x| has one) still shows a card's height of itself.
    least = _LEAST_HEIGHT * (x_hi - x_lo) / _CARD_ASPECT
    height = y_hi - y_lo
    run_on = least if height < least / 10 else max(_RUN_ON * height, least / 4)
    floor, ceiling = y_lo - run_on, y_hi + run_on
    for y in values:
        if floor <= y <= ceiling:
            y_lo, y_hi = min(y_lo, y), max(y_hi, y)
    return _padded(*_with_axis(y_lo, y_hi), 1.0)


def span_range(span: Span, x_lo: float, x_hi: float) -> tuple[float, float]:
    low = x_lo if span.low == -oo else max(x_lo, float(span.low))
    high = x_hi if span.high == oo else min(x_hi, float(span.high))
    return low, high


def fit_window(scene: Scene, places: list[tuple[float, float]]) -> Window:
    """The window the picture is about. One scale on both axes, when asked for, is the
    phone's to set at the card's own size (``lib/math/plotGraph.plotBounds``)."""
    places = _finite(places) or [(0.0, 0.0)]
    places += _line_crossings(scene, _box(places))
    x_lo, x_hi = _x_window(scene, places)
    return (x_lo, x_hi, *_y_window(scene, places, x_lo, x_hi))
