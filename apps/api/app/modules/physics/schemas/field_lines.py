"""The `field` diagram: electric field lines the server traced, which the phone only draws.

The phone computes no field. It gets the charges (where each sits, its sign, its label),
the plates, every line as a polyline in the picture's units, one arrowhead per line (a
point and the field's direction there) and the neutral points, all worked out by
``physics.field_lines``.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, Field, model_serializer, model_validator

MAX_FIELD_LINES = 64
MAX_LINE_POINTS = 160
MAX_FIELD_POINTS = 2400
MAX_NEUTRAL_POINTS = 4


def _finite_pair(point: list[float], name: str) -> None:
    if len(point) != 2 or not all(math.isfinite(value) for value in point):
        raise ValueError(f"{name} must be a finite [x, y] pair")


class FieldCharge(BaseModel):
    """A point charge: a circle with its sign, and the question's value under it."""

    at: list[float]
    sign: Literal[1, -1]
    # The circle's radius in the picture's units: the lines start and end on it.
    radius: float = Field(gt=0, le=1)
    label: str | None = Field(default=None, max_length=16)

    @model_validator(mode="after")
    def finite(self) -> FieldCharge:
        _finite_pair(self.at, "charge position")
        return self

    @model_serializer(mode="wrap")
    def omit_unlabelled(self, handler: Any) -> Any:
        data = handler(self)
        if isinstance(data, dict) and data.get("label") is None:
            data.pop("label", None)
        return data


class FieldPlate(BaseModel):
    """A charged plate seen edge-on, from ``start`` to ``end``."""

    start: list[float]
    end: list[float]
    sign: Literal[1, -1]

    @model_validator(mode="after")
    def finite(self) -> FieldPlate:
        _finite_pair(self.start, "plate start")
        _finite_pair(self.end, "plate end")
        if self.start == self.end:
            raise ValueError("a plate needs a length")
        return self


class FieldArrow(BaseModel):
    """An arrowhead on a line, pointing the way the field does there."""

    at: list[float]
    dx: float
    dy: float

    @model_validator(mode="after")
    def directed(self) -> FieldArrow:
        _finite_pair(self.at, "arrow position")
        if not (math.isfinite(self.dx) and math.isfinite(self.dy)) or (self.dx, self.dy) == (0, 0):
            raise ValueError("an arrow needs a finite direction")
        return self


class FieldSpec(BaseModel):
    charges: list[FieldCharge] = Field(default_factory=list, max_length=3)
    plates: list[FieldPlate] = Field(default_factory=list, max_length=2)
    lines: list[list[list[float]]] = Field(min_length=1, max_length=MAX_FIELD_LINES)
    arrows: list[FieldArrow] = Field(default_factory=list, max_length=MAX_FIELD_LINES)
    # Where the field is zero: between two like charges, or beyond the smaller of two
    # unlike ones. Three charges in a row have at most four on the row.
    neutral: list[list[float]] = Field(default_factory=list, max_length=MAX_NEUTRAL_POINTS)
    # The part of the question this picture answers: "a" titles it "(a)".
    part: str | None = Field(default=None, pattern=r"^[a-h]$")

    @model_validator(mode="after")
    def drawable(self) -> FieldSpec:
        if bool(self.charges) == bool(self.plates):
            raise ValueError("a field is of point charges or of plates, not both or neither")
        total = 0
        for line in self.lines:
            if not 2 <= len(line) <= MAX_LINE_POINTS:
                raise ValueError("a field line is 2 to 160 points")
            for point in line:
                _finite_pair(point, "line point")
            total += len(line)
        if total > MAX_FIELD_POINTS:
            raise ValueError("too many points to draw")
        for point in self.neutral:
            _finite_pair(point, "neutral point")
        return self

    @model_serializer(mode="wrap")
    def omit_empty(self, handler: Any) -> Any:
        data = handler(self)
        if isinstance(data, dict):
            for key, default in (("charges", []), ("plates", []), ("neutral", []), ("part", None)):
                if data.get(key) == default:
                    data.pop(key, None)
        return data
