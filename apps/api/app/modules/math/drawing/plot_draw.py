"""A checked graph drawn, every coordinate the server's, in the window ``plot_window`` fits.

Each curve is sampled in the window with its turning points and the edges of its breaks among the
samples, and split at every break, so it never joins across a pole or a jump; the end of a
piece is an open or a filled circle as its condition says, and nothing where two pieces
meet.
"""

from __future__ import annotations

import math
from typing import Any

from sympy import oo

from app.modules.math.drawing.plot_scene import DrawnCurve, DrawnLine, DrawnPoint, Scene
from app.modules.math.drawing.plot_window import (
    Window,
    curve_places,
    fit_window,
    line_points,
    of_interest,
    span_range,
)
from app.modules.math.schemas import GraphSampleInput
from app.modules.math.schemas.plot import PlotCurve, PlotGraphSpec, PlotLine, PlotPoint, PlotRegion
from app.modules.math.solve import SolveServiceError, sample_function
from app.modules.math.solve.graph_expr_text import graph_expr_text

_SAMPLES = 400
# Half the last place the sampler writes x to.
_ROUNDING = 5e-5


def _ends(curve: DrawnCurve) -> list[DrawnPoint]:
    """The circles at the ends of a curve's pieces and at its breaks: filled where the
    function takes the value there, open where it does not; none where pieces meet."""
    if curve.shape is None:
        return []
    events: list[tuple[float, float, bool]] = []
    for span in curve.shape.spans:
        for end, closed, inward in (
            (span.low, span.low_closed, 1),
            (span.high, span.high_closed, -1),
        ):
            if end in (-oo, oo):
                continue
            x = float(end)
            y = span.fn.at(x) if closed else span.fn.at(x + inward * 1e-7 * max(1.0, abs(x)))
            if math.isfinite(y) and abs(y) < 1e6:
                events.append((x, y, closed))
    for x_at, y_at in curve.shape.dots:
        events.append((float(x_at), float(y_at), True))
    for found in curve.breaks:
        x = float(found.x)
        for side in (found.left, found.right):
            if side.kind == "finite":
                closed = found.value is not None and abs(found.value - side.value) < 1e-6
                events.append((x, side.value, closed))
        if found.value is not None and all(
            abs(found.value - s.value) > 1e-6 for s in (found.left, found.right)
        ):
            events.append((x, found.value, True))
    return _circles(events, curve.color)


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


def _sample(expr: Any, low: float, high: float) -> list[tuple[list[float], list[float]]]:
    """The graph sampler's own samples of ``expr`` on [low, high], piece by piece: odd roots
    real, split at its poles and jumps, as every ```graph is sampled."""
    # Printed in the grammar the sampler and the phone read: ln for a natural log, log for
    # base 10 (SymPy's own "log(x)" is read as base 10, and drew (ln x)/x a third as high).
    text = graph_expr_text(expr, "x")
    if not text:
        return []
    try:
        found = sample_function(GraphSampleInput(expr=text, x_min=low, x_max=high, n=_SAMPLES))
    except (SolveServiceError, ValueError):
        return []
    pieces = found.segments or [found.points]
    return [([p[0] for p in piece], [p[1] for p in piece]) for piece in pieces]


