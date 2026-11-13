"""A circle and its parts from the values a question states: a radius or diameter drawn and
labelled, a chord at its true distance from the centre, a shape drawn inside it with its
corners on the circle, or around it with its sides touching."""

from __future__ import annotations

import math

from app.modules.math.figure.drawing import Drawing, length_label, polar
from app.modules.math.figure.quads import POLYGON_SIDES
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec

_RADIUS = 3.0
# Where a drawn radius points when nothing else places it.
_RADIUS_TURN = 35.0
_TOLERANCE = 1e-6


def _corners_count(request: FigureRequest, name: str) -> int | None:
    if not name:
        return None
    if name in {"regular_polygon", "polygon"}:
        return request.sides
    if name in {"equilateral_triangle", "triangle"}:
        return 3
    return POLYGON_SIDES.get(name.removeprefix("regular_"))


def _turns(count: int) -> list[float]:
    """A polygon's corner directions: a flat bottom side, a point on top when odd."""
    first = 90.0 if count % 2 else 90.0 + 180.0 / count
    return [first + k * 360.0 / count for k in range(count)]


def _letters(request: FigureRequest, count: int) -> list[str]:
    letters = request.vertices.strip()
    if len(letters) == count and len(set(letters)) == count and letters.isalpha():
        return list(letters)
    return []


def build_circle(request: FigureRequest) -> FigureSpec | None:
    radius = request.first("radius")
    diameter = request.first("diameter")
    chord = request.first("chord")
    if radius is not None and diameter is not None and abs(2 * radius - diameter) > _TOLERANCE:
        return None
    size = radius or (diameter / 2 if diameter is not None else None)
    if chord is not None and size is not None and chord > 2 * size + _TOLERANCE:
        return None
    r = size or (max(_RADIUS, chord * 0.75) if chord is not None else _RADIUS)
    drawing = Drawing("circle")
    letter = request.center.strip()[:1]
    center = drawing.point(
        (0.0, 0.0), letter if letter.isalpha() else "", show=letter.isalpha(), dot=True
    )
    drawing.arc(center, r)
    unit = request.unit
    radius_label = length_label(radius, unit) if radius is not None else None
    inside = _corners_count(request, request.inscribed)
    around = _corners_count(request, request.circumscribed)
    if chord is not None:
        _chord(drawing, center, r, chord, radius_label, unit, request)
    elif inside is not None:
        _inscribed(drawing, center, r, inside, radius_label, request)
    elif radius is not None or request.has_part("radius"):
        end = drawing.point(polar(r, _RADIUS_TURN))
        drawing.line(center, end, radius_label)
    if around is not None:
        _around(drawing, r, around, request)
    if diameter is not None or request.has_part("diameter"):
        left, right = drawing.point(polar(r, 180.0)), drawing.point(polar(r, 0.0))
        label = length_label(diameter, unit) if diameter is not None else None
        # Clear of the centre's dot and letter.
        drawing.line(left, right, label, label_at=0.75)
    drawing.shape = "circle_" + (
        "chord" if chord else request.inscribed or request.circumscribed or "parts"
    )
    return drawing.spec()


def _chord(
    drawing: Drawing,
    center: str,
    r: float,
    chord: float,
    radius_label: str | None,
    unit: str,
    request: FigureRequest,
) -> None:
    """The chord below the centre at its distance, the radius to its end, and the dashed
    perpendicular from the centre that halves it."""
    half = chord / 2
    depth = math.sqrt(max(0.0, r * r - half * half))
    names = _letters(request, 2)
    left = drawing.point((-half, -depth), names[0] if names else "", show=bool(names))
    right = drawing.point((half, -depth), names[1] if names else "", show=bool(names))
    drawing.line(left, right, length_label(chord, unit))
    drawing.line(center, right, radius_label)
    if depth > _TOLERANCE:
        foot = drawing.point((0.0, -depth))
        drawing.line(center, foot, dashed=True)
        drawing.angle(foot, right, center, right=True)


def _inscribed(
    drawing: Drawing,
    center: str,
    r: float,
    count: int,
    radius_label: str | None,
    request: FigureRequest,
) -> None:
    names = _letters(request, count)
    corners = [
        drawing.point(polar(r, turn), names[i] if names else "", show=bool(names))
        for i, turn in enumerate(_turns(count))
    ]
    drawing.outline(corners)
    for i in range(count):
        drawing.label_side(corners[i], corners[(i + 1) % count], None, ticks=1)
    drawing.line(center, corners[0], radius_label, dashed=radius_label is None)


def _around(drawing: Drawing, r: float, count: int, request: FigureRequest) -> None:
    reach = r / math.cos(math.pi / count)
    names = [] if request.inscribed else _letters(request, count)
    corners = [
        drawing.point(polar(reach, turn), names[i] if names else "", show=bool(names))
        for i, turn in enumerate(_turns(count))
    ]
    drawing.outline(corners, face=False)
