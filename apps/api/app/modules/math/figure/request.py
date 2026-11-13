"""What a question asks to see, as a model reads it: the kind of picture and the values the
question states. Only a reading: every number in it is checked against the question
(``grounding``) and the server works out the picture (``build``)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

FigureKind = Literal[
    "none", "polygon", "circle", "lines", "solid", "number_line", "function", "points"
]
# The parts of a figure a measure names. ``side`` is any side; the rest name a part.
MeasureWhat = Literal[
    "side",
    "base",
    "height",
    "leg",
    "hypotenuse",
    "equal_side",
    "parallel_side",
    "diagonal",
    "angle",
    "perimeter",
    "radius",
    "diameter",
    "chord",
    "length",
    "width",
    "edge",
    "slant_height",
]
_KINDS = ("none", "polygon", "circle", "lines", "solid", "number_line", "function", "points")


class Measure(BaseModel):
    """One value the question states: what it measures, the letters naming it ("AB",
    "A"), and the number as written."""

    what: MeasureWhat
    name: str = Field(default="", max_length=8)
    value: float = Field(gt=0, le=1_000_000)


class NamedPoint(BaseModel):
    name: str = Field(default="", max_length=4)
    x: float = Field(ge=-1_000_000, le=1_000_000)
    y: float = Field(ge=-1_000_000, le=1_000_000)


class FigureRequest(BaseModel):
    kind: FigureKind = "none"
    # The shape by its plain name ("parallelogram", "right_triangle", "cylinder",
    # "parallel_lines"): each kind's builder reads its own names and draws nothing for one
    # it does not know.
    shape: str = Field(default="", max_length=32)
    # The letters naming the vertices in order ("ABCD"), "" when the question names none.
    vertices: str = Field(default="", max_length=8)
    # The letter of a circle's centre, or of where a shape's diagonals meet ("O").
    center: str = Field(default="", max_length=4)
    measures: list[Measure] = Field(default_factory=list, max_length=12)
    # A regular polygon's number of sides.
    sides: int | None = Field(default=None, ge=3, le=12)
    # Extra parts to draw: "diagonals", "radius", "diameter", "height", "net".
    parts: list[str] = Field(default_factory=list, max_length=6)
    # A shape drawn inside a circle with its corners on it, or around it.
    inscribed: str = Field(default="", max_length=32)
    circumscribed: str = Field(default="", max_length=32)
    unit: str = Field(default="", max_length=12)
    # A number line: the numbers as written ("-5/2", "1.5"), or an inequality copied.
    numbers: list[str] = Field(default_factory=list, max_length=10)
    inequality: str = Field(default="", max_length=80)
    # A function graph: y = expr in ``variable``, over the stated range, axis names.
    expr: str = Field(default="", max_length=120)
    variable: str = Field(default="x", max_length=4)
    x_min: float | None = None
    x_max: float | None = None
    x_label: str = Field(default="", max_length=32)
    y_label: str = Field(default="", max_length=32)
    # Points on a coordinate plane.
    points: list[NamedPoint] = Field(default_factory=list, max_length=12)
    quadrants: bool = False

    @field_validator("kind", mode="before")
    @classmethod
    def _kind(cls, value: Any) -> str:
        text = str(value or "").strip().lower()
        return text if text in _KINDS else "none"

    @field_validator("shape", "inscribed", "circumscribed", mode="before")
    @classmethod
    def _name(cls, value: Any) -> str:
        return " ".join(str(value or "").strip().lower().replace("-", " ").split()).replace(
            " ", "_"
        )

    @field_validator("parts", mode="before")
    @classmethod
    def _parts(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip().lower() for item in value if str(item).strip()]

    @field_validator("measures", mode="before")
    @classmethod
    def _measures(cls, value: Any) -> list[Any]:
        """A measure the reader named oddly is left out, never the whole reading."""
        if not isinstance(value, list):
            return []
        kept: list[Any] = []
        for item in value:
            try:
                kept.append(Measure.model_validate(item))
            except ValueError:
                continue
        return kept

    def given(self, what: str) -> list[Measure]:
        return [measure for measure in self.measures if measure.what == what]

    def first(self, *whats: str) -> float | None:
        for what in whats:
            found = self.given(what)
            if found:
                return found[0].value
        return None

    def has_part(self, part: str) -> bool:
        return any(part in item for item in self.parts)
