"""Heights and distances: the right triangle a question describes, drawn in its scene.

A tower seen from the ground ("elevation"), a boat seen from a cliff ("depression": the
horizontal at the top dashed, the angle between it and the line of sight marked), a ladder
against a wall ("leaning") and a kite string or a ramp ("slope": nothing stands up, so the
height is dashed). Each is a right triangle with its right angle at the foot of what stands
up: the vertical (``height``), the ground (``distance``), the slanting line (``length``:
the ladder, the string, the line of sight) and the angle at the ground (``angle``, or
``angle_from_vertical`` at the top). Any two of them, one a length, decide it; a third the
question states must agree, or nothing is drawn. Two angles seen from two points ``gap``
apart decide the height too (``two_points``). A man's eye height (``of`` "observer", or a
person the read names) is the observer's, never the tower's: the angle is drawn at his
eye, from the level through it, and the tower is his eye height and the rise above it. A
1.6 m "man" read beside a 30° angle was drawn as a 1.6 m tower (2026-11-21). Two heights
of two things (a flagstaff on a building) are no one triangle: nothing is drawn. Only
stated values are labelled; the right angle is boxed.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from app.modules.math.figure.drawing import Drawing, angle_label, length_label
from app.modules.math.figure.request import FigureRequest, Measure
from app.modules.math.figure.two_points import build_two_points, sides_as_said
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
# Whose height is an observer's, by the words a read names it ``of`` with.
_OBSERVERS = frozenset(
    {
        "observer", "man", "woman", "boy", "girl", "person", "child", "student", "eye",
        "eyes", "eye_level", "eye_height", "he", "she", "his", "her", "viewer", "surveyor",
    }
)  # fmt: skip


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


# A triangle's roles, as a scene's: its base runs along the ground, its hypotenuse slants.
_AS_SCENE = {"base": "distance", "hypotenuse": "length"}


def as_scene(request: FigureRequest) -> FigureRequest:
    """A right triangle read partly by a scene's roles ("a 15 m wire", "9 m from the foot"),
    read wholly as the upright scene."""
    measures = [
        m.model_copy(update={"what": _AS_SCENE.get(m.what, m.what)}) for m in request.measures
    ]
    return request.model_copy(update={"shape": "elevation", "measures": measures})


def as_said(request: FigureRequest, texts: Iterable[str]) -> FigureRequest | None:
    """A scene's reading held to the question's words: the side its two points are on."""
    return sides_as_said(request, texts) if request.shape in SCENES else request


def _observer(m: Measure) -> bool:
    return bool(m.of) and (m.of in _OBSERVERS or bool(set(m.of.split("_")) & _OBSERVERS))


def _heights(request: FigureRequest) -> tuple[float | None, float | None] | None:
    """(what stands up, the observer's eye height), each None when not stated; None when
    the heights are of more than one thing standing up, or of two observers."""
    heights = request.given("height")
    eyes = [m for m in heights if _observer(m)]
    standing = [m for m in heights if not _observer(m)]
    if len(eyes) > 1 or len(standing) > 1:
        return None
    return (
        standing[0].value if standing else None,
        eyes[0].value if eyes else None,
    )


def build_scene(request: FigureRequest) -> FigureSpec | None:
    scene = SCENES.get(request.shape)
    heights = _heights(request)
    if scene is None or heights is None:
        return None
    height, eye = heights
    angles = [m.value for m in request.given("angle")]
    if len(angles) == 2 and scene in {"elevation", "depression"} and eye is None:
        return build_two_points(request, scene, angles, height)
    if len(angles) > 1 or request.given("gap"):
        return None
    angle = _ground_angle(request)
    if angle is not None and angle < 0:
        return None
    if eye is not None:
        return _observed(request, scene, (height, eye), angle)
    right = _solve(height, request.first("distance"), request.first("length"), angle)
    if right is None:
        return None
    return _draw(request, scene, right, height)


def _labels(request: FigureRequest, height: float | None) -> dict[str, str | None]:
    unit = request.unit
    found: dict[str, str | None] = {}
    for what in ("distance", "length"):
        value = request.first(what)
        found[what] = length_label(value, unit) if value is not None else None
    found["height"] = length_label(height, unit) if height is not None else None
    for what in ("angle", "angle_from_vertical"):
        value = request.first(what)
        found[what] = angle_label(value) if value is not None else None
    return found


def _draw(request: FigureRequest, scene: str, right: _Right, height: float | None) -> FigureSpec:
    """The triangle with its right angle at the origin, the vertical up the y-axis, the
    ground along the x-axis; the depression's horizontal across the top."""
    labels = _labels(request, height)
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


def _observed(
    request: FigureRequest,
    scene: str,
    heights: tuple[float | None, float],
    angle: float | None,
) -> FigureSpec | None:
    """An angle of elevation seen from a man's eye: the right triangle above his eye level
    (its rise the tower less his eye height), the level dashed from his eye to the tower,
    the angle at his eye. A tower no taller than his eye, a depression, an angle from the
    vertical or a line of sight stated draws nothing."""
    height, eye = heights
    if scene != "elevation" or request.first("angle_from_vertical", "length") is not None:
        return None
    if height is not None and height <= eye + _TOLERANCE:
        return None
    rise = height - eye if height is not None else None
    above = _solve(rise, request.first("distance"), None, angle)
    if above is None:
        return None
    labels = _labels(request, height)
    d, top_y = above.distance, eye + above.height
    drawing = Drawing("elevation_observer")
    foot = drawing.point((0.0, 0.0))
    top = drawing.point((0.0, top_y))
    level = drawing.point((0.0, eye))
    stands = drawing.point((d, 0.0))
    at_eye = drawing.point((d, eye))
    drawing.line(foot, stands, labels["distance"])
    drawing.line(stands, drawing.point((d + _RUN_ON * max(top_y, d), 0.0)))
    drawing.line(foot, top, labels["height"])
    drawing.line(stands, at_eye, length_label(eye, request.unit))
    drawing.line(at_eye, level, dashed=True)
    drawing.line(at_eye, top)
    drawing.angle(foot, stands, top, right=True)
    drawing.angle(level, at_eye, top, right=True)
    drawing.angle(at_eye, level, top, labels["angle"])
    return drawing.spec()
