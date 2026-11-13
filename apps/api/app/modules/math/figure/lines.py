"""Lines and angles from the angle a question states: two parallel lines and a transversal,
two lines crossing, one angle, angles on a straight line, complementary angles. The stated
angle is marked and labelled where it is; the angles the question asks for are left for the
student."""

from __future__ import annotations

import math

from app.modules.math.figure.drawing import Drawing, angle_label, polar
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec

# A ray's length, the gap between two parallel lines, and how far a transversal runs past
# them, in the drawing's units; the angle drawn when the question states none.
_RAY = 5.0
_GAP = 3.0
_PAST = 2.0
_DEFAULT_ANGLE = 60.0
_PARALLEL = frozenset({"parallel_lines", "parallel_transversal", "transversal"})
_CROSSING = frozenset({"intersecting_lines", "vertical_angles", "vertically_opposite_angles"})


def _angle(request: FigureRequest) -> tuple[float, bool]:
    value = request.first("angle")
    return (value, True) if value is not None else (_DEFAULT_ANGLE, False)


def build_lines(request: FigureRequest) -> FigureSpec | None:
    angle, stated = _angle(request)
    if not 0 < angle < 180:
        return None
    label = angle_label(angle) if stated else None
    shape = request.shape
    if shape in _PARALLEL:
        return _parallel(angle, label)
    if shape in _CROSSING or shape == "perpendicular_lines":
        return _crossing(90.0 if shape == "perpendicular_lines" else angle, label)
    if shape == "angles_on_line":
        return _on_line(angle, label)
    if shape == "complementary_angles":
        return _complementary(angle, label) if angle < 90 else None
    if shape == "angle":
        return _one_angle(angle, label, request.vertices.strip())
    return None


def _parallel(angle: float, label: str | None) -> FigureSpec:
    """Two horizontal parallel lines; the transversal makes ``angle`` with the upper one,
    measured from the line's right-hand ray to the transversal's upper ray."""
    drawing = Drawing("parallel_lines")
    run = _GAP / math.tan(math.radians(angle)) if abs(angle - 90) > 1e-9 else 0.0
    left = min(-_RAY, -run - _RAY / 2)
    right = max(_RAY, -run + _RAY / 2, _RAY / 2)
    upper = drawing.point((0.0, 0.0))
    for y in (0.0, -_GAP):
        start, end = drawing.point((left, y)), drawing.point((right, y))
        drawing.line(start, end, arrows=1)
    top = drawing.point(polar(_PAST, angle))
    bottom = drawing.point(polar(_PAST, angle + 180, center=(-run, -_GAP)))
    drawing.line(top, bottom)
    drawing.angle(upper, _right_of(drawing, 0.0), top, label, right=abs(angle - 90) < 1e-9)
    return drawing.spec()


def _right_of(drawing: Drawing, y: float) -> str:
    """The right end of the line at height ``y``."""
    ends = [p for p in drawing.points if abs(p.y - y) < 1e-9]
    return max(ends, key=lambda p: p.x).name


def _crossing(angle: float, label: str | None) -> FigureSpec:
    drawing = Drawing("intersecting_lines")
    middle = drawing.point((0.0, 0.0))
    east, west = drawing.point((_RAY, 0.0)), drawing.point((-_RAY, 0.0))
    up, down = drawing.point(polar(_RAY, angle)), drawing.point(polar(_RAY, angle + 180))
    drawing.line(west, east)
    drawing.line(down, up)
    drawing.angle(middle, east, up, label, right=abs(angle - 90) < 1e-9)
    return drawing.spec()


def _on_line(angle: float, label: str | None) -> FigureSpec:
    drawing = Drawing("angles_on_line")
    middle = drawing.point((0.0, 0.0), dot=True)
    east, west = drawing.point((_RAY, 0.0)), drawing.point((-_RAY, 0.0))
    ray = drawing.point(polar(_RAY, angle))
    drawing.line(west, east)
    drawing.line(middle, ray)
    drawing.angle(middle, east, ray, label)
    drawing.angle(middle, ray, west)
    return drawing.spec()


def _complementary(angle: float, label: str | None) -> FigureSpec:
    drawing = Drawing("complementary_angles")
    middle = drawing.point((0.0, 0.0))
    east, north = drawing.point((_RAY, 0.0)), drawing.point((0.0, _RAY))
    ray = drawing.point(polar(_RAY, angle))
    drawing.line(middle, east)
    drawing.line(middle, north)
    drawing.line(middle, ray)
    drawing.angle(middle, east, ray, label)
    drawing.angle(middle, ray, north)
    return drawing.spec()


def _one_angle(angle: float, label: str | None, letters: str) -> FigureSpec:
    """Angle ABC is the angle at B: its letters name the ray ends and the vertex."""
    named = len(letters) == 3 and len(set(letters)) == 3 and letters.isalpha()
    first, vertex, last = list(letters) if named else ("", "", "")
    drawing = Drawing("angle")
    at = drawing.point((0.0, 0.0), vertex, show=named)
    east = drawing.point((_RAY, 0.0), first, show=named)
    ray = drawing.point(polar(_RAY, angle), last, show=named)
    drawing.line(at, east)
    drawing.line(at, ray)
    drawing.angle(at, east, ray, label, right=abs(angle - 90) < 1e-9)
    return drawing.spec()
