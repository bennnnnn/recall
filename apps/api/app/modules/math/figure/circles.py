"""A circle and its parts from the values a question states: a radius or diameter drawn and
labelled, a chord at its true distance from the centre (the radius it asks for drawn to its
true length, unlabelled), a polygon drawn as stated with the circle through its corners
(inscribed in the circle) or touching its sides (around it), and each circle theorem's
figure by its own builder (``circle_arcs``, ``circle_angles``, ``circle_lines``), and two
circles with different centres (``two_circles``)."""

from __future__ import annotations

import math
from collections.abc import Callable

from app.modules.math.figure import circle_angles, circle_arcs, circle_lines, two_circles
from app.modules.math.figure.circle_frame import (
    CIRCLE_ANGLES,
    CIRCLE_LENGTHS,
    CircleFigure,
    close,
    letters,
    start,
    stated_size,
)
from app.modules.math.figure.drawing import Drawing, Point, length_label, polar
from app.modules.math.figure.polygon import build_polygon
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec

_RADIUS = 3.0
# Where a drawn radius points when nothing else places it.
_RADIUS_TURN = 35.0
_TOLERANCE = 1e-6
_CIRCLE_PARTS = CIRCLE_LENGTHS | CIRCLE_ANGLES

Builder = Callable[[FigureRequest], FigureSpec | None]
# Each circle theorem's figure by the shape the read names it.
_THEOREMS: dict[str, Builder] = {
    "sector": circle_arcs.build_sector,
    "arc": circle_arcs.build_sector,
    "segment": circle_arcs.build_segment,
    "annulus": circle_arcs.build_annulus,
    "concentric_circles": circle_arcs.build_annulus,
    "tangent": circle_lines.build_tangent,
    "two_tangents": circle_lines.build_two_tangents,
    "tangents": circle_lines.build_two_tangents,
    "intersecting_chords": circle_lines.build_intersecting_chords,
    "angle_at_centre": circle_angles.build_angle_at_centre,
    "angle_at_center": circle_angles.build_angle_at_centre,
    "inscribed_angle": circle_angles.build_angle_at_centre,
    "angle_in_semicircle": circle_angles.build_angle_in_semicircle,
    "cyclic_quadrilateral": circle_angles.build_cyclic_quadrilateral,
}


def _semicircle(request: FigureRequest) -> Builder:
    """A semicircle with a point on its arc (a third letter, an angle there, a side to it) is
    the angle in a semicircle; one by itself (its radius or diameter, its perimeter or area
    asked) is drawn as itself, never a whole circle with a triangle in it."""
    point_on_it = len(request.vertices.strip()) >= 3 or any(
        m.what not in circle_arcs.SIZES or len(m.name.strip()) == 2 for m in request.measures
    )
    return circle_angles.build_angle_in_semicircle if point_on_it else circle_arcs.build_semicircle


def _theorem(request: FigureRequest) -> Builder | None:
    """The theorem's builder: by the shape the read names, else by what it measures (a read
    that says "circle" with an angle at the centre is a sector)."""
    if request.shape in {"semicircle", "semi_circle", "half_circle"}:
        return _semicircle(request)
    if two_circles.reads_two(request):
        return two_circles.build_two_circles
    if request.shape in _THEOREMS:
        return _THEOREMS[request.shape]
    if request.inscribed or request.circumscribed:
        return None
    if request.given("inscribed_angle"):
        return circle_angles.build_angle_at_centre
    if request.given("central_angle"):
        return circle_arcs.build_sector
    if request.given("tangent"):
        return circle_lines.build_tangent
    sizes = {m.value / (2 if m.what == "diameter" else 1) for m in request.measures
             if m.what in {"radius", "diameter"}}  # fmt: skip
    return circle_arcs.build_annulus if len(sizes) == 2 else None


def build_circle(request: FigureRequest) -> FigureSpec | None:
    theorem = _theorem(request)
    if theorem is not None:
        return theorem(request)
    holds, size = stated_size(request)
    if not holds:
        return None
    radius, diameter = request.first("radius"), request.first("diameter")
    chord, gap = request.first("chord"), request.first("distance")
    if request.inscribed or request.circumscribed:
        if chord is not None or gap is not None or (request.inscribed and request.circumscribed):
            return None
        return _with_polygon(request, size)
    if gap is not None:
        return _chord_at(request, size, chord, gap)
    if chord is not None and size is not None and chord > 2 * size + _TOLERANCE:
        return None
    r = size or (max(_RADIUS, chord * 0.75) if chord is not None else _RADIUS)
    figure = start(request, "circle_chord" if chord else "circle_parts", r)
    figure.drawing.arc(figure.centre, r)
    if chord is not None:
        _chord(figure, chord, chord, None, request)
    elif radius is not None or request.has_part("radius"):
        end = figure.drawing.point(polar(r, _RADIUS_TURN))
        figure.drawing.line(figure.centre, end, figure.length(radius))
    if diameter is not None or request.has_part("diameter"):
        _diameter(figure.drawing, r, figure.length(diameter))
    return figure.drawing.spec()


