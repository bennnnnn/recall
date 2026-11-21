"""A coordinate plane being drawn: its parts, the view that holds them, the finished spec.

Every coordinate is exact (fractions) until it is drawn; lines that run on for ever (a
mirror line, a perpendicular bisector) are cut to the view once it is known.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from fractions import Fraction

from app.modules.math.schemas.figure import (
    LabelSide,
    PlaneCircle,
    PlanePolygon,
    PlaneRightAngle,
    PlaneRole,
    PlaneSegment,
    PlotPoint,
    PointsGraphSpec,
)

Exact = tuple[Fraction, Fraction]
Float = tuple[float, float]
# The least a plane shows across, and the room kept past its farthest part.
_LEAST_SPAN = 6.0
_ROOM = 0.12
_SIDES: dict[tuple[bool, bool], LabelSide] = {
    (True, True): "ne", (True, False): "nw", (False, True): "se", (False, False): "sw",
}  # fmt: skip


def as_float(point: Exact) -> Float:
    return (float(point[0]), float(point[1]))


@dataclass
class _Line:
    """A line through ``at`` along ``along``, cut to the view when the plane is finished."""

    at: Float
    along: Float
    label: str | None
    role: PlaneRole


@dataclass
class Plane:
    points: list[PlotPoint] = field(default_factory=list)
    segments: list[PlaneSegment] = field(default_factory=list)
    polygons: list[PlanePolygon] = field(default_factory=list)
    circles: list[PlaneCircle] = field(default_factory=list)
    right_angles: list[PlaneRightAngle] = field(default_factory=list)
    lines: list[_Line] = field(default_factory=list)
    names: set[str] = field(default_factory=set)

    def point(
        self, at: Exact, label: str, role: PlaneRole = "shape", side: LabelSide = "ne"
    ) -> None:
        x, y = as_float(at)
        self.points.append(PlotPoint(x=x, y=y, label=label, role=role, side=side))

    def segment(
        self,
        a: Exact,
        b: Exact,
        *,
        role: PlaneRole = "shape",
        label: str | None = None,
        dashed: bool = False,
        arrow: bool = False,
        ticks: int = 0,
    ) -> None:
        if a == b:
            return
        self.segments.append(
            PlaneSegment(
                start=as_float(a), end=as_float(b), label=label, role=role, dashed=dashed,
                arrow=arrow, ticks=ticks,
            )
        )  # fmt: skip

    def line(self, at: Exact, along: Exact, label: str | None, role: PlaneRole) -> None:
        self.lines.append(_Line(as_float(at), as_float(along), label, role))

    def right_angle(self, at: Exact, a: Exact, b: Exact) -> None:
        self.right_angles.append(PlaneRightAngle(at=as_float(at), a=as_float(a), b=as_float(b)))

    def _extent(self) -> list[Float]:
        found: list[Float] = [(0.0, 0.0)]
        found += [(p.x, p.y) for p in self.points]
        found += [end for s in self.segments for end in (s.start, s.end)]
        found += [corner for polygon in self.polygons for corner in polygon.points]
        for circle in self.circles:
            (cx, cy), r = circle.center, circle.radius
            found += [(cx - r, cy - r), (cx + r, cy + r)]
        found += [line.at for line in self.lines]
        return found

    def spec(self) -> PointsGraphSpec:
        x_min, x_max, y_min, y_max = _view(self._extent())
        segments = list(self.segments)
        for line in self.lines:
            cut = _clip(line.at, line.along, (x_min, x_max, y_min, y_max))
            if cut is not None:
                segments.append(
                    PlaneSegment(start=cut[0], end=cut[1], label=line.label, role=line.role)
                )
        return PointsGraphSpec(
            points=self.points,
            x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max,
            segments=segments,
            polygons=self.polygons,
            circles=self.circles,
            right_angles=self.right_angles,
        )  # fmt: skip


def _view(extent: list[Float]) -> tuple[float, float, float, float]:
    """A square view, one unit as long on both axes (a right angle looks right, a circle
    round), holding the origin and every part with room to spare, on whole numbers."""
    xs, ys = [x for x, _ in extent], [y for _, y in extent]
    span = max(max(xs) - min(xs), max(ys) - min(ys), _LEAST_SPAN)
    span += 2 * max(1.0, span * _ROOM)
    centre_x, centre_y = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    x_min, y_min = math.floor(centre_x - span / 2), math.floor(centre_y - span / 2)
    side = math.ceil(span)
    return float(x_min), float(x_min + side), float(y_min), float(y_min + side)


def _clip(
    at: Float, along: Float, view: tuple[float, float, float, float]
) -> tuple[Float, Float] | None:
    """The part of the line through ``at`` along ``along`` inside the view (Liang-Barsky)."""
    x_min, x_max, y_min, y_max = view
    low, high = -math.inf, math.inf
    for start, step, least, most in (
        (at[0], along[0], x_min, x_max),
        (at[1], along[1], y_min, y_max),
    ):
        if step == 0:
            if not least <= start <= most:
                return None
            continue
        one, two = (least - start) / step, (most - start) / step
        low, high = max(low, min(one, two)), min(high, max(one, two))
    if not low < high or not math.isfinite(low) or not math.isfinite(high):
        return None
    return (
        (at[0] + low * along[0], at[1] + low * along[1]),
        (at[0] + high * along[0], at[1] + high * along[1]),
    )


def side_from(point: Exact, centre: tuple[float, float]) -> LabelSide:
    """The side of ``point`` away from ``centre``: where its label clears its shape."""
    dx, dy = float(point[0]) - centre[0], float(point[1]) - centre[1]
    return _SIDES[(dy >= 0, dx >= 0)]


def centroid(points: list[Exact]) -> tuple[float, float]:
    return (
        sum(float(p[0]) for p in points) / len(points),
        sum(float(p[1]) for p in points) / len(points),
    )
