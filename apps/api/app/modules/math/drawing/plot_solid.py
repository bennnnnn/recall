"""The solid a shaded region sweeps about its axis, sketched on the region's own graph.

"Sketch the region and the solid" (u5-071, u5-082): the textbook's picture is the region,
its mirror across the axis of revolution, and the circle each end of the solid turns
through, seen at a slant as an ellipse. All of it comes from what the server already
checked: the shaded region (the question's curves, on its interval) and the axis the
question names. Nothing the reply writes is drawn here, so nothing here can be wrong
where the region is right. A part of the region on both sides of the axis sweeps a solid
that folds over itself, and none is sketched; parts on either side (x³ on [-1, 2], cut at
0) each sweep their own.
"""

from __future__ import annotations

import math

import numpy as np

from app.modules.math.drawing.plot_scene import DrawnRegion, Scene

# An end's ellipse as wide as this share of its radius, on axes of equal scale: a circle
# seen from a little above. The window's two scales are not yet known; the region's
# extents along and across the axis stand in for them.
_SLANT = 0.3
_ELLIPSE_POINTS = 48
# Points within this share of the region's length of an end are at that end.
_AT_AN_END = 1e-3
_SOLID_COLOR = 0
# An end where the region's width is under this share of its width a little way in (this
# share of its length) is a point its edges meet at, not a washer's two edges.
_POINT_WIDTH, _WAY_IN = 0.25, 0.05


def _axis(scene: Scene) -> tuple[str, float] | None:
    """The axis of revolution: ("y", k) for the line y = k, ("x", h) for x = h."""
    for mark in scene.marks:
        if mark.role == "axis":
            if mark.vertical is not None:
                return "x", float(mark.vertical)
            return "y", float(mark.offset)
    return None


def _ellipse(
    along: float, level: float, half_along: float, radius: float
) -> list[tuple[float, float]]:
    turns = np.linspace(0.0, 2 * math.pi, _ELLIPSE_POINTS, endpoint=False)
    return [(along + half_along * math.cos(t), level + radius * math.sin(t)) for t in turns]


def _folds(flat: list[list[tuple[float, float]]], reach: float) -> bool:
    """Some of the region lies on each side of the axis at the same place along it: one
    part across it, or two parts on either side over the same stretch (x² on [-1, 2] about
    the y-axis, cut at 0 into [-1, 0] and [0, 2]). Parts on either side over different
    stretches (x³ on [-1, 2] about the x-axis) each sweep their own solid."""
    tol = 1e-6 * reach
    spans: list[tuple[int, float, float]] = []
    for part in flat:
        sides = [d for _, d in part]
        if min(sides) < -tol and max(sides) > tol:
            return True
        alongs = [a for a, _ in part]
        spans.append((1 if max(sides) > tol else -1, min(alongs), max(alongs)))
    for i, (side, low, high) in enumerate(spans):
        for other, low2, high2 in spans[i + 1 :]:
            overlap = min(high, high2) - max(low, low2)
            if side != other and overlap > 1e-6 * max(1.0, high - low, high2 - low2):
                return True
    return False


def _narrows_to_a_point(flat: list[list[tuple[float, float]]], end: float, length: float) -> bool:
    """The region's two edges meet at ``end``: its width across there is a small share of
    its width a little way in. A thin washer (y = 10 and y = 9.5) keeps its width all along."""

    def width(reach: float) -> float:
        across = [d for part in flat for a, d in part if abs(a - end) <= reach]
        return max(across) - min(across) if across else 0.0

    inside = width(_WAY_IN * length)
    return inside > 0 and width(_AT_AN_END * length) <= _POINT_WIDTH * inside


def solid_of(scene: Scene) -> None:
    """The mirror of each shaded part across the axis, and an ellipse at each end of the
    solid with the radius the region reaches there (a cone's point has none)."""
    axis = _axis(scene)
    parts = [region for region in scene.regions if region.kind == "shade"]
    if axis is None or not parts:
        return
    letter, level = axis
    # In (along, across) coordinates: along the axis, and the signed distance from it.
    if letter == "y":
        flat = [[(x, y - level) for x, y in part.points] for part in parts]
    else:
        flat = [[(y, x - level) for x, y in part.points] for part in parts]
    distances = [d for part in flat for _, d in part]
    reach = max(abs(d) for d in distances)
    if not reach or not all(math.isfinite(d) for d in distances):
        return
    if _folds(flat, reach):
        return  # the region on both sides of its axis at once: the solid folds over itself
    alongs = [a for part in flat for a, _ in part]
    low, high = min(alongs), max(alongs)
    length = high - low
    if length <= 0:
        return
    shapes = [[(a, -d) for a, d in part] for part in flat]
    near = _AT_AN_END * length
    for end in (low, high):
        radii = [abs(d) for part in flat for a, d in part if abs(a - end) <= near]
        outer = max(radii, default=0.0)
        if outer <= 1e-6 * reach:
            continue  # a point: a cone's tip
        # On equal scales an end circle is _SLANT as wide as it is tall; the region is
        # ``length`` along and twice ``reach`` across, so its width in the along unit is:
        half_along = _SLANT * outer * length / (2 * reach)
        shapes.append(_ellipse(end, 0.0, half_along, outer))
        inner = min(radii, default=0.0)
        if _narrows_to_a_point(flat, end, length):
            # The region's edges meet there, off the axis (4 - x² at its top, about x = 3):
            # one circle, no hole between radii a sample apart.
            outer = (outer + inner) / 2
            half_along = _SLANT * outer * length / (2 * reach)
            shapes[-1] = _ellipse(end, 0.0, half_along, outer)
        elif inner > 1e-6 * reach:
            shapes.append(_ellipse(end, 0.0, half_along * inner / outer, inner))  # a washer's hole
    for shape in shapes:
        if letter == "y":
            points = [(a, level + d) for a, d in shape]
        else:
            points = [(level + d, a) for a, d in shape]
        scene.regions.append(DrawnRegion(points, kind="mirror", color=_SOLID_COLOR))
