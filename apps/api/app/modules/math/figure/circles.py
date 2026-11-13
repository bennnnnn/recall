"""A circle and its parts from the values a question states: a radius or diameter drawn and
labelled, a chord at its true distance from the centre, a polygon drawn as stated with the
circle through its corners (inscribed in the circle) or touching its sides (around it)."""

from __future__ import annotations

import math

from app.modules.math.figure.drawing import Drawing, Point, length_label, polar
from app.modules.math.figure.polygon import build_polygon
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec

_RADIUS = 3.0
# Where a drawn radius points when nothing else places it.
_RADIUS_TURN = 35.0
_TOLERANCE = 1e-6
_CIRCLE_PARTS = frozenset({"radius", "diameter", "chord"})


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
    shape = request.inscribed or request.circumscribed
    if shape:
        if chord is not None or (request.inscribed and request.circumscribed):
            return None
        return _with_polygon(request, size)
    if chord is not None and size is not None and chord > 2 * size + _TOLERANCE:
        return None
    r = size or (max(_RADIUS, chord * 0.75) if chord is not None else _RADIUS)
    drawing = Drawing("circle_chord" if chord else "circle_parts")
    center = _centre(drawing, request, set())
    drawing.arc(center, r)
    unit = request.unit
    radius_label = length_label(radius, unit) if radius is not None else None
    if chord is not None:
        _chord(drawing, center, r, chord, radius_label, unit, request)
    elif radius is not None or request.has_part("radius"):
        end = drawing.point(polar(r, _RADIUS_TURN))
        drawing.line(center, end, radius_label)
    if diameter is not None or request.has_part("diameter"):
        _diameter(drawing, r, length_label(diameter, unit) if diameter is not None else None)
    return drawing.spec()


def _centre(drawing: Drawing, request: FigureRequest, taken: set[str]) -> str:
    letter = request.center.strip()[:1]
    named = letter.isalpha() and letter not in taken
    return drawing.point((0.0, 0.0), letter if named else "", show=named, dot=True)


def _diameter(drawing: Drawing, r: float, label: str | None) -> None:
    left, right = drawing.point(polar(r, 180.0)), drawing.point(polar(r, 0.0))
    # Clear of the centre's dot and letter.
    drawing.line(left, right, label, label_at=0.75)


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


def _with_polygon(request: FigureRequest, size: float | None) -> FigureSpec | None:
    """A polygon drawn as the question states it, and the circle through its corners
    (inscribed in the circle) or touching its sides (the circle inscribed in it). A circle
    of a stated size scales a polygon the question gives no length of; one it does give must
    agree with it. A polygon no circle passes through (or touches) draws nothing."""
    inside = bool(request.inscribed)
    shape = request.inscribed or request.circumscribed
    if shape in {"polygon", "regular_polygon"}:
        shape = "regular_polygon"
    polygon = build_polygon(
        request.model_copy(
            update={
                "kind": "polygon",
                "shape": shape,
                "measures": [m for m in request.measures if m.what not in _CIRCLE_PARTS],
                "inscribed": "",
                "circumscribed": "",
            }
        )
    )
    if polygon is None or not polygon.faces:
        return None
    at = {p.name: (p.x, p.y) for p in polygon.points}
    corners = [at[name] for name in polygon.faces[0]]
    found = circumcircle(corners) if inside else incircle(corners)
    if found is None:
        return None
    (cx, cy), reach = found
    sized = any(m.what not in _CIRCLE_PARTS | {"angle"} for m in request.measures)
    scale = 1.0
    if size is not None and sized and abs(reach - size) > 1e-4 * size:
        return None
    if size is not None and not sized:
        scale = size / reach
    return _composed(request, polygon, (cx, cy), scale, reach * scale, corners)


def _composed(
    request: FigureRequest,
    polygon: FigureSpec,
    centre: Point,
    scale: float,
    r: float,
    corners: list[Point],
) -> FigureSpec:
    drawing = Drawing(f"circle_{request.inscribed or request.circumscribed}")
    for p in polygon.points:
        moved = ((p.x - centre[0]) * scale, (p.y - centre[1]) * scale)
        drawing.points.append(p.model_copy(update={"x": moved[0], "y": moved[1]}))
    drawing.segments, drawing.angles = list(polygon.segments), list(polygon.angles)
    drawing.faces = [list(face) for face in polygon.faces]
    # An unnamed point is named by its place in the list, so no name repeats.
    centre_name = _centre(drawing, request, {p.name for p in polygon.points})
    drawing.arc(centre_name, r)
    radius, diameter = request.first("radius"), request.first("diameter")
    if radius is not None:
        if request.inscribed:
            target = drawing.at(polygon.faces[0][0])
        else:
            (ax, ay), (bx, by) = (
                ((x - centre[0]) * scale, (y - centre[1]) * scale) for x, y in corners[:2]
            )
            t = -(ax * (bx - ax) + ay * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)
            target = (ax + t * (bx - ax), ay + t * (by - ay))
        drawing.line(centre_name, drawing.point(target), length_label(radius, request.unit))
    if diameter is not None:
        _diameter(drawing, r, length_label(diameter, request.unit))
    return drawing.spec()


def circumcircle(corners: list[Point]) -> tuple[Point, float] | None:
    """The circle through every corner, or None when no circle passes through them all."""
    (ax, ay), (bx, by), (cx, cy) = corners[:3]
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < _TOLERANCE:
        return None
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    if any(abs(math.hypot(x - ux, y - uy) - r) > 1e-6 * max(1.0, r) for x, y in corners):
        return None
    return (ux, uy), r


def incircle(corners: list[Point]) -> tuple[Point, float] | None:
    """The circle touching every side, or None when no circle touches them all: where the
    bisectors of the first two corners meet, the same distance from every side."""
    count = len(corners)

    def bisector(i: int) -> Point:
        vx, vy = corners[i]
        (px, py), (nx, ny) = corners[i - 1], corners[(i + 1) % count]
        lp, ln = math.hypot(px - vx, py - vy), math.hypot(nx - vx, ny - vy)
        return ((px - vx) / lp + (nx - vx) / ln, (py - vy) / lp + (ny - vy) / ln)

    (x0, y0), (x1, y1) = corners[0], corners[1]
    (dx0, dy0), (dx1, dy1) = bisector(0), bisector(1)
    cross = dx0 * dy1 - dy0 * dx1
    if abs(cross) < _TOLERANCE:
        return None
    t = ((x1 - x0) * dy1 - (y1 - y0) * dx1) / cross
    centre = (x0 + t * dx0, y0 + t * dy0)
    gaps = [_gap(centre, corners[i], corners[(i + 1) % count]) for i in range(count)]
    if any(abs(gap - gaps[0]) > 1e-6 * max(1.0, gaps[0]) for gap in gaps):
        return None
    return centre, gaps[0]


def _gap(point: Point, a: Point, b: Point) -> float:
    (px, py), (ax, ay), (bx, by) = point, a, b
    return abs((bx - ax) * (ay - py) - (ax - px) * (by - ay)) / math.hypot(bx - ax, by - ay)
