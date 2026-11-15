"""What a ```draw description may hold: a closed vocabulary, read item by item.

``kind`` names the picture: "space", a scene in three dimensions (axes, points, vectors,
segments, polygons, a box, a sphere, a plane, an angle), or "shape", a word problem's figure
(a window, a ladder, a tank, a frustum, a cylinder in a cone, a polygon at stated
coordinates). A graph's curves and lines join later as a third kind, "plot", with items of
its own. A description carries no coordinate the question does not state: a shape's parts
are labelled ("r", "2r", "12 m") and the server works out where everything goes.

Each item is read on its own: one the vocabulary does not hold is left out, and keeps its
place and name (``read_items``), so the check can tell when the picture's main object went
with it.
"""

from __future__ import annotations

import json
import math
import re
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
)

DrawKind = Literal["space", "shape"]
ShapeName = Literal[
    "window",
    "rectangle",
    "square",
    "circle",
    "cylinder",
    "cone",
    "sphere",
    "frustum",
    "box",
    "sheet",
    "ladder",
    "tank",
    "inscribed",
    "polygon",
]
_MAX_ITEMS = 16
_LABEL_CHARS = 12
# As the other geometry inputs allow.
_MAX_COORDINATE = 1_000_000.0
# A point's or a vector's name: a letter, then at most two more letters, digits or primes.
_NAME = re.compile(r"^[A-Za-z\u0391-\u03c9][A-Za-z0-9\u2032']{0,2}$")


def _finite[T: tuple[float, ...]](values: T) -> T:
    if not all(math.isfinite(v) and abs(v) <= _MAX_COORDINATE for v in values):
        raise ValueError("coordinates are finite")
    return values


def _name(value: Any) -> str:
    text = str(value or "").strip()
    if not _NAME.match(text):
        raise ValueError("a name is a letter, at most three characters")
    return text


Name = Annotated[str, BeforeValidator(_name)]


def _label(value: Any) -> str:
    """A label too long to be one ("floor diagonal") is no label: the part is still drawn."""
    text = str(value if value is not None else "").strip()
    return text if len(text) <= _LABEL_CHARS else ""


Label = Annotated[str, BeforeValidator(_label)]
Triple = Annotated[tuple[float, float, float], AfterValidator(_finite)]
Pair = Annotated[tuple[float, float], AfterValidator(_finite)]


class _Item(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class Axes(_Item):
    item: Literal["axes"]


class SpacePoint(_Item):
    item: Literal["point"]
    name: Name
    at: Triple
    # Dashed lines down to the xy-plane and across to the axes, locating the point.
    guides: bool = False


class SpaceVector(_Item):
    """An arrow: from the origin (or a named point) to a named point, or by components."""

    item: Literal["vector"]
    name: Name
    start: str = Field(default="", alias="from", max_length=3)
    end: Name | Triple = Field(alias="to")


class SpaceSegment(_Item):
    item: Literal["segment"]
    start: Name = Field(alias="from")
    end: Name = Field(alias="to")
    label: Label = ""


class SpacePolygon(_Item):
    item: Literal["polygon"]
    vertices: list[Name] = Field(min_length=3, max_length=6)


class SpaceBox(_Item):
    """A box from the origin with its edges along x, y and z: its size (x, y, z) as the
    question states it, the corners the reply letters by where they are ({"G": [8, 6, 3]}),
    and diagonals between lettered corners. A letter tied to its corner leaves no doubt
    which diagonal is which (a lettering order would)."""

    item: Literal["box"]
    size: Triple | None = None
    corners: dict[Name, Triple] = Field(default_factory=dict, max_length=8)
    diagonals: list[Annotated[str, Field(min_length=2, max_length=2)]] = Field(
        default_factory=list, max_length=4
    )


class SpaceSphere(_Item):
    item: Literal["sphere"]
    name: str = Field(default="", max_length=3)
    center: Triple | None = None
    # The radius the question states; one the reply worked out ("√5") is checked against
    # the question's own equation instead.
    radius: float | str | None = None
    # The sphere's equation as the question writes it: its centre and radius worked out.
    equation: str = Field(default="", max_length=120)


class SpacePlane(_Item):
    """A patch of the plane through three named points."""

    item: Literal["plane"]
    through: list[Name] = Field(min_length=3, max_length=3)


class SpaceAngle(_Item):
    """The angle at ``at`` between the rays to two named points or vectors."""

    item: Literal["angle"]
    at: Name
    between: list[Name] = Field(min_length=2, max_length=2)
    label: Label = ""


SpaceItem = Annotated[
    Axes
    | SpacePoint
    | SpaceVector
    | SpaceSegment
    | SpacePolygon
    | SpaceBox
    | SpaceSphere
    | SpacePlane
    | SpaceAngle,
    Field(discriminator="item"),
]


class PlanePoint(BaseModel):
    name: str = Field(default="", max_length=3)
    at: Pair


class ShapePart(BaseModel):
    """One shape of a word problem's figure. Its parts' labels are its other keys, by the
    part ("radius": "r", "height": "h", "width": "2r", "length": "12 m"); ``shapes`` names the
    parts each shape has."""

    model_config = ConfigDict(extra="allow")

    item: ShapeName
    # A tank's shape (cone or cylinder), or the shape a cylinder sits inside (cone or sphere).
    container: Literal["cone", "cylinder", "sphere"] | None = None
    # A box with no lid.
    open: bool = False
    # A polygon's corners at the coordinates the question gives.
    vertices: list[PlanePoint] = Field(default_factory=list, max_length=8)

    def labels(self) -> dict[str, str]:
        """Each part's label as written ("" for none)."""
        found: dict[str, str] = {}
        for key, value in (self.model_extra or {}).items():
            if isinstance(value, bool) or not isinstance(value, str | int | float):
                continue
            found[key] = str(value).strip()[:_LABEL_CHARS]
        return found


_SPACE: TypeAdapter[Any] = TypeAdapter(SpaceItem)


class Description(BaseModel):
    kind: DrawKind
    items: list[dict[str, Any]] = Field(min_length=1, max_length=_MAX_ITEMS)


def read_description(body: str) -> Description | None:
    """A ```draw fence's body, or None when it is no description."""
    try:
        return Description.model_validate(json.loads(body))
    except (ValueError, ValidationError):
        return None


def read_items(description: Description) -> list[tuple[str, Any | None]]:
    """Each item in order: what it names itself, and the item, or None when the vocabulary
    does not hold it."""
    read: list[tuple[str, Any | None]] = []
    for raw in description.items:
        name = str(raw.get("item", ""))
        try:
            if description.kind == "space":
                read.append((name, _SPACE.validate_python(raw)))
            else:
                read.append((name, ShapePart.model_validate(raw)))
        except ValidationError:
            read.append((name, None))
    return read