def _chord_at(
    request: FigureRequest, size: float | None, chord: float | None, gap: float
) -> FigureSpec | None:
    """A chord at its stated distance from the centre: the radius, the half chord and the
    distance make a right triangle, so any two of them draw the third."""
    if size is None and chord is None:
        return None
    if size is None:
        size_drawn = math.hypot(chord / 2, gap) if chord is not None else 0.0
    else:
        size_drawn = size
    if gap >= size_drawn - _TOLERANCE:
        return None
    width = 2 * math.sqrt(size_drawn**2 - gap**2)
    if chord is not None and not close(width, chord):
        return None
    figure = start(request, "circle_chord", size_drawn)
    figure.drawing.arc(figure.centre, size_drawn)
    _chord(figure, width, chord, gap, request)
    diameter = request.first("diameter")
    if diameter is not None:
        _diameter(figure.drawing, size_drawn, figure.length(diameter))
    return figure.drawing.spec()


def _diameter(drawing: Drawing, r: float, label: str | None) -> None:
    left, right = drawing.point(polar(r, 180.0)), drawing.point(polar(r, 0.0))
    # Clear of the centre's dot and letter.
    drawing.line(left, right, label, label_at=0.75)


def _chord(
    figure: CircleFigure,
    width: float,
    chord: float | None,
    gap: float | None,
    request: FigureRequest,
) -> None:
    """The chord below the centre at its distance, the radius to its end, and the dashed
    perpendicular from the centre that halves it, labelled with the distance stated."""
    drawing, r, half = figure.drawing, figure.r, width / 2
    depth = math.sqrt(max(0.0, r * r - half * half))
    names = letters(request, 2) or ["", ""]
    left = figure.named((-half, -depth), names[0])
    right = figure.named((half, -depth), names[1])
    drawing.line(left, right, figure.length(chord))
    drawing.line(figure.centre, right, figure.length(request.first("radius")))
    if depth > _TOLERANCE:
        foot = figure.named((0.0, -depth), _foot_letter(request))
        drawing.line(figure.centre, foot, figure.length(gap), dashed=True)
        drawing.angle(foot, right, figure.centre, right=True)


def _foot_letter(request: FigureRequest) -> str:
    """The chord's midpoint as the distance's name letters it ("OM": M), or none."""
    centre = request.center.strip()[:1]
    for measure in request.given("distance"):
        name = measure.name.strip()
        if len(name) == 2 and centre and centre in name:
            return name.replace(centre, "", 1)
    return ""


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
                "circle_through": "",
                "circle_within": "",
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
    taken = {p.name for p in polygon.points}
    name = request.center.strip()[:1]
    named = name.isalpha() and name not in taken
    centre_name = drawing.point((0.0, 0.0), name if named else "", show=named, dot=True)
    drawing.arc(centre_name, r)
    radius, diameter = request.first("radius"), request.first("diameter")
    # The radius is drawn when stated, and unlabelled when it is what the question asks.
    if radius is not None or (request.has_part("radius") and diameter is None):
        if request.inscribed:
            target = drawing.at(polygon.faces[0][0])
        else:
            side = _quiet_side(polygon)
            (ax, ay), (bx, by) = (
                ((x - centre[0]) * scale, (y - centre[1]) * scale)
                for x, y in (corners[side], corners[(side + 1) % len(corners)])
            )
            t = -(ax * (bx - ax) + ay * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)
            target = (ax + t * (bx - ax), ay + t * (by - ay))
        label = length_label(radius, request.unit) if radius is not None else None
        drawing.line(centre_name, drawing.point(target), label)
    if diameter is not None:
        _diameter(drawing, r, length_label(diameter, request.unit))
    return drawing.spec()


def _quiet_side(polygon: FigureSpec) -> int:
    """The first side with no label: the radius to it keeps clear of the side's number."""
    face = polygon.faces[0]
    for i, name in enumerate(face):
        other = face[(i + 1) % len(face)]
        side = next((s for s in polygon.segments if {s.a, s.b} == {name, other}), None)
        if side is not None and side.label is None:
            return i
    return 0


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
