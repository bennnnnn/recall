"""The pictures the server draws from a question's own values (``math/figure``).

A ```geometry ``figure`` is a plane drawing in the question's units: named points, the
segments between them, circle and ellipse arcs, angle marks and lightly filled faces. The
server works out every coordinate; the phone only fits the drawing to the card and places
the labels. A ```graph ``points`` plot is lettered points on a coordinate plane, and a
number line may carry labelled marks for the numbers it shows.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# The largest coordinate a drawing may hold: as the other geometry inputs allow.
_MAX_COORDINATE = 1_000_000.0
_LABEL_CHARS = 24


def _finite(*values: float) -> bool:
    return all(math.isfinite(value) and abs(value) <= _MAX_COORDINATE for value in values)


class FigurePoint(BaseModel):
    name: str = Field(min_length=1, max_length=8)
    x: float
    y: float
    # The name is drawn beside the point (a vertex the question letters).
    show: bool = False
    # A small filled dot: a circle's centre, a point on a line.
    dot: bool = False


class FigureSegment(BaseModel):
    a: str = Field(min_length=1, max_length=8)
    b: str = Field(min_length=1, max_length=8)
    label: str | None = Field(default=None, max_length=_LABEL_CHARS)
    # A hidden edge of a solid, a height or a construction line.
    dashed: bool = False
    # Marks on sides of equal length, and on lines that are parallel.
    ticks: int = Field(default=0, ge=0, le=3)
    arrows: int = Field(default=0, ge=0, le=3)
    # Where along the segment its label sits: two diagonals crossing at their middles
    # label each a little way from the crossing.
    label_at: float = Field(default=0.5, ge=0.1, le=0.9)


class FigureArc(BaseModel):
    """An arc of an axis-aligned ellipse about a point; a circle has ``rx == ry``. Angles
    in degrees, counterclockwise from the positive x-axis."""

    center: str = Field(min_length=1, max_length=8)
    rx: float = Field(gt=0, le=_MAX_COORDINATE)
    ry: float = Field(gt=0, le=_MAX_COORDINATE)
    start: float = Field(default=0.0, ge=-360, le=360)
    end: float = Field(default=360.0, ge=-360, le=720)
    dashed: bool = False


class FigureAngle(BaseModel):
    """The angle at ``at`` between the rays to ``a`` and ``b`` (the one under 180°)."""

    at: str = Field(min_length=1, max_length=8)
    a: str = Field(min_length=1, max_length=8)
    b: str = Field(min_length=1, max_length=8)
    label: str | None = Field(default=None, max_length=_LABEL_CHARS)
    right: bool = False


class FigureSpec(BaseModel):
    type: Literal["figure"] = "figure"
    # What is drawn ("parallelogram", "cube_net"): the trace's and the tests' name for it.
    shape: str = Field(min_length=1, max_length=32)
    points: list[FigurePoint] = Field(min_length=1, max_length=80)
    segments: list[FigureSegment] = Field(default_factory=list, max_length=120)
    arcs: list[FigureArc] = Field(default_factory=list, max_length=16)
    angles: list[FigureAngle] = Field(default_factory=list, max_length=16)
    faces: list[list[str]] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def drawable(self) -> FigureSpec:
        names = [point.name for point in self.points]
        if len(set(names)) != len(names):
            raise ValueError("figure point names must be unique")
        if not all(_finite(point.x, point.y) for point in self.points):
            raise ValueError("figure points must be finite")
        known = set(names)
        used = [name for seg in self.segments for name in (seg.a, seg.b)]
        used += [arc.center for arc in self.arcs]
        used += [name for angle in self.angles for name in (angle.at, angle.a, angle.b)]
        used += [name for face in self.faces for name in face]
        if not set(used) <= known:
            raise ValueError("figure parts must name its points")
        if any(seg.a == seg.b for seg in self.segments):
            raise ValueError("a segment joins two points")
        if not (self.segments or self.arcs):
            raise ValueError("a figure draws something")
        return self


class PlotPoint(BaseModel):
    x: float
    y: float
    label: str = Field(min_length=1, max_length=_LABEL_CHARS)


class PointsGraphSpec(BaseModel):
    """Points plotted on a coordinate plane, each with its letter and coordinates."""

    type: Literal["points"] = "points"
    title: str = Field(default="", max_length=64)
    points: list[PlotPoint] = Field(min_length=1, max_length=12)
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    # The quadrants' numerals (I to IV), when the question asks which quadrant.
    quadrants: bool = False

    @model_validator(mode="after")
    def in_view(self) -> PointsGraphSpec:
        if not _finite(self.x_min, self.x_max, self.y_min, self.y_max):
            raise ValueError("points graph needs finite bounds")
        if self.x_max <= self.x_min or self.y_max <= self.y_min:
            raise ValueError("points graph needs ordered bounds")
        for point in self.points:
            inside = self.x_min <= point.x <= self.x_max and self.y_min <= point.y <= self.y_max
            if not (_finite(point.x, point.y) and inside):
                raise ValueError("every plotted point is in view")
        return self


class NumberLineMark(BaseModel):
    """A number shown on a number line, labelled as the question writes it."""

    x: float
    # On the line: the phone reads a number line's marks as it reads a graph's, at (x, y).
    y: float = 0.0
    label: str = Field(min_length=1, max_length=_LABEL_CHARS)

    @model_validator(mode="after")
    def finite(self) -> NumberLineMark:
        if not _finite(self.x):
            raise ValueError("a number line mark is finite")
        return self
