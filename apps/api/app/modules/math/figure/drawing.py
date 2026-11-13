"""A figure being drawn: points, the lines between them and their labels, in one place.

Every builder draws through this, so a figure's parts always name points it holds and the
labels read one way: a length with the question's unit ("9 cm"), an angle in degrees.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.modules.math.schemas.figure import (
    FigureAngle,
    FigureArc,
    FigurePoint,
    FigureSegment,
    FigureSpec,
)

Point = tuple[float, float]


def number_text(value: float) -> str:
    """A value as a textbook prints it: 9, 2.5, 0.333 (never 9.0)."""
    rounded = round(value, 3)
    return f"{rounded:g}" if abs(rounded) < 1e6 else f"{rounded:.0f}"


def length_label(value: float, unit: str) -> str:
    return f"{number_text(value)} {unit}".strip()


def angle_label(degrees: float) -> str:
    return f"{number_text(degrees)}°"


@dataclass
class Drawing:
    shape: str
    points: list[FigurePoint] = field(default_factory=list)
    segments: list[FigureSegment] = field(default_factory=list)
    arcs: list[FigureArc] = field(default_factory=list)
    angles: list[FigureAngle] = field(default_factory=list)
    faces: list[list[str]] = field(default_factory=list)

    def point(self, xy: Point, name: str = "", *, show: bool = False, dot: bool = False) -> str:
        """The point's name; an unnamed one gets a name no question uses ("_3")."""
        label = name or f"_{len(self.points)}"
        self.points.append(FigurePoint(name=label, x=xy[0], y=xy[1], show=show, dot=dot))
        return label

    def corner(self, xy: Point) -> str:
        """The point at ``xy``: the one already there when a net's faces share it."""
        for point in self.points:
            if abs(point.x - xy[0]) < 1e-9 and abs(point.y - xy[1]) < 1e-9:
                return point.name
        return self.point(xy)

    def edge(self, a: Point, b: Point, label: str | None = None) -> None:
        """A side between two corners, drawn once however many faces share it."""
        start, end = self.corner(a), self.corner(b)
        segment = self.side_of(start, end)
        if segment is None:
            self.line(start, end, label)
        elif label is not None:
            segment.label = label

    def at(self, name: str) -> Point:
        for point in self.points:
            if point.name == name:
                return (point.x, point.y)
        raise KeyError(name)

    def line(
        self,
        a: str,
        b: str,
        label: str | None = None,
        *,
        dashed: bool = False,
        ticks: int = 0,
        arrows: int = 0,
        label_at: float = 0.5,
    ) -> None:
        self.segments.append(
            FigureSegment(
                a=a, b=b, label=label, dashed=dashed, ticks=ticks, arrows=arrows, label_at=label_at
            )
        )

    def outline(self, names: list[str], *, face: bool = True) -> None:
        """A closed polygon through ``names`` in order, lightly filled when ``face``."""
        for i, name in enumerate(names):
            self.line(name, names[(i + 1) % len(names)])
        if face:
            self.faces.append(list(names))

    def arc(
        self,
        center: str,
        rx: float,
        ry: float | None = None,
        *,
        start: float = 0.0,
        end: float = 360.0,
        dashed: bool = False,
    ) -> None:
        self.arcs.append(
            FigureArc(
                center=center,
                rx=rx,
                ry=rx if ry is None else ry,
                start=start,
                end=end,
                dashed=dashed,
            )
        )

    def angle(
        self, at: str, a: str, b: str, label: str | None = None, *, right: bool = False
    ) -> None:
        self.angles.append(FigureAngle(at=at, a=a, b=b, label=label, right=right))

    def side_of(self, a: str, b: str) -> FigureSegment | None:
        for segment in self.segments:
            if {segment.a, segment.b} == {a, b}:
                return segment
        return None

    def label_side(self, a: str, b: str, label: str | None, *, ticks: int = 0) -> None:
        """Set the label (and equal-length marks) of the side already drawn from a to b."""
        segment = self.side_of(a, b)
        if segment is None:
            return
        if label is not None:
            segment.label = label
        if ticks:
            segment.ticks = ticks

    def spec(self) -> FigureSpec:
        return FigureSpec(
            shape=self.shape,
            points=self.points,
            segments=self.segments,
            arcs=self.arcs,
            angles=self.angles,
            faces=self.faces,
        )


def polar(radius: float, degrees: float, center: Point = (0.0, 0.0)) -> Point:
    turn = math.radians(degrees)
    return (center[0] + radius * math.cos(turn), center[1] + radius * math.sin(turn))


def distance(p: Point, q: Point) -> float:
    return math.hypot(q[0] - p[0], q[1] - p[1])


def angle_at(vertex: Point, a: Point, b: Point) -> float:
    """The angle at ``vertex`` between the rays to a and b, in degrees (0 to 180)."""
    ax, ay = a[0] - vertex[0], a[1] - vertex[1]
    bx, by = b[0] - vertex[0], b[1] - vertex[1]
    norm = math.hypot(ax, ay) * math.hypot(bx, by)
    if norm == 0:
        return 0.0
    cosine = max(-1.0, min(1.0, (ax * bx + ay * by) / norm))
    return math.degrees(math.acos(cosine))
