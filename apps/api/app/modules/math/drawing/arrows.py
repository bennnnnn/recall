"""Arrows on a figure: a vector's head and an axis's, drawn as two short strokes.

A figure segment's own ``arrows`` are parallel marks at its middle, so a head at the tip is
drawn here, in the plane of the drawing. The phone scales a figure the same way across and
up, so the head keeps its shape.
"""

from __future__ import annotations

import math

from app.modules.math.figure.drawing import Drawing, Point

# The head's strokes turn this far from the shaft.
_TURN = math.radians(25)
# A head is at most this share of its shaft.
_MOST = 0.3


def arrowhead(drawing: Drawing, tail: Point, tip: Point, size: float, tip_name: str) -> None:
    """Two strokes back from ``tip`` (the point named ``tip_name``), ``size`` long at most."""
    dx, dy = tail[0] - tip[0], tail[1] - tip[1]
    shaft = math.hypot(dx, dy)
    if shaft == 0:
        return
    length = min(size, _MOST * shaft)
    for turn in (_TURN, -_TURN):
        cos, sin = math.cos(turn), math.sin(turn)
        end = (
            tip[0] + (dx * cos - dy * sin) / shaft * length,
            tip[1] + (dx * sin + dy * cos) / shaft * length,
        )
        drawing.line(tip_name, drawing.point(end))


def axis(drawing: Drawing, start: Point, tip: Point, name: str, size: float) -> str:
    """An axis from ``start`` to its arrowhead at ``tip``, its letter beside the head."""
    tip_name = drawing.point(tip, name, show=True)
    drawing.line(drawing.point(start), tip_name)
    arrowhead(drawing, start, tip, size, tip_name)
    return tip_name
