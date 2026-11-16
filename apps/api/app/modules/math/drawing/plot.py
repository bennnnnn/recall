"""A graph's ```draw description (kind "plot") checked and drawn as a ```graph ``plot``.

The curves are checked first (``plot_check``): with none of them the question's, there is
no picture. Each other item is checked on its own against the curves and the question
(``plot_marks``, ``plot_regions``) and left out when it fails; ``plot_draw`` fits the window
and writes every coordinate.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from sympy import Symbol

from app.modules.math.drawing import plot_marks, plot_regions, plot_volumes
from app.modules.math.drawing.plot_check import asked_places
from app.modules.math.drawing.plot_curves import add_curves
from app.modules.math.drawing.plot_draw import draw_plot
from app.modules.math.drawing.plot_items import (
    Asymptotes,
    Average,
    Axis,
    Curve,
    KeyPoints,
    Line,
    Nearest,
    Point,
    Rectangles,
    Shade,
    Slice,
    Touching,
)
from app.modules.math.drawing.plot_pieces import formula, formula_shape
from app.modules.math.drawing.plot_question import PlotQuestion, read_plot_question
from app.modules.math.drawing.plot_scene import DrawnCurve, Scene
from app.modules.math.drawing.real_curve import X
from app.modules.math.schemas.plot import PlotGraphSpec
from app.modules.math.tool_check import written_relations, written_values
from app.services.card_text import without_emphasis
from app.services.latex_markup import without_markup

logger = logging.getLogger(__name__)
_MOST_LINE_CURVES = 4
_X, _Y = Symbol("x"), Symbol("y")


def plot_spec(
    items: list[tuple[str, Any | None]], texts: Sequence[str], reply: str = ""
) -> PlotGraphSpec | None:
    """The checked graph of ``items`` (``vocabulary.read_items``), or None. ``reply``: the
    reply's text, whose working the server's labels are held to."""
    question = read_plot_question(texts)
    read = _axes_by_name([item for _name, item in items if item is not None])
    working = _both_signs(reply)
    scene = Scene(
        reply_values=tuple(written_values(working)),
        reply_lines=written_lines(working),
        asked=tuple(asked_places(question)),
    )
    add_curves(read, question, scene)
    if not scene.curves:
        _lines_as_curves(scene)
    if not scene.curves:
        return None
    # A slice is cut from a region and turned about an axis: it comes after both.
    for item in sorted(read, key=lambda found: isinstance(found, Slice)):
        try:
            _add(item, question, scene)
        except Exception:  # SymPy's and numpy's own errors included: that item is left out.
            logger.info("plot item %s failed", type(item).__name__, exc_info=True)
    return draw_plot(scene)


def _axes_by_name(read: list[Any]) -> list[Any]:
    """A region's edge described as a curve or line y = 0 (or x = 0) is the x-axis (the
    y-axis), an edge every picture has: u5-071 named y = 0 "g" and shaded between f and g."""
    axes: dict[str, str] = {}
    for item in read:
        if not isinstance(item, Curve | Line) or not item.name or getattr(item, "pieces", None):
            continue
        if item.y and not item.x and formula(item.y) == 0:
            axes[item.name] = "x-axis"
        elif item.x and not item.y and formula(item.x, _Y) == 0:
            axes[item.name] = "y-axis"
    if not axes:
        return read
    return [
        item.model_copy(update={"between": [axes.get(n, n) for n in item.between]})
        if isinstance(item, Shade)
        else item
        for item in read
    ]


def _lines_as_curves(scene: Scene) -> None:
    """A picture of lines alone (a triangle's three sides) draws its stated lines as its
    curves, so shading between them holds as between any curves."""
    for name, line in list(scene.lines.items()):
        if line.vertical is None and len(scene.curves) < _MOST_LINE_CURVES:
            expr = line.slope * X + line.offset
            shape = formula_shape(expr, None)
            curve = DrawnCurve(name, line.label, line.color, shape, held=line.held)
            scene.curves[name] = curve
            del scene.lines[name]


def _both_signs(reply: str) -> str:
    """The working with each ± line written twice, once with each sign: "x = ±2" writes both
    -2 and 2."""
    lines = reply.splitlines()
    signed = [line for line in lines if "\u00b1" in line or "\\pm" in line]
    plus = [line.replace("\u00b1", "+").replace("\\pm", "+") for line in signed]
    minus = [line.replace("\u00b1", "-").replace("\\pm", "-") for line in signed]
    return "\n".join([*lines, *plus, *minus])


def written_lines(reply: str) -> tuple[tuple[float | None, float], ...]:
    """The lines the reply's working writes: y = mx + c as (m, c), x = a as (None, a)."""
    found: list[tuple[float | None, float]] = []
    # Read as text: its markup and emphasis off ("**vertical asymptote at $x = 2$**" read
    # as no line, and g03's x = 2 went unlabelled).
    lines = [without_markup(without_emphasis(line)) for line in reply.splitlines()]
    relations = [relation for line in lines for relation in written_relations(line)]
    for lhs, op, rhs in relations:
        if op != "=" or not isinstance(lhs, Symbol) or not rhs.free_symbols <= {_X}:
            continue
        slope = rhs.diff(_X)
        if str(lhs) == "y" and slope.is_number and slope.is_real:
            found.append((float(slope), float(rhs.subs(_X, 0))))
        elif str(lhs) == "x" and rhs.is_number and rhs.is_real:
            found.append((None, float(rhs)))
    return tuple(found)


def _add(item: Any, question: PlotQuestion, scene: Scene) -> None:
    if isinstance(item, Touching):
        plot_marks.touching(item, question, scene)
    elif isinstance(item, Asymptotes):
        plot_marks.asymptotes(item, scene)
    elif isinstance(item, KeyPoints):
        plot_marks.key_points(item, scene)
    elif isinstance(item, Point):
        plot_marks.point(item, question, scene)
    elif isinstance(item, Nearest):
        plot_marks.nearest(item, question, scene)
    elif isinstance(item, Shade):
        plot_regions.shade(item, question, scene)
    elif isinstance(item, Rectangles):
        plot_regions.rectangles(item, question, scene)
    elif isinstance(item, Axis):
        plot_regions.axis(item, question, scene)
    elif isinstance(item, Average):
        plot_volumes.average(item, question, scene)
    elif isinstance(item, Slice):
        plot_volumes.slice_of(item, scene)
