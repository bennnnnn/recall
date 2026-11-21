"""What a question asks to see, as a model reads it: the kind of picture and the values the
question states. Only a reading: every number in it is checked against the question
(``grounding``) and the server works out the picture (``build``)."""

from __future__ import annotations

import math
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.math.drawing.plot_reading import number

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
    # An isosceles triangle's angle where its equal sides meet, and one of the two others.
    "apex_angle",
    "base_angle",
    "perimeter",
    "radius",
    "diameter",
    "chord",
    "length",
    "width",
    "edge",
    "slant_height",
    # A scene of heights and distances: the distance along the ground (or the water) from
    # the foot of what stands up, the distance between two points the angles are seen from,
    # an object's shadow, and an angle measured from the vertical (a ladder's with its wall).
    "distance",
    "gap",
    "shadow",
    "angle_from_vertical",
    # A polygon's angle inside at a corner, and outside it (one side drawn on past it).
    "interior_angle",
    "exterior_angle",
]
# The measures that are angles, in degrees; every other one is a length.
ANGLE_WHATS = frozenset(
    {
        "angle",
        "apex_angle",
        "base_angle",
        "angle_from_vertical",
        "interior_angle",
        "exterior_angle",
    }
)
_KINDS = ("none", "polygon", "circle", "lines", "solid", "number_line", "function", "points")


# A word naming an object rather than points is this long at least ("cone", "ship").
_WORD = 3
_LEADING = re.compile(r"\s*\d+(?:\.\d+)?")


class Measure(BaseModel):
    """One value the question states: what it measures, the letters naming it ("AB",
    "A"), and the number as written."""

    what: MeasureWhat
    name: str = Field(default="", max_length=8)
    value: float = Field(gt=0, le=1_000_000)
    # Which part of a figure of two the value belongs to ("cone", "semicircle", "tree"):
    # the attached shape's name, an object's, or "second"; "" for the main shape.
    of: str = Field(default="", max_length=16)

    @model_validator(mode="before")
    @classmethod
    def _named_object(cls, data: Any) -> Any:
        """A measure named by a word ("lighthouse", "cone") names no points: the word says
        what the value is of. A value written with its unit ("50 m", "35°") is its number.
        Either read otherwise lost the measure, and the picture a stated value."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        name = str(data.get("name") or "").strip()
        if len(name) >= _WORD and name.isalpha() and name.islower():
            data["name"] = ""
            data["of"] = data.get("of") or name
        value = data.get("value")
        if isinstance(value, str) and (found := _LEADING.match(value)):
            data["value"] = found.group()
        return data

    @field_validator("of", mode="before")
    @classmethod
    def _of(cls, value: Any) -> str:
        text = " ".join(str(value or "").strip().lower().replace("-", " ").split())
        return text.replace(" ", "_")[:16]


class AngleTerm(BaseModel):
    """An angle the question writes with a letter, copied as written ("2x", "x + 20"), and
    the letters naming it ("B", "AOC") or ""."""

    term: str = Field(min_length=1, max_length=16)
    name: str = Field(default="", max_length=4)


class NamedPoint(BaseModel):
    name: str = Field(default="", max_length=4)
    x: float = Field(ge=-1_000_000, le=1_000_000)
    y: float = Field(ge=-1_000_000, le=1_000_000)


# The longest range end kept as written ("-π/2", "2*pi", "e^2"): a longer one is no end.
_BOUND_CHARS = 24


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
    # The letter where an isosceles triangle's equal sides meet ("AB = AC": "A").
    apex: str = Field(default="", max_length=1)
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
    # Only the whole numbers that meet the inequality are asked for ("the integers n with
    # -3 < n <= 2"): each is marked, the line between them is not shaded.
    integers: bool = False
    # A function graph: y = expr in ``variable``, over the stated range, axis names.
    expr: str = Field(default="", max_length=120)
    variable: str = Field(default="x", max_length=4)
    # Each end as written ("-3", "2π", "1/e"): read to a number in the SymPy pool alone
    # (``bounds``), never while the reply's read is validated on the event loop.
    x_min: float | str | None = None
    x_max: float | str | None = None
    x_label: str = Field(default="", max_length=32)
    y_label: str = Field(default="", max_length=32)
    # Points on a coordinate plane.
    points: list[NamedPoint] = Field(default_factory=list, max_length=12)
    quadrants: bool = False
    # A second shape joined to the first ("semicircle" on a rectangle's side, "triangle" on
    # its top, "rectangle" for an L-shape, "cone" on a hemisphere, "hemisphere" on a
    # cylinder): ``shape`` is the main one, and each measure says which it is ``of``.
    attached: str = Field(default="", max_length=32)
    # Angles written with a letter ("x", "2x", "x + 20"): the server solves the letter
    # where the angles' sum decides it and draws their sizes, labelled as written.
    angle_terms: list[AngleTerm] = Field(default_factory=list, max_length=6)

    @field_validator("kind", mode="before")
    @classmethod
    def _kind(cls, value: Any) -> str:
        text = str(value or "").strip().lower()
        return text if text in _KINDS else "none"

    @field_validator("shape", "inscribed", "circumscribed", "attached", mode="before")
    @classmethod
    def _name(cls, value: Any) -> str:
        return " ".join(str(value or "").strip().lower().replace("-", " ").split()).replace(
            " ", "_"
        )

    @field_validator("x_min", "x_max", mode="before")
    @classmethod
    def _bound(cls, value: Any) -> float | str | None:
        """A range's end as the question writes it ("-3" with its minus sign, "-1/2", "2π",
        "1/e", "e²"), kept as written; one that is no number or text is left out, never the
        whole reading (12 of 98 Unit 5 turns lost theirs, 2026-11-16)."""
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, int | float):
            return float(value) if math.isfinite(value) else None
        text = str(value).strip()
        return text if 0 < len(text) <= _BOUND_CHARS else None

    def bounds(self) -> tuple[float | None, float | None]:
        """The range's ends as numbers, each read by the drawing check's own number reader
        (SymPy: call it in the SymPy pool only); one it cannot read is None."""
        return _read_bound(self.x_min), _read_bound(self.x_max)

    @field_validator("apex", mode="before")
    @classmethod
    def _letter(cls, value: Any) -> str:
        letter = str(value or "").strip()[:1]
        return letter if letter.isalpha() else ""

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

    @field_validator("angle_terms", mode="before")
    @classmethod
    def _terms(cls, value: Any) -> list[Any]:
        """A term the reader wrote oddly is left out, never the whole reading."""
        if not isinstance(value, list):
            return []
        kept: list[Any] = []
        for item in value:
            try:
                kept.append(AngleTerm.model_validate(item))
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


def _read_bound(value: float | str | None) -> float | None:
    if value is None or isinstance(value, float):
        return value
    read = number(value)
    found = None if read is None else float(read)
    return found if found is not None and math.isfinite(found) else None
