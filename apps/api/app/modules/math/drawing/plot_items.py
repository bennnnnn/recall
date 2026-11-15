"""What a graph's ```draw description may hold (kind "plot"): a closed vocabulary.

Every item names what the picture shows, never where: a curve is the question's formula, a
tangent names its curve and the x where it touches, a shaded region names its two edges and
its bounds. The server checks each against the question (``plot_check``) and works out
every coordinate. Values a description may write are ones the question states, as text
SymPy reads ("-1/2", "pi/2", "e"); one the server finds (a crossing, a turning point) it
writes too, and the check holds it to what the server found.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

_FORMULA_CHARS = 120
_VALUE_CHARS = 24
# A curve, a line or a region named so other items can point at it: "f", "g", "y = 3x".
_REF_CHARS = 24
_MOST_PIECES = 6
_MOST_RECTANGLES = 40
_MOST_SHOWN = 6
_MOST_SHIFTS = 5


def _text(value: object) -> str:
    """A formula or a value written as a number (2, -0.5) is read as its text."""
    if isinstance(value, bool) or value is None:
        return ""
    return str(value).strip() if isinstance(value, str | int | float) else ""


Formula = Annotated[str, BeforeValidator(_text), Field(max_length=_FORMULA_CHARS)]
Value = Annotated[str, BeforeValidator(_text), Field(max_length=_VALUE_CHARS)]
Ref = Annotated[str, BeforeValidator(_text), Field(max_length=_REF_CHARS)]
Pair = tuple[Value, Value]


class _Item(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class Piece(BaseModel):
    """One piece of a function defined in pieces: its formula and where it holds, as the
    question writes it ("-5 < x <= -2", "x = -5", "x != 1")."""

    model_config = ConfigDict(extra="ignore")

    y: Formula
    when: Annotated[str, BeforeValidator(_text), Field(max_length=48)]


class Curve(_Item):
    """y = f(x) (``y``), x = g(y) (``x``), or a function in ``pieces``; drawn on the
    question's own interval when it states one (``domain``). ``y`` may be an antiderivative
    of the question's function, drawn once for each constant in ``shifts`` (F(x) + C)."""

    item: Literal["curve"]
    name: Ref = ""
    y: Formula = ""
    x: Formula = ""
    pieces: list[Piece] = Field(default_factory=list, max_length=_MOST_PIECES)
    domain: Pair | None = None
    shifts: list[Value] = Field(default_factory=list, max_length=_MOST_SHIFTS)


class Line(_Item):
    """A line the question writes: y = mx + c (``y``), x = a (``x``), or the line through
    two points it writes (``through``)."""

    item: Literal["line"]
    name: Ref = ""
    y: Formula = ""
    x: Formula = ""
    through: list[Pair] = Field(default_factory=list, max_length=2)


class Touching(_Item):
    """The tangent or the normal to a curve where x is ``at``."""

    item: Literal["tangent", "normal"]
    to: Ref
    at: Value


class Asymptotes(_Item):
    """A curve's asymptotes, every one SymPy finds: vertical, horizontal and oblique."""

    item: Literal["asymptotes"]
    of: Ref


Feature = Literal["extrema", "inflections", "intercepts", "ends", "crossings"]


class KeyPoints(_Item):
    """A curve's points of the kinds named, found by the server and labelled with their
    coordinates: turning points (cusps and corners too), inflection points, where it meets
    the axes, the ends of its stated interval, where it crosses the other curves."""

    item: Literal["points"]
    of: Ref
    show: list[Feature] = Field(min_length=1, max_length=_MOST_SHOWN)


class Point(_Item):
    """A point the question writes (``at``), or the point on a curve where x is ``x``."""

    item: Literal["point"]
    at: Pair | None = None
    on: Ref = ""
    x: Value = ""


class Nearest(_Item):
    """The points of a curve nearest a point the question writes, joined to it."""

    item: Literal["nearest"]
    on: Ref
    to: Pair


class Shade(_Item):
    """The region between two edges, each a curve or line by name or "x-axis" / "y-axis",
    from ``start`` to ``end`` along x (or along y, ``wrt``). Left out, the bounds are the
    outermost places the edges meet. Three edges: the region the three enclose."""

    item: Literal["shade"]
    between: list[Ref] = Field(min_length=2, max_length=3)
    start: Value = Field(default="", alias="from")
    end: Value = Field(default="", alias="to")
    wrt: Literal["x", "y"] = "x"


class Rectangles(_Item):
    """``n`` rectangles under a curve from ``start`` to ``end``, each as tall as the curve
    at its left end, its right end, its midpoint, or its lowest or highest value."""

    item: Literal["rectangles"]
    under: Ref
    start: Value = Field(alias="from")
    end: Value = Field(alias="to")
    n: int = Field(ge=1, le=_MOST_RECTANGLES)
    rule: Literal["left", "right", "midpoint", "lower", "upper"] = "left"


class Average(_Item):
    """A curve's average value over a stated interval, as a level line across it."""

    item: Literal["average"]
    of: Ref
    start: Value = Field(alias="from")
    end: Value = Field(alias="to")


class AxisNames(_Item):
    """What the axes measure: the question's letters and units ("t (s)", "v (m/s)")."""

    item: Literal["axes"]
    x: Annotated[str, BeforeValidator(_text), Field(max_length=16)] = ""
    y: Annotated[str, BeforeValidator(_text), Field(max_length=16)] = ""


class Slice(_Item):
    """One representative disc, washer or shell of a solid of revolution: a thin strip of
    the shaded region and its turn about the axis, drawn where the server picks."""

    item: Literal["slice"]
    method: Literal["disc", "washer", "shell"]


class Axis(_Item):
    """The axis a region turns about: "x-axis", "y-axis", or a line "y = 2" / "x = -1"."""

    item: Literal["axis"]
    line: Formula


PlotItem = Annotated[
    Curve
    | Line
    | Touching
    | Asymptotes
    | KeyPoints
    | Point
    | Nearest
    | Shade
    | Rectangles
    | Average
    | AxisNames
    | Slice
    | Axis,
    Field(discriminator="item"),
]
