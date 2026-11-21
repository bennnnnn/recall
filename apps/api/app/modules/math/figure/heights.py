"""Heights and distances: the right triangle a question describes, drawn in its scene.

A tower seen from the ground ("elevation"), a boat seen from a cliff ("depression": the
horizontal at the top dashed, the angle between it and the line of sight marked), a ladder
against a wall ("leaning") and a kite string or a ramp ("slope": nothing stands up, so the
height is dashed). Each is a right triangle with its right angle at the foot of what stands
up: the vertical (``height``), the ground (``distance``), the slanting line (``length``:
the ladder, the string, the line of sight) and the angle at the ground (``angle``, or
``angle_from_vertical`` at the top). Any two of them, one a length, decide it; a third the
question states must agree, or nothing is drawn. Two angles seen from two points ``gap``
apart on one side decide the height too. Only stated values are labelled; the right angle
is boxed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.modules.math.figure.drawing import Drawing, angle_label, length_label
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec

SCENES = {
    "elevation": "elevation",
    "angle_of_elevation": "elevation",
    "depression": "depression",
    "angle_of_depression": "depression",
    "leaning": "leaning",
    "ladder": "leaning",
    "slope": "slope",
    "incline": "slope",
    "ramp": "slope",
}
# The measures only a scene has: no triangle's own sides or angles.
ROLES = frozenset({"distance", "gap", "angle_from_vertical", "length"})
_TOLERANCE = 1e-4
# What a scene leaves open: the ground's length, and the angle at the ground.
_DEFAULT_DISTANCE = 5.0
_DEFAULT_ANGLE = 55.0
# How far the ground and a wall run on past the triangle, as a share of its size.
_RUN_ON = 0.15


@dataclass(frozen=True)
class _Right:
    """The scene's triangle: its vertical side and its ground."""

    height: float
    distance: float

    @property
    def length(self) -> float:
        return math.hypot(self.height, self.distance)

    @property
    def angle(self) -> float:
        return math.degrees(math.atan2(self.height, self.distance))


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= _TOLERANCE * max(1.0, abs(b))


def _ground_angle(request: FigureRequest) -> float | None:
    angle = request.first("angle")
    from_vertical = request.first("angle_from_vertical")
    if from_vertical is not None:
        if angle is not None and not _close(angle, 90 - from_vertical):
            return None
        angle = 90 - from_vertical
    return angle if angle is None or 0 < angle < 90 else -1.0


def _solve(
    height: float | None, distance: float | None, length: float | None, angle: float | None
) -> _Right | None:
    """The triangle two of its values decide, held to every one stated."""
    tan = math.tan(math.radians(angle)) if angle is not None else None
    if height is not None and distance is not None:
        found = _Right(height, distance)
    elif height is not None and tan is not None:
        found = _Right(height, height / tan)
    elif distance is not None and tan is not None:
        found = _Right(distance * tan, distance)
    elif length is not None and angle is not None:
        turn = math.radians(angle)
        found = _Right(length * math.sin(turn), length * math.cos(turn))
    elif length is not None and (height is not None or distance is not None):
        known = float(height if height is not None else distance or 0)
        if length <= known:
            return None
        other = math.sqrt(length * length - known * known)
        found = _Right(known, other) if height is not None else _Right(other, known)
    elif angle is None and (height, distance, length) != (None, None, None):
        # One length: the angle at the ground is the picture's choice, left unlabelled.
        return _solve(height, distance, length, _DEFAULT_ANGLE)
    elif angle is not None:
        return _solve(None, _DEFAULT_DISTANCE, None, angle)
    else:
        return None
    holds = (
        (length is None or _close(found.length, length))
        and (angle is None or abs(found.angle - angle) < 0.05)
        and (height is None or _close(found.height, height))
        and (distance is None or _close(found.distance, distance))
    )
    return found if holds else None


