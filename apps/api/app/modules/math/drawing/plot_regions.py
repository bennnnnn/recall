"""The areas a graph shades, its Riemann rectangles, and the axis a region turns about.

A shaded region lies between two edges, each a curve or a line the picture draws or an
axis, from one bound to another: a value the question gives x (or y) or a place the edges
meet, which the server finds. Left out, the bounds are the outermost places they meet. It
is cut where the edges cross, one polygon to each part, and never drawn across a break.
Rectangles stand on the stated interval, as many as the question says, each as tall as the
curve where the rule the question names says (left, right, midpoint, inscribed or
circumscribed).
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

import numpy as np
from sympy import nsimplify

from app.modules.math.drawing.curve_breaks import has_pole
from app.modules.math.drawing.curve_features import snapped, zeros
from app.modules.math.drawing.plot_check import (
    edge_function,
    on_a_stated_interval,
    stated_end,
    stated_interval,
)
from app.modules.math.drawing.plot_enclosed import enclosed
from app.modules.math.drawing.plot_items import Axis, Rectangles, Shade
from app.modules.math.drawing.plot_labels import point_text
from app.modules.math.drawing.plot_question import PlotQuestion
from app.modules.math.drawing.plot_reading import number, same_number
from app.modules.math.drawing.plot_scene import DrawnLine, DrawnPoint, DrawnRegion, Scene, Shaded
from app.modules.math.drawing.plot_x import axis_line
from app.modules.math.drawing.real_curve import RealFunction, X
from app.modules.math.solve.approximation import rule_nodes

_SAMPLES = 120
_BELOW_COLOR = 2
_MOST_REGIONS = 8
_MOST_UNSTATED_RECTANGLES = 12
# Rules a rectangle stands for: any other a question names (trapezoids, Simpson's
# parabolas) is no picture of rectangles.
_RECTANGLE_RULES = frozenset({"left", "right", "midpoint"})


def _sideways_edge(name: str, scene: Scene) -> RealFunction | None:
    if name in {"y-axis", "x=0", "x = 0"}:
        return RealFunction(X * 0)
    curve = scene.curves.get(name)
    return curve.sideways if curve is not None else None


def _meet(written: Any, meets: list[float]) -> float | None:
    near = [m for m in meets if same_number(written, m, 1e-3)]
    return min(near, key=lambda m: abs(m - float(written))) if near else None


def _stated_bounds(item: Shade, meets: list[float], question: PlotQuestion) -> list[float] | None:
    """Bounds the item writes: an interval the question writes, or places the edges meet,
    one of them perhaps an edge the question names ("bounded by y = x², the x-axis and
    x = 2"). Any other value the question writes bounds nothing (b01's "the gradient at
    x = 3", b03's "between 2 and 3" said of the answer)."""
    start, end = number(item.start), number(item.end)
    if start is None or end is None:
        return None
    low, high = (start, end) if float(start) <= float(end) else (end, start)
    along_x = item.wrt == "x"
    held = stated_interval(low, high, question) if along_x else None
    if held is not None:
        return [float(held.low), float(held.high)]
    ends = [_meet(low, meets), _meet(high, meets)]
    if ends == [None, None]:
        return None
    meet = next(end for end in ends if end is not None)
    for i, written in enumerate((low, high)):
        if ends[i] is None:
            own = stated_end(written, question, meet) if along_x else None
            if own is None:
                return None
            ends[i] = float(own)
    return [end for end in ends if end is not None]


def _bounds(item: Shade, low_edge: RealFunction, high_edge: RealFunction, scene: Scene,
            question: PlotQuestion) -> tuple[float, float, list[float]] | None:  # fmt: skip
    reach = max(abs(v) for curve in scene.curves.values() for v in curve.search)
    difference = RealFunction(low_edge.expr - high_edge.expr)
    meets = zeros(difference.values, -reach, reach)
    if not item.start and not item.end:
        # Left out, the bounds are the outermost places the edges meet: only when they meet
        # that often and no more (sin x and cos x meet without end; b04 drew five lobes).
        if len(meets) < 2 or len(zeros(difference.values, -2 * reach, 2 * reach)) != len(meets):
            return None
        found = [meets[0], meets[-1]]
    else:
        stated_ends = _stated_bounds(item, meets, question)
        if stated_ends is None:
            return None
        found = stated_ends
    low, high = sorted(found)
    if item.wrt == "x" and not on_a_stated_interval(low, high, question):
        return None  # the question's own interval, or no region
    if high - low < 1e-9 or has_pole(low_edge, low, high) or has_pole(high_edge, low, high):
        return None  # no area, or one across a pole (1/x² on [-1, 1])
    return low, high, [m for m in meets if low - 1e-9 <= m <= high + 1e-9]


def shade(item: Shade, question: PlotQuestion, scene: Scene) -> None:
    if len(item.between) == 3:
        enclosed(item, scene)
        return
    # Two curves x = g(y) bound a region along y, whatever the item says.
    if all(_sideways_edge(name, scene) is not None for name in item.between):
        item = item.model_copy(update={"wrt": "y"})
    pick = _sideways_edge if item.wrt == "y" else edge_function
    first, second = (pick(name, scene) for name in item.between)
    if first is None or second is None or len(scene.regions) >= _MOST_REGIONS:
        return
    found = _bounds(item, first, second, scene, question)
    if found is None:
        return
    low, high, meets = found
    cuts = [m for m in meets if low + 1e-9 < m < high - 1e-9]
    edges = [low, *cuts, high]
    parts: list[list[tuple[float, float]]] = []
    for a, b in pairwise(edges):
        ts = np.linspace(a, b, _SAMPLES)
        one, two = first.values(ts), second.values(ts)
        if not (np.all(np.isfinite(one)) and np.all(np.isfinite(two))):
            return  # a break inside: the area is not a region the picture can shade
        outline = [*zip(ts, one, strict=True), *zip(ts[::-1], two[::-1], strict=True)]
        parts.append([(float(t), float(v)) for t, v in outline])
    # A signed area: the parts above the axis in one colour, the parts below in another.
    signed = item.wrt == "x" and "x-axis" in item.between
    for part in parts:
        points = [(v, t) for t, v in part] if item.wrt == "y" else part
        below = signed and sum(y for _, y in part) < 0
        scene.regions.append(DrawnRegion(points, color=_BELOW_COLOR if below else 0))
    scene.shaded.append(Shaded(first, second, low, high, item.wrt))
    difference = first.expr - second.expr
    for meet in meets:
        exact = snapped(meet, [], difference)
        other = first.exact_at(exact) if not exact.is_Float else None
        across = other if other is not None else first.at(meet)
        x, y = (across, exact) if item.wrt == "y" else (exact, across)
        held = (float(x), float(y))
        scene.add_point(DrawnPoint(*held, point_text(x, y), held=held, meet=True))
    scene.focus += [(low, 0.0), (high, 0.0)] if item.wrt == "x" else [(0.0, low), (0.0, high)]


def _rules_named(question: PlotQuestion) -> set[str] | None:
    """The rules the question allows: the one the numerical-method reader reads
    (``match.numerical_methods``), each side it names ("compare the left and right sums",
    "heights at the left endpoints") and the lower or upper sums it names; none for another
    rule (trapezoids, Simpson's); None when it names no rule or no side ("a Riemann sum"),
    and the reply's rectangles stand as described."""
    if question.rule in _RECTANGLE_RULES:
        return {question.rule}
    named = set(question.sides) | set(question.sums)
    if named:
        return named
    # "A limit of sums of rectangles", "a Riemann sum" with no side: no rule is named.
    unnamed = question.rule == "unworked" and not question.estimates
    return None if question.rule is None or unnamed else set()


def _heights(fn: RealFunction, low: Any, high: Any, n: int, rule: str) -> Any:
    """Each rectangle's height: the curve at the rule's nodes (``solve.approximation``), or
    its least or greatest on the rectangle for an inscribed or circumscribed sum."""
    if rule in _RECTANGLE_RULES:
        _h, nodes, _weights, _factor = rule_nodes(low, high, n, rule)
        return fn.values(np.array([float(node) for node in nodes]))
    edges = np.linspace(float(low), float(high), n + 1)
    inside = np.array([fn.values(np.linspace(a, b, 64)) for a, b in pairwise(edges)])
    return inside.min(axis=1) if rule == "lower" else inside.max(axis=1)


def _count_holds(n: int, low: Any, high: Any, question: PlotQuestion) -> bool:
    """``n`` rectangles are the question's: the count it writes, or the width it gives
    ("rectangles of width 0.5" on [0, 2] are 4); a few when it says neither."""
    if question.width is not None and question.width > 0:
        across = nsimplify((high - low) / question.width, rational=True)
        if not across.is_Integer or int(across) != n:
            return False
    counts = set(question.counts)
    if counts:
        return n in counts
    return question.width is not None or n <= _MOST_UNSTATED_RECTANGLES


def rectangles(item: Rectangles, question: PlotQuestion, scene: Scene) -> None:
    curve = scene.curves.get(item.under)
    fn = curve.whole if curve is not None else None
    start, end = number(item.start), number(item.end)
    held = stated_interval(start, end, question) if start is not None and end is not None else None
    if fn is None or held is None or item.rule not in {*_RECTANGLE_RULES, "lower", "upper"}:
        return  # no stated interval
    low, high = held.low, held.high
    if not _count_holds(item.n, low, high, question) or has_pole(fn, float(low), float(high)):
        return
    heights = _heights(fn, low, high, item.n, item.rule)
    allowed = _rules_named(question)
    if allowed is not None and not any(
        np.allclose(heights, _heights(fn, low, high, item.n, rule)) for rule in allowed
    ):
        return  # rectangles of a rule the question does not name, by their heights
    if not np.all(np.isfinite(heights)):
        return
    edges = np.linspace(float(low), float(high), item.n + 1)
    for a, b, h in zip(edges[:-1], edges[1:], heights, strict=True):
        corners = [(float(a), 0.0), (float(a), float(h)), (float(b), float(h)), (float(b), 0.0)]
        scene.regions.append(DrawnRegion(corners, kind="strip", color=curve.color if curve else 0))
    scene.focus += [(float(low), 0.0), (float(high), 0.0)]


def axis(item: Axis, question: PlotQuestion, scene: Scene) -> None:
    """The axis a region turns about: the line the question names after "about" or
    "around", never another line it mentions (a boundary, f01's x-axis)."""
    wanted, own = question.revolution_axis, axis_line(item.line)
    if wanted is None or own is None or own[0] != wanted[0]:
        return
    name, at = wanted
    if not same_number(own[1], at):
        return
    scene.marks.append(
        DrawnLine(vertical=at, role="axis") if name == "x" else DrawnLine(0, at, role="axis")
    )
