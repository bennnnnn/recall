"""What a graph of a solid of revolution adds: a representative slice, and an average value.

A slice is one thin strip of the shaded region and its mirror across the axis of
revolution, the strip a disc, a washer or a shell sweeps out. It is drawn only where the
region and the axis allow that method honestly: a disc's strip runs from the axis, a
washer's lies wholly to one side of it with a gap, both cut across the axis; a shell's
strip runs along it. The strip stands at the middle of the region, the server's choice, and
carries no number.

A curve's average value over a stated interval is SymPy's integral divided by its length
(by its quick methods, else to six places from the samples), drawn as a level line across
that interval and labelled with it; never across a pole.
"""

from __future__ import annotations

import math
from typing import Any, Literal

import numpy as np
from sympy import Abs, Float, radsimp, sign

from app.modules.math.drawing.curve_breaks import has_pole
from app.modules.math.drawing.plot_check import stated_interval
from app.modules.math.drawing.plot_items import Average, Slice
from app.modules.math.drawing.plot_labels import number_text
from app.modules.math.drawing.plot_pieces import value
from app.modules.math.drawing.plot_question import PlotQuestion
from app.modules.math.drawing.plot_scene import DrawnLine, DrawnRegion, Scene
from app.modules.math.drawing.real_curve import RealFunction, X, closed_integral

_STRIP = 0.04
_STRIP_COLOR = 3
_AVERAGE_COLOR = 2
_QUADRATURE = 4001


def _axis(scene: Scene) -> tuple[str, float] | None:
    """The axis of revolution: ("y", k) for y = k, ("x", h) for x = h."""
    for mark in scene.marks:
        if mark.role == "axis":
            return (
                ("x", float(mark.vertical))
                if mark.vertical is not None
                else ("y", float(mark.offset))
            )
    return None


def slice_of(item: Slice, scene: Scene) -> None:
    axis = _axis(scene)
    if axis is None or not scene.shaded:
        return
    region = scene.shaded[-1]
    # The strip's own direction: across the axis for a disc or a washer, along it for a shell.
    across = item.method != "shell"
    strip_along_x_fixed = (axis[0] == "y") == across
    if strip_along_x_fixed != (region.wrt == "x"):
        return  # the region is not cut that way: no honest strip
    middle = (region.low + region.high) / 2
    half = _STRIP * (region.high - region.low) / 2
    ends = sorted([region.first.at(middle), region.second.at(middle)])
    if not all(math.isfinite(v) for v in ends) or ends[1] - ends[0] < 1e-9:
        return
    level = axis[1]
    if across:
        on_axis = min(abs(v - level) for v in ends) < 1e-9
        apart = ends[0] > level + 1e-9 or ends[1] < level - 1e-9
        if (item.method == "disc" and not on_axis) or (item.method == "washer" and not apart):
            return
        mirror = (middle - half, middle + half, 2 * level - ends[1], 2 * level - ends[0])
    else:
        if region.low < level < region.high:
            return  # a shell's strip on both sides of its axis is no shell
        far = 2 * level - middle
        mirror = (far - half, far + half, ends[0], ends[1])
    strip = (middle - half, middle + half, ends[0], ends[1])
    for (t0, t1, v0, v1), turned in ((strip, False), (mirror, True)):
        corners = [(t0, v0), (t0, v1), (t1, v1), (t1, v0)]
        points = corners if region.wrt == "x" else [(v, t) for t, v in corners]
        kind: Literal["strip", "mirror"] = "mirror" if turned else "strip"
        scene.regions.append(DrawnRegion(points, kind=kind, color=_STRIP_COLOR))


def _mean(fn: RealFunction, a: Any, b: Any) -> Any | None:
    """The mean value, exact from SymPy when the formula has no |…| or odd root in it,
    else to twelve places from the samples (labelled as a decimal)."""
    if not fn.expr.has(Abs, sign):
        total = closed_integral(fn.expr, (X, a, b))
        if total is not None and total.is_finite:
            return radsimp(total / (b - a))
    xs = np.linspace(float(a), float(b), _QUADRATURE)
    ys = fn.values(xs)
    if not np.all(np.isfinite(ys)):
        return None
    total = float(np.sum((ys[1:] + ys[:-1]) * np.diff(xs)) / 2)
    return Float(total / (float(b) - float(a)), 6)


def average(item: Average, question: PlotQuestion, scene: Scene) -> None:
    curve = scene.curves.get(item.of)
    fn = curve.whole if curve is not None else None
    start, end = value(item.start), value(item.end)
    ends = stated_interval(start, end, question) if start is not None and end is not None else None
    if fn is None or ends is None or has_pole(fn, float(ends[0]), float(ends[1])):
        return  # no stated interval, or one across a pole (1/(x - 1) on [0, 3])
    mean = _mean(fn, ends[0], ends[1])
    if mean is None:
        return
    shown = number_text(mean)
    label = f"{scene.y_label[:1] or 'y'} = {shown}" if not mean.is_Float else f"≈ {shown}"
    line = ((float(ends[0]), float(mean)), (float(ends[1]), float(mean)))
    scene.marks.append(
        DrawnLine(role="line", ends=line, label=label, color=_AVERAGE_COLOR, held=(float(mean),))
    )
