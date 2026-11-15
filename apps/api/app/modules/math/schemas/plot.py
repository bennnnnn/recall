"""A ```graph ``plot``: a graph the server drew from a checked ```draw description.

Every coordinate is the server's: curves sampled and split where they break, lines cut to
the window, shaded regions as polygons, points with the labels the server wrote. The phone
draws it as it is (``apps/mobile/lib/math/plotGraph.ts``) and works nothing out.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_LABEL_CHARS = 48
Coordinate = tuple[float, float]


def _finite(point: Coordinate) -> Coordinate:
    if not all(math.isfinite(value) for value in point):
        raise ValueError("plot coordinates are finite")
    return point


class PlotCurve(BaseModel):
    label: str = Field(default="", max_length=_LABEL_CHARS)
    # Each piece drawn as its own line: a curve never joins across a break.
    segments: list[list[Coordinate]] = Field(min_length=1, max_length=24)
    color: int = Field(default=0, ge=0, le=5)


class PlotLine(BaseModel):
    start: Coordinate
    end: Coordinate
    # "line": a stated line, a tangent or a normal; "asymptote": dashed, never a curve's;
    # "axis": the axis a region turns about; "segment": a distance, joined end to end.
    role: Literal["line", "asymptote", "axis", "segment"] = "line"
    label: str = Field(default="", max_length=_LABEL_CHARS)
    color: int = Field(default=0, ge=0, le=5)

    _points = field_validator("start", "end")(_finite)


class PlotRegion(BaseModel):
    points: list[Coordinate] = Field(min_length=3, max_length=600)
    # "shade": an area between two edges; "strip": a Riemann rectangle or a slice of a
    # solid, outlined; "mirror": a slice turned about its axis, outlined dashed.
    kind: Literal["shade", "strip", "mirror"] = "shade"
    color: int = Field(default=0, ge=0, le=5)


class PlotPoint(BaseModel):
    x: float
    y: float
    # An open circle: a hole, or the end of a piece that leaves its end out.
    open: bool = False
    label: str = Field(default="", max_length=_LABEL_CHARS)
    color: int = Field(default=0, ge=0, le=5)


class PlotGraphSpec(BaseModel):
    type: Literal["plot"] = "plot"
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    # One unit as long on both axes: a normal looks perpendicular, a distance true.
    equal: bool = False
    x_label: str = Field(default="x", max_length=16)
    y_label: str = Field(default="y", max_length=16)
    curves: list[PlotCurve] = Field(default_factory=list, max_length=6)
    lines: list[PlotLine] = Field(default_factory=list, max_length=16)
    regions: list[PlotRegion] = Field(default_factory=list, max_length=48)
    points: list[PlotPoint] = Field(default_factory=list, max_length=24)
