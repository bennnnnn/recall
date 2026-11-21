"""Lines and angles from the angles a question states: two parallel lines and a transversal,
two lines crossing, one angle, angles on a straight line or about a point, complementary
angles, supplementary angles. Each stated angle is marked and labelled where it is; the
angles the question asks for are left for the student. Angles written with a letter ("x",
"2x") are drawn at the sizes their sum decides, labelled as written (``angle_terms``)."""

from __future__ import annotations

import math

from app.modules.math.figure.angle_terms import WHOLES, sized_angles
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
# The shapes whose angles add up to a whole: a straight line, a full turn, a right angle.
_SUMS = frozenset(
    {"angles_on_line", "supplementary_angles", "angles_at_point", "complementary_angles"}
)
_CROSSING = frozenset({"intersecting_lines", "vertical_angles", "vertically_opposite_angles"})


def build_lines(request: FigureRequest) -> FigureSpec | None:
    """Every angle the question states drawn and labelled where it is; nothing when they
    are more than the picture holds (a second angle beside parallel lines) or do not fit it
    (40° between perpendicular lines)."""
    if any(m.what != "angle" for m in request.measures):
        return None
    shape = request.shape
    if request.angle_terms:
        return _lettered(request)
    angles = [m.value for m in request.measures]
    if any(not 0 < value < 180 for value in angles):
        return None
    labelled = [(value, angle_label(value)) for value in angles]
    if shape in {"angles_on_line", "angles_at_point", "supplementary_angles"}:
        whole = 360.0 if shape == "angles_at_point" else 180.0
        if shape == "supplementary_angles" and len(angles) > 2:
            return None
        return _around(shape, angles, whole) if angles and sum(angles) <= whole else None
    if shape == "complementary_angles":
        return _complementary(labelled)
    if len(angles) > 1:
        return None
    angle, label = (angles[0], angle_label(angles[0])) if angles else (_DEFAULT_ANGLE, None)
    if shape in _PARALLEL:
        return _parallel(angle, label)
    if shape == "perpendicular_lines":
        return _crossing(90.0, None) if angle == 90 or not angles else None
    if shape in _CROSSING:
        return _crossing(angle, label)
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


def _lettered(request: FigureRequest) -> FigureSpec | None:
    """Angles written with a letter, at the sizes their sum decides, labelled as written."""
    whole = WHOLES.get(request.shape) if request.shape in _SUMS else None
    sized = sized_angles(request, whole) if whole is not None else None
    if sized is None or abs(sum(angle.size for angle in sized) - (whole or 0)) > 1e-9:
        return None
    labelled = [(angle.size, angle.label or angle_label(angle.size)) for angle in sized]
    if request.shape == "complementary_angles":
        return _complementary(labelled)
    return _around(request.shape, [a for a, _ in labelled], whole or 0.0, [b for _, b in labelled])


def _around(
    shape: str, angles: list[float], whole: float, labels: list[str] | None = None
) -> FigureSpec:
    """Angles side by side about one point: each stated one labelled (with its size, or
    with ``labels``), what is left of the straight line or the full turn drawn and left for
    the student."""
    drawing = Drawing(shape)
    middle = drawing.point((0.0, 0.0), dot=True)
    east = drawing.point((_RAY, 0.0))
    on_line = shape != "angles_at_point"
    start = drawing.point((-_RAY, 0.0)) if on_line else middle
    drawing.line(start, east)
    turn, last = 0.0, east
    for index, value in enumerate(angles):
        label = labels[index] if labels is not None else angle_label(value)
        turn += value
        ray = drawing.point(polar(_RAY, turn))
        # The ray that closes the turn is the first one again (east), or the straight line's
        # other half: drawn already. At a point, the ray at 180° is a ray of its own.
        if abs(turn - whole) > 1e-9:
            drawing.line(middle, ray)
        drawing.angle(middle, last, ray, label)
        last = ray
    left = whole - turn
    if 1e-9 < left < 180:
        drawing.angle(middle, last, start if on_line else east)
    return drawing.spec()


def _complementary(angles: list[tuple[float, str]]) -> FigureSpec | None:
    """Two angles making a right angle: the stated one (or both) labelled."""
    if not angles or len(angles) > 2 or angles[0][0] >= 90:
        return None
    if len(angles) == 2 and abs(angles[0][0] + angles[1][0] - 90) > 1e-9:
        return None
    drawing = Drawing("complementary_angles")
    middle = drawing.point((0.0, 0.0))
    east, north = drawing.point((_RAY, 0.0)), drawing.point((0.0, _RAY))
    ray = drawing.point(polar(_RAY, angles[0][0]))
    drawing.line(middle, east)
    drawing.line(middle, north)
    drawing.line(middle, ray)
    drawing.angle(middle, east, ray, angles[0][1])
    drawing.angle(middle, ray, north, angles[1][1] if len(angles) == 2 else None)
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