def _sampled(curve: DrawnCurve, window: Window) -> list[list[tuple[float, float]]]:
    x_lo, x_hi, y_lo, y_hi = window
    height, width = y_hi - y_lo, x_hi - x_lo
    if curve.sideways is not None:
        across = (x_lo - 3 * width, x_hi + 3 * width)
        return [
            [(x, t) for t, x in piece]
            for ts, xs in _sample(curve.sideways.expr, y_lo, y_hi)
            if _true_to(curve.sideways, ts, xs)
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
            for xs, ys in _sample(span.expr, low, high):
                if not _true_to(span.fn, xs, ys):
                    return []
                found += _pieces(xs, ys, cuts, limit)
    return found


def _true_to(fn: Any, xs: list[float], ys: list[float]) -> bool:
    """The samples are the curve's own values, the ones every place on it was found from:
    a curve the sampler read another way (log as base 10) is drawn nowhere, never wrong."""
    picks = range(0, len(xs), max(1, len(xs) // 12))
    for i in picks:
        # The sampler writes x to four places: the value anywhere in that rounding is its own.
        around = [fn.at(xs[i] + step) for step in (-_ROUNDING, 0.0, _ROUNDING)]
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
        xs = [x_lo, x_hi] if slope == 0 else sorted(
            [max(x_lo, min((y_lo - offset) / slope, (y_hi - offset) / slope)),
             min(x_hi, max((y_lo - offset) / slope, (y_hi - offset) / slope))]
        )  # fmt: skip
        if xs[0] >= xs[1] or (slope == 0 and not y_lo <= offset <= y_hi):
            return None
        start, end = (xs[0], slope * xs[0] + offset), (xs[1], slope * xs[1] + offset)
    return PlotLine(start=start, end=end, role=line.role, label=line.label, color=line.color)


def _rounded(window: Window) -> Any:
    """A coordinate to a ten-thousandth of the window, far finer than a pixel: the fence
    stays small."""
    span = max(window[1] - window[0], window[3] - window[2])
    places = max(0, 4 - math.floor(math.log10(span)))

    def each(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        return [(round(x, places), round(y, places)) for x, y in points]

    return each


def _agreed(held: tuple[float, ...], scene: Scene) -> bool:
    """Every value the server worked out for a label is one the reply's working writes (to
    the label's two places), or 0: a label never says what the reply does not."""
    return all(
        abs(value) < 1e-9
        or any(abs(value - own) <= 0.006 * max(1.0, abs(value)) for own in scene.reply_values)
        for value in held
    )


def _near(a: float, b: float) -> bool:
    return abs(a - b) <= 0.006 * max(1.0, abs(a))


def _line_agreed(line: DrawnLine, scene: Scene) -> bool:
    """A line the server worked out is named only as the reply writes it: its slope and
    offset one of the reply's lines (y = 7x - 35), or a vertical one's x."""
    if all(abs(value) < 1e-9 for value in line.held) or line.role == "segment" or line.ends:
        return _agreed(line.held, scene)
    if len(line.held) == 1:
        return any(m is None and _near(line.held[0], c) for m, c in scene.reply_lines)
    slope, offset = line.held
    return any(m is not None and _near(slope, m) and _near(offset, c) for m, c in scene.reply_lines)


def _about_the_regions(scene: Scene) -> None:
    """A picture of a region marks the places that bound it: sin x and cos x cross every π,
    and u5-062 marked eight crossings across a window of 18 for a region of π/4."""
    xs = [x for region in scene.regions for x, _ in region.points]
    if not xs:
        return
    low, high = min(xs), max(xs)
    room = 0.1 * (high - low) + 1e-9
    scene.points = [p for p in scene.points if not p.held or low - room <= p.x <= high + room]


def draw_plot(scene: Scene) -> PlotGraphSpec | None:
    if not scene.curves:
        return None
    _about_the_regions(scene)
    ends = [point for curve in scene.curves.values() for point in _ends(curve)]
    places = [p for curve in scene.curves.values() for p in curve_places(curve)]
    places = of_interest(scene, places)
    places += [(p.x, p.y) for p in [*scene.points, *ends]] + scene.focus
    places += [p for region in scene.regions for p in region.points]
    places += [p for line in [*scene.lines.values(), *scene.marks] for p in line_points(line)]
    window, square = fit_window(scene, places)
    rounded = _rounded(window)
    curves = [
        PlotCurve(
            label=curve.label, segments=[rounded(s) for s in segments[:24]], color=curve.color
        )
        for curve in scene.curves.values()
        if (segments := _sampled(curve, window))
    ]
    if not curves:
        return None
    for point in scene.points:
        point.label = point.label if _agreed(point.held, scene) else ""
    for mark in scene.marks:
        mark.label = mark.label if _line_agreed(mark, scene) else ""
    lines = [
        drawn
        for line in [*scene.lines.values(), *scene.marks]
        if (drawn := _drawn_line(line, window))
    ]
    for end in ends:
        scene.add_point(end)
    points = [
        PlotPoint(x=x, y=y, open=p.open, label=p.label, color=p.color)
        for p in scene.points
        for x, y in rounded([(p.x, p.y)])
    ]
    regions = [
        PlotRegion(points=rounded(r.points), kind=r.kind, color=r.color) for r in scene.regions
    ]
    return PlotGraphSpec(
        x_min=window[0], x_max=window[1], y_min=window[2], y_max=window[3], equal=square,
        curves=curves, lines=lines[:16], regions=regions[:48], points=points[:24],
        x_label=scene.x_label[:16], y_label=scene.y_label[:16],
    )  # fmt: skip
