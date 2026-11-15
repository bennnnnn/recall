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

import math
from itertools import pairwise
from typing import Any

import numpy as np

from app.modules.math.drawing.curve_features import snapped, zeros
from app.modules.math.drawing.plot_check import edge_function, stated
from app.modules.math.drawing.plot_enclosed import enclosed
from app.modules.math.drawing.plot_items import Axis, Rectangles, Shade
from app.modules.math.drawing.plot_labels import point_text
from app.modules.math.drawing.plot_pieces import value
from app.modules.math.drawing.plot_question import PlotQuestion
from app.modules.math.drawing.plot_scene import DrawnLine, DrawnPoint, DrawnRegion, Scene, Shaded
from app.modules.math.drawing.real_curve import RealFunction, X

_SAMPLES = 120
_BELOW_COLOR = 2
_MOST_REGIONS = 8
_MOST_UNSTATED_RECTANGLES = 12
# The words that name a rule, the words for inscribed and circumscribed before them.
_RULE_WORDS = (
    ("circumscribed", "upper"),
    ("inscribed", "lower"),
    ("upper", "upper"),
    ("lower", "lower"),
    ("left", "left"),
    ("right", "right"),
    ("mid", "midpoint"),
)


def _sideways_edge(name: str, scene: Scene) -> RealFunction | None:
    if name in {"y-axis", "x=0", "x = 0"}:
        return RealFunction(X * 0)
    curve = scene.curves.get(name)
    return curve.sideways if curve is not None else None


def _bounds(item: Shade, low_edge: RealFunction, high_edge: RealFunction, scene: Scene,
            question: PlotQuestion) -> tuple[float, float, list[float]] | None:  # fmt: skip
    reach = max(abs(v) for curve in scene.curves.values() for v in curve.search)
    difference = RealFunction(low_edge.expr - high_edge.expr)
    meets = zeros(difference.values, -reach, reach)
    found: list[float] = []
    for text in (item.start, item.end):
        if not text:
            found.append(math.nan)
            continue
        written = value(text)
        if written is None:
            return None
        held = stated(written, question) if item.wrt == "x" else None
        if held is not None:
            found.append(float(held))
        elif any(abs(m - float(written)) < 1e-3 * max(1.0, abs(m)) for m in meets):
            found.append(min(meets, key=lambda m: abs(m - float(written))))
        else:
            return None
    if math.isnan(found[0]) or math.isnan(found[1]):
        if len(meets) < 2 or not (math.isnan(found[0]) and math.isnan(found[1])):
            return None
        found = [meets[0], meets[-1]]
    low, high = sorted(found)
    if high - low < 1e-9:
        return None
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
        scene.add_point(DrawnPoint(float(x), float(y), point_text(x, y), held=(float(x), float(y))))
    scene.focus += [(low, 0.0), (high, 0.0)] if item.wrt == "x" else [(0.0, low), (0.0, high)]


def _rules_named(words: str) -> set[str]:
    named: set[str] = set()
    for word, rule in _RULE_WORDS:
        if word in words:
            named.add(rule)
            words = words.replace(word, " ")
    return named


def _heights(fn: RealFunction, edges: Any, rule: str) -> Any:
    lefts, rights = edges[:-1], edges[1:]
    if rule == "left":
        return fn.values(lefts)
    if rule == "right":
        return fn.values(rights)
    if rule == "midpoint":
        return fn.values((lefts + rights) / 2)
    inside = np.array(
        [fn.values(np.linspace(a, b, 64)) for a, b in zip(lefts, rights, strict=True)]
    )
    return inside.min(axis=1) if rule == "lower" else inside.max(axis=1)


def rectangles(item: Rectangles, question: PlotQuestion, scene: Scene) -> None:
    curve = scene.curves.get(item.under)
    fn = curve.whole if curve is not None else None
    start, end = value(item.start), value(item.end)
    held = [stated(v, question) if v is not None else None for v in (start, end)]
    if fn is None or held[0] is None or held[1] is None or float(held[0]) >= float(held[1]):
        return
    counts = set(question.counts)
    if (counts and item.n not in counts) or (not counts and item.n > _MOST_UNSTATED_RECTANGLES):
        return
    edges = np.linspace(float(held[0]), float(held[1]), item.n + 1)
    heights = _heights(fn, edges, item.rule)
    named = _rules_named(question.words)
    if (
        named
        and item.rule not in named
        and not any(np.allclose(heights, _heights(fn, edges, rule)) for rule in named)
    ):
        return
    if not np.all(np.isfinite(heights)):
        return
    for a, b, h in zip(edges[:-1], edges[1:], heights, strict=True):
        corners = [(float(a), 0.0), (float(a), float(h)), (float(b), float(h)), (float(b), 0.0)]
        scene.regions.append(DrawnRegion(corners, kind="strip", color=curve.color if curve else 0))
    scene.focus += [(float(held[0]), 0.0), (float(held[1]), 0.0)]


def axis(item: Axis, question: PlotQuestion, scene: Scene) -> None:
    """The axis a region turns about, the question's own: "about the x-axis", "y = 2"."""
    line = item.line.strip().lower().replace(" ", "")
    words = question.words.replace(" ", "")
    if line in {"x-axis", "y=0"} and ("x-axis" in words or "xaxis" in words):
        scene.marks.append(DrawnLine(0, 0, role="axis"))
        return
    if line in {"y-axis", "x=0"} and ("y-axis" in words or "yaxis" in words):
        scene.marks.append(DrawnLine(vertical=0, role="axis"))
        return
    name, _, side = line.partition("=")
    at = value(side)
    if at is None or name not in {"x", "y"}:
        return
    if any(
        w.name == name and w.expr.is_number and abs(float(w.expr) - float(at)) < 1e-12
        for w in question.formulas
    ):
        scene.marks.append(
            DrawnLine(vertical=at, role="axis") if name == "x" else DrawnLine(0, at, role="axis")
        )
