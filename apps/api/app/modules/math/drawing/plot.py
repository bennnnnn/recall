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

from app.modules.math.drawing import plot_marks, plot_regions, plot_volumes
from app.modules.math.drawing.plot_curves import add_curves
from app.modules.math.drawing.plot_draw import draw_plot
from app.modules.math.drawing.plot_items import (
    Asymptotes,
    Average,
    Axis,
    KeyPoints,
    Nearest,
    Point,
    Rectangles,
    Shade,
    Slice,
    Touching,
)
from app.modules.math.drawing.plot_question import PlotQuestion, read_plot_question
from app.modules.math.drawing.plot_scene import Scene
from app.modules.math.schemas.plot import PlotGraphSpec

logger = logging.getLogger(__name__)


def plot_spec(items: list[tuple[str, Any | None]], texts: Sequence[str]) -> PlotGraphSpec | None:
    """The checked graph of ``items`` (``vocabulary.read_items``), or None."""
    question = read_plot_question(texts)
    read = [item for _name, item in items if item is not None]
    scene = Scene()
    add_curves(read, question, scene)
    if not scene.curves:
        return None
    # A slice is cut from a region and turned about an axis: it comes after both.
    for item in sorted(read, key=lambda found: isinstance(found, Slice)):
        try:
            _add(item, question, scene)
        except Exception:  # SymPy's and numpy's own errors included: that item is left out.
            logger.info("plot item %s failed", type(item).__name__, exc_info=True)
    return draw_plot(scene)


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
