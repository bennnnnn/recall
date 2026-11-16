"""A checked graph drawn, every coordinate the server's, in the window ``plot_window`` fits.

Each curve is sampled in the window with its turning points and the edges of its breaks among the
samples, and split at every break, so it never joins across a pole or a jump; the end of a
piece is an open or a filled circle as its condition says, and nothing where two pieces
meet.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from sympy import oo

from app.modules.math.drawing.curve_features import bisect
from app.modules.math.drawing.plot_check import crossings
from app.modules.math.drawing.plot_pieces import end_value
from app.modules.math.drawing.plot_reading import same_number
from app.modules.math.drawing.plot_scene import DrawnCurve, DrawnLine, DrawnPoint, Scene
from app.modules.math.drawing.plot_window import (
    Window,
    curve_places,
    equal_scaled,
    fit_window,
    line_points,
    of_interest,
    span_range,
)
from app.modules.math.drawing.real_curve import defined_at
from app.modules.math.schemas import GraphSampleInput
from app.modules.math.schemas.plot import PlotCurve, PlotGraphSpec, PlotLine, PlotPoint, PlotRegion
from app.modules.math.solve import SolveServiceError, sample_function
from app.modules.math.solve.graph_expr_text import graph_expr_text
from app.modules.math.solve.graph_sampling import sample_places

_SAMPLES = 400
# A label's value agrees with the reply's to its two places.
_LABEL_PLACES = 0.006
# An interval with too many waves for one sampling is halved at most this often.
_MOST_HALVINGS = 2


def _ends(curve: DrawnCurve) -> list[DrawnPoint]:
    """The circles at the ends of a curve's pieces and at its breaks: filled where the
    function takes the value there, open where it does not; none where pieces meet."""
    if curve.shape is None:
        return []
    events: list[tuple[float, float, bool]] = []
    # An end a piece leaves out, where no other piece drawn has a value: open only when the
    # shape holds every piece (else the value there may be a piece left out, t09).
    lone: list[tuple[float, float, bool]] = []
    for span in curve.shape.spans:
        for end, closed, inward in (
            (span.low, span.low_closed, 1),
            (span.high, span.high_closed, -1),
        ):
            if end in (-oo, oo):
                continue
            y = end_value(span, end, closed, inward)
            if y is not None:
                closed = closed and math.isfinite(span.fn.at(float(end)))
                closed = closed and defined_at(span.fn.expr, end)
                (events if closed or curve.shape.complete else lone).append((float(end), y, closed))
    for x_at, y_at in curve.shape.dots:
        events.append((float(x_at), float(y_at), True))
    for found in curve.breaks:
        x = float(found.x)
        # Its value there, when a piece holds x and the formula has one (x⁰ has none at 0).
        holder = curve.span_holding(x)
        held = holder is not None and defined_at(holder.fn.expr, found.x)
        value = found.value if held else None
        for side in (found.left, found.right):
            if side.kind == "finite":
                closed = value is not None and abs(value - side.value) < 1e-6
                events.append((x, side.value, closed))
        if value is not None and all(
            abs(value - s.value) > 1e-6 for s in (found.left, found.right)
        ):
            events.append((x, value, True))
    events += [end for end in lone if _covered(curve, end[0])]
    return _circles(events, curve.color)


def _covered(curve: DrawnCurve, x: float) -> bool:
    """Another drawn piece, or a value the question gives, holds at ``x``."""
    shape = curve.shape
    if shape is None:
        return False
    near = 1e-9 * max(1.0, abs(x))
    dots = any(abs(float(at) - x) < near for at, _ in shape.dots)
    return (
        dots
        or sum(
            (s.low == -oo or float(s.low) < x + near) and (s.high == oo or x - near < float(s.high))
            for s in shape.spans
        )
        > 1
    )


def _circles(events: list[tuple[float, float, bool]], color: int) -> list[DrawnPoint]:
    by_x: dict[float, list[tuple[float, bool]]] = {}
    for x, y, closed in events:
        key = next((k for k in by_x if abs(k - x) < 1e-9 * max(1.0, abs(x))), x)
        by_x.setdefault(key, []).append((y, closed))
    found: list[DrawnPoint] = []
    for x, here in by_x.items():
        groups: list[list[tuple[float, bool]]] = []
        for y, closed in here:
            group = next((g for g in groups if abs(g[0][0] - y) < 1e-6 * (1 + abs(y))), None)
            if group is None:
                groups.append([(y, closed)])
            else:
                group.append((y, closed))
        for group in groups:
            joined = len(group) > 1 and any(c for _, c in group)
            if len(groups) == 1 and joined:
                continue  # two pieces meet: the curve runs on
            found.append(DrawnPoint(x, group[0][0], open=not any(c for _, c in group), color=color))
    return found


def _cuts(curve: DrawnCurve) -> list[float]:
    return [float(b.x) for b in curve.breaks]


def _pieces(
    xs: Any, ys: Any, cuts: list[float], limit: tuple[float, float]
) -> list[list[tuple[float, float]]]:
    pieces: list[list[tuple[float, float]]] = [[]]
    for i, (x, y) in enumerate(zip(xs, ys, strict=True)):
        crossed = i and any(xs[i - 1] < c < x or xs[i - 1] == c for c in cuts)
        if not math.isfinite(y) or crossed:
            pieces.append([])
        if math.isfinite(y) and not any(abs(x - c) < 1e-12 for c in cuts):
            pieces[-1].append((float(x), float(min(max(y, limit[0]), limit[1]))))
    return [p for p in pieces if len(p) >= 2]


def _sample(
    expr: Any, low: float, high: float, depth: int = 0
) -> list[tuple[list[float], list[float]]] | None:
    """The graph sampler's own samples of ``expr`` on [low, high], piece by piece: odd roots
    real, split at its poles and jumps, as every ```graph is sampled. Where it holds too
    many waves for one call the sampler shows only some of them (sin 50x on [0, 2π] came
    back on [2.64, 3.64], n04): the interval is sampled in halves, or not drawn (None)."""
    # Printed in the grammar the sampler and the phone read: ln for a natural log, log for
    # base 10 (SymPy's own "log(x)" is read as base 10, and drew (ln x)/x a third as high).
    text = graph_expr_text(expr, "x")
    if not text:
        return []
    try:
        found = sample_function(GraphSampleInput(expr=text, x_min=low, x_max=high, n=_SAMPLES))
    except (SolveServiceError, ValueError):
        return []
    if (found.x_min, found.x_max) != (low, high):
        if depth >= _MOST_HALVINGS:
            return None
        middle = (low + high) / 2
        halves = [_sample(expr, a, b, depth + 1) for a, b in ((low, middle), (middle, high))]
        return None if None in halves else [piece for half in halves for piece in half or []]
    pieces = found.segments or [found.points]
    return [([p[0] for p in piece], [p[1] for p in piece]) for piece in pieces]


def _sampled(curve: DrawnCurve, window: Window) -> list[list[tuple[float, float]]]:
    x_lo, x_hi, y_lo, y_hi = window
    height, width = y_hi - y_lo, x_hi - x_lo
    if curve.sideways is not None:
        across = (x_lo - 3 * width, x_hi + 3 * width)
        return [
            [(x, t) for t, x in piece]
            for ts, xs in _sample(curve.sideways.expr, y_lo, y_hi) or []
            if _true_to(curve.sideways, ts, xs, y_hi - y_lo)
            for piece in _pieces(ts, xs, [], across)
        ]
    if curve.shape is None:
        return []
    cuts = _cuts(curve)
    limit = (y_lo - 3 * height, y_hi + 3 * height)
    found: list[list[tuple[float, float]]] = []
    for span in curve.shape.spans:
        low, high = span_range(span, x_lo, x_hi)
        if low < high:
            sampled = _sample(span.expr, low, high)
            if sampled is None:
                return []
            places = [float(p.x) for p in [*curve.turns, *curve.roots, *curve.inflections]]
            for xs, ys in sampled:
                if not _true_to(span.fn, xs, ys, high - low):
                    return []
                found += [
                    _finished(piece, span.fn, places, (low, high), limit)
                    for piece in _pieces(xs, ys, cuts, limit)
                ]
    return found


def _finished(
    piece: list[tuple[float, float]], fn: Any, places: list[float],
    span: tuple[float, float], limit: tuple[float, float],
) -> list[tuple[float, float]]:  # fmt: skip
    """A sampled piece with the curve's own places in it (its turning points, roots and
    bends, exactly), run on to the end of the curve's domain where it stops short of it:
    √(9 - x²) ended at (±2.993, 0.208), not at (±3, 0)."""
    step = piece[1][0] - piece[0][0]
    xs = [x for x in places if piece[0][0] < x < piece[-1][0]]
    for x0, outward in ((piece[0][0], -1), (piece[-1][0], 1)):
        beyond = x0 + outward * step
        if span[0] <= beyond <= span[1] and not math.isfinite(fn.at(beyond)):

            def has(v: Any) -> Any:
                return np.where(np.isfinite(fn.values(v)), 1.0, -1.0)

            edge = bisect(has, *sorted((x0, beyond)))
            edge = edge if math.isfinite(fn.at(edge)) else x0 + outward * 0.999 * abs(edge - x0)
            xs.append(edge)
    extra = [(x, fn.at(x)) for x in xs]
    extra = [(x, min(max(y, limit[0]), limit[1])) for x, y in extra if math.isfinite(y)]
    return sorted({*piece, *extra})


def _true_to(fn: Any, xs: list[float], ys: list[float], width: float) -> bool:
    """The samples are the curve's own values, the ones every place on it was found from:
    a curve the sampler read another way (log as base 10) is drawn nowhere, never wrong."""
    picks = range(0, len(xs), max(1, len(xs) // 12))
    # The sampler writes x to so many places for the width it samples: the value anywhere in
    # that rounding is its own.
    rounding = 0.5 * 10.0 ** -sample_places(width)
    for i in picks:
        around = [fn.at(xs[i] + step) for step in (-rounding, 0.0, rounding)]
        if not all(math.isfinite(v) for v in around):
            continue
        low, high = min(around), max(around)
        slack = 1e-3 * (1.0 + abs(around[1]))
        if not low - slack <= ys[i] <= high + slack:
            return False
    return True


def _drawn_line(line: DrawnLine, window: Window) -> PlotLine | None:
    x_lo, x_hi, y_lo, y_hi = window
    if line.ends is not None:
        start, end = line.ends
    elif line.vertical is not None:
        x = float(line.vertical)
        if not x_lo <= x <= x_hi:
            return None
        start, end = (x, y_lo), (x, y_hi)
    else:
        slope, offset = float(line.slope), float(line.offset)
        if slope == 0:
            xs = [x_lo, x_hi]
        else:
            # Where the line enters and leaves the window's height, cut to its width: a line
            # that never crosses the window is none (d05's asymptotes).
            crossed = sorted([(y_lo - offset) / slope, (y_hi - offset) / slope])
            xs = [max(x_lo, crossed[0]), min(x_hi, crossed[1])]
        if xs[0] >= xs[1] or (slope == 0 and not y_lo <= offset <= y_hi):
            return None
        start, end = (xs[0], slope * xs[0] + offset), (xs[1], slope * xs[1] + offset)
    return PlotLine(start=start, end=end, role=line.role, label=line.label, color=line.color)


def _rounded(window: Window) -> Any:
    """Each coordinate to a ten-thousandth of the window's own width or height, far finer
    than a pixel: the fence stays small. One rounding for both drew e^x on [0, 20] (a height
    of 5·10⁸) in whole steps of x, and x² on [0, 0.001] as a staircase (j01, j02)."""
    x_places = max(0, 4 - math.floor(math.log10(window[1] - window[0])))
    y_places = max(0, 4 - math.floor(math.log10(window[3] - window[2])))

    def each(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        return [(round(x, x_places), round(y, y_places)) for x, y in points]

    return each


def _agreed(held: tuple[float, ...], scene: Scene) -> bool:
    """Every value the server worked out for a label is one the reply's working writes (to
    the label's two places), or 0: a label never says what the reply does not."""
    return all(
        abs(value) < 1e-9
        or any(same_number(own, value, _LABEL_PLACES) for own in scene.reply_values)
        for value in held
    )


def _named_line(held: tuple[float, ...], scene: Scene) -> bool:
    """A line the server worked out, (slope, offset) or a vertical one's (x,), is one the
    reply's working writes (y = 7x - 35, x = 2)."""
    if len(held) == 1:
        return any(
            m is None and same_number(c, held[0], _LABEL_PLACES) for m, c in scene.reply_lines
        )
    slope, offset = held
    return any(
        m is not None
        and same_number(m, slope, _LABEL_PLACES)
        and same_number(c, offset, _LABEL_PLACES)
        for m, c in scene.reply_lines
    )


def _line_agreed(line: DrawnLine, scene: Scene) -> bool:
    """A line the server worked out is named only as the reply writes it; a value on a
    segment or a level line across an interval (a distance, an average) only when the reply
    writes that value; a line the question writes always."""
    if all(abs(value) < 1e-9 for value in line.held) or line.role == "segment" or line.ends:
        return _agreed(line.held, scene)
    return _named_line(line.held, scene)


def _curve_label(curve: DrawnCurve, scene: Scene) -> str:
    """A curve's label; one the server worked out (a triangle's side through two stated
    points) only as the reply's working writes that line."""
    return curve.label if not curve.held or _named_line(curve.held, scene) else ""


def _about_the_regions(scene: Scene) -> None:
    """A picture of a region marks the meets that bound it: sin x and cos x cross every π,
    and u5-062 marked eight crossings across a window of 18 for a region of π/4. A turning
    point or an inflection asked for stays wherever it is (j04)."""
    xs = [x for region in scene.regions for x, _ in region.points]
    if not xs:
        return
    low, high = min(xs), max(xs)
    room = 0.1 * (high - low) + 1e-9
    scene.points = [p for p in scene.points if not p.meet or low - room <= p.x <= high + room]


# The most points a plot carries (``schemas.plot``).
_MOST_POINTS = 24
# Which kind of place goes first when a picture marks more than it can carry.
_DROPPED_FIRST = ("inflections", "turns", "roots")


def _within_the_cap(scene: Scene, room: int) -> None:
    """A kind of place is marked whole or not at all: past the ``room`` the curves' own
    circles leave, the kinds the question does not ask for go first, the bends before the
    turns. Cut at the cap, three of sin x + cos 2x's roots went unmarked in view; then its
    asked turns lost to its bends."""
    order = sorted(_DROPPED_FIRST, key=lambda kind: kind in scene.asked)
    dropped: set[str] = set()
    for kind in order:
        if len(scene.points) <= room:
            return
        dropped.add(kind)
        # A place of two kinds (a root that is a bend) goes only with both.
        scene.points = [p for p in scene.points if not p.kinds or not p.kinds <= dropped]
        for curve in scene.curves.values():
            curve.marked.discard(kind)


def _within(x: float, y: float, window: Window) -> bool:
    x_lo, x_hi, y_lo, y_hi = window
    near_x, near_y = 1e-4 * (x_hi - x_lo), 1e-4 * (y_hi - y_lo)
    return x_lo - near_x <= x <= x_hi + near_x and y_lo - near_y <= y <= y_hi + near_y


def draw_plot(scene: Scene) -> PlotGraphSpec | None:
    if not scene.curves:
        return None
    _about_the_regions(scene)
    # A curve's circles (a jump's open end, a piece's filled one) are counted first: they
    # are the curve itself, never cut for a kind of place it marks.
    ends = [point for curve in scene.curves.values() for point in _ends(curve)]
    _within_the_cap(scene, _MOST_POINTS - len(ends))
    places = [p for curve in scene.curves.values() for p in curve_places(curve)]
    # Where the curves meet each other, and the lines the picture draws: two curves, or a
    # curve and a line, are drawn to be seen together (b01; x³ beside x = 2 was cut at 1).
    if len(scene.curves) > 1 or scene.lines:
        places += [p.at for curve in scene.curves.values() for p in crossings(curve, scene)]
    places = of_interest(scene, places)
    places += [(p.x, p.y) for p in [*scene.points, *ends]] + scene.focus
    places += [p for region in scene.regions for p in region.points]
    places += [p for line in [*scene.lines.values(), *scene.marks] for p in line_points(line)]
    window = fit_window(scene, places)
    # One scale on both axes, when asked for, before anything is sampled in the window.
    grown = equal_scaled(window) if scene.equal else None
    window = grown or window
    rounded = _rounded(window)
    curves = [
        PlotCurve(label=_curve_label(curve, scene), segments=[rounded(s) for s in segments[:24]],
                  color=curve.color)
        for curve in scene.curves.values()
        if (segments := _sampled(curve, window))
    ]  # fmt: skip
    if not curves:
        return None
    for point in scene.points:
        point.label = point.label if _agreed(point.held, scene) else ""
    for line in [*scene.lines.values(), *scene.marks]:
        line.label = line.label if _line_agreed(line, scene) else ""

    lines = [
        drawn
        for line in [*scene.lines.values(), *scene.marks]
        if (drawn := _drawn_line(line, window))
    ]
    for end in ends:
        scene.add_point(end)
    # Past the cap, the marks of a kind go last: the circles, the stated and labelled
    # points and the meets the window was fitted to stay.
    kept = sorted(scene.points, key=lambda p: bool(p.kinds))
    points = [
        PlotPoint(x=x, y=y, open=p.open, label=p.label, color=p.color)
        for p in kept
        for x, y in rounded([(p.x, p.y)])
        # A point with no value is no point, and one outside the window is not shown.
        if math.isfinite(x) and math.isfinite(y) and _within(x, y, window)
    ]
    regions = [
        PlotRegion(points=rounded(r.points), kind=r.kind, color=r.color) for r in scene.regions
    ]
    return PlotGraphSpec(
        x_min=window[0], x_max=window[1], y_min=window[2], y_max=window[3], equal=grown is not None,
        curves=curves, lines=lines[:16], regions=regions[:48], points=points[:_MOST_POINTS],
        x_label=scene.x_label[:16], y_label=scene.y_label[:16],
    )  # fmt: skip