def build_scene(request: FigureRequest) -> FigureSpec | None:
    scene = SCENES.get(request.shape)
    if scene is None:
        return None
    angles = [m.value for m in request.given("angle")]
    if len(angles) == 2 and scene in {"elevation", "depression"}:
        return _two_points(request, scene, sorted(angles))
    if len(angles) > 1 or request.given("gap"):
        return None
    angle = _ground_angle(request)
    if angle is not None and angle < 0:
        return None
    right = _solve(
        request.first("height"), request.first("distance"), request.first("length"), angle
    )
    if right is None:
        return None
    return _draw(request, scene, right)


def _labels(request: FigureRequest) -> dict[str, str | None]:
    unit = request.unit
    found: dict[str, str | None] = {}
    for what in ("height", "distance", "length", "gap"):
        value = request.first(what)
        found[what] = length_label(value, unit) if value is not None else None
    for what in ("angle", "angle_from_vertical"):
        value = request.first(what)
        found[what] = angle_label(value) if value is not None else None
    return found


def _draw(request: FigureRequest, scene: str, right: _Right) -> FigureSpec:
    """The triangle with its right angle at the origin, the vertical up the y-axis, the
    ground along the x-axis; the depression's horizontal across the top."""
    labels = _labels(request)
    h, d = right.height, right.distance
    run = _RUN_ON * max(h, d)
    drawing = Drawing(scene)
    foot = drawing.point((0.0, 0.0))
    top = drawing.point((0.0, h))
    end = drawing.point((d, 0.0))
    drawing.line(foot, end, labels["distance"])
    drawing.line(end, drawing.point((d + run, 0.0)))
    drawing.line(foot, top, labels["height"], dashed=scene == "slope")
    drawing.line(end, top, labels["length"])
    drawing.angle(foot, end, top, right=True)
    if scene == "depression":
        level = drawing.point((d + run, h))
        drawing.line(top, level, dashed=True)
        drawing.angle(top, level, end, labels["angle"])
    elif labels["angle"] is not None or labels["angle_from_vertical"] is None:
        drawing.angle(end, foot, top, labels["angle"])
    if scene == "leaning":
        drawing.line(top, drawing.point((0.0, h + run)))
    if labels["angle_from_vertical"] is not None:
        drawing.angle(top, foot, end, labels["angle_from_vertical"])
    return drawing.spec()


def _two_points(request: FigureRequest, scene: str, angles: list[float]) -> FigureSpec | None:
    """Two angles of elevation (or depression) seen from two points on one side, ``gap``
    apart: the smaller from the farther. The height is what makes both true."""
    far, near = angles
    if not 0 < far < near < 90 or request.first("distance", "length") is not None:
        return None
    cot_far, cot_near = (1 / math.tan(math.radians(a)) for a in (far, near))
    gap, height = request.first("gap"), request.first("height")
    if gap is not None:
        found = gap / (cot_far - cot_near)
        if height is not None and not _close(found, height):
            return None
        height = found
    if height is None:
        return None
    gap_size = height * (cot_far - cot_near)
    labels = _labels(request)
    drawing = Drawing(f"{scene}_two_points")
    foot = drawing.point((0.0, 0.0))
    top = drawing.point((0.0, height))
    near_at = drawing.point((height * cot_near, 0.0))
    far_at = drawing.point((height * cot_near + gap_size, 0.0))
    drawing.line(foot, near_at)
    drawing.line(near_at, far_at, labels["gap"])
    drawing.line(foot, top, labels["height"])
    drawing.line(near_at, top)
    drawing.line(far_at, top)
    drawing.angle(foot, near_at, top, right=True)
    if scene == "depression":
        level = drawing.point((height * cot_near + gap_size, height))
        drawing.line(top, level, dashed=True)
        drawing.angle(top, level, far_at, angle_label(far))
        drawing.angle(top, level, near_at, angle_label(near))
    else:
        drawing.angle(far_at, foot, top, angle_label(far))
        drawing.angle(near_at, foot, top, angle_label(near))
    return drawing.spec()
