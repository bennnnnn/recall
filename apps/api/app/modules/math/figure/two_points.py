"""Two angles of elevation (or depression) of one top, seen from two points on the ground.

On one side of what stands up, the smaller angle is seen from the farther point and the
points are ``gap`` = h(cot far - cot near) apart; on opposite sides of it ("from two points
on opposite sides of the tower") each point is h cot of its angle from the foot, and the gap
is h(cot a + cot b) across it. The height or the gap decides the other; a question that
states both must agree. Which side is what the question says (``sides_as_said``), never a
read's guess: a read flag for it was set on "on the same side of the tower" (2026-11-21).
A question that names both sides draws nothing.
Angles of elevation of the bottom and the top of one thing standing on another (a
flagstaff on a building) are seen from one point, never two: nothing is drawn for them.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable

from app.modules.math.figure.drawing import Drawing, angle_label, length_label
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec

_TOLERANCE = 1e-4
OPPOSITE = "opposite_sides"
SAME = "same_side"
_SIDE_WORDS = {
    OPPOSITE: re.compile(
        r"\bopposite sides?\b|\beither side\b|\bboth sides\b|\bon (?:the )?other side\b"
    ),
    SAME: re.compile(r"\bsame side\b"),
}
# One point, two tops: "the angles of elevation of the bottom and the top of a flagstaff".
_TWO_TOPS = re.compile(
    r"\b(?:bottom|foot|base)\s+and\s+(?:the\s+)?top\b|\btop\s+and\s+(?:the\s+)?(?:bottom|foot|base)\b"
)


def sides_as_said(request: FigureRequest, texts: Iterable[str]) -> FigureRequest | None:
    """The reading with the side its two points are on as the question says it (parts
    "opposite_sides" or "same_side"), whatever side parts the read gave; None when the
    question says both, or the two angles are of two tops seen from one point. A question
    that says no side is drawn on one side, as textbooks mean."""
    if request.kind != "polygon" or len(request.given("angle")) != 2:
        return request
    words = " ".join(texts).lower()
    if _TWO_TOPS.search(words):
        return None
    said = {part for part, named in _SIDE_WORDS.items() if named.search(words)}
    if len(said) > 1:
        return None
    parts = [part for part in request.parts if part not in _SIDE_WORDS]
    return request.model_copy(update={"parts": [*parts, *said]})


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= _TOLERANCE * max(1.0, abs(b))


def build_two_points(
    request: FigureRequest, scene: str, angles: list[float], height: float | None
) -> FigureSpec | None:
    """The top seen from two points, at the height the angles and the gap decide."""
    if not all(0 < a < 90 for a in angles) or request.first("distance", "length") is not None:
        return None
    opposite = OPPOSITE in request.parts
    first, second = angles if opposite else sorted(angles)
    if not opposite and not first < second:
        return None
    cot_first, cot_second = (1 / math.tan(math.radians(a)) for a in (first, second))
    # The gap per unit of height: across the foot, or between the far and the near point.
    spread = cot_first + cot_second if opposite else cot_first - cot_second
    gap, stated = request.first("gap"), height
    if gap is not None:
        found = gap / spread
        if height is not None and not _close(found, height):
            return None
        height = found
    if height is None:
        return None
    labels = (
        length_label(gap, request.unit) if gap is not None else None,
        length_label(stated, request.unit) if stated is not None else None,
    )
    if opposite:
        return _across(scene, (first, second), height, labels)
    return _one_side(scene, (first, second), height, labels)


# The gap's label and the height's, each None when the question does not state it.
_Labels = tuple[str | None, str | None]


def _one_side(
    scene: str, angles: tuple[float, float], height: float, labels: _Labels
) -> FigureSpec:
    """Both points on one side: the smaller angle from the farther."""
    far, near = angles
    cot_far, cot_near = (1 / math.tan(math.radians(a)) for a in angles)
    gap_label, height_label = labels
    drawing = Drawing(f"{scene}_two_points")
    foot = drawing.point((0.0, 0.0))
    top = drawing.point((0.0, height))
    near_at = drawing.point((height * cot_near, 0.0))
    far_at = drawing.point((height * cot_far, 0.0))
    drawing.line(foot, near_at)
    drawing.line(near_at, far_at, gap_label)
    drawing.line(foot, top, height_label)
    drawing.line(near_at, top)
    drawing.line(far_at, top)
    drawing.angle(foot, near_at, top, right=True)
    if scene == "depression":
        level = drawing.point((height * cot_far, height))
        drawing.line(top, level, dashed=True)
        drawing.angle(top, level, far_at, angle_label(far))
        drawing.angle(top, level, near_at, angle_label(near))
    else:
        drawing.angle(far_at, foot, top, angle_label(far))
        drawing.angle(near_at, foot, top, angle_label(near))
    return drawing.spec()


def _across(scene: str, angles: tuple[float, float], height: float, labels: _Labels) -> FigureSpec:
    """The points on opposite sides of the foot, each h cot its angle from it; the gap runs
    across the foot from one to the other."""
    gap_label, height_label = labels
    reach = [height / math.tan(math.radians(a)) for a in angles]
    drawing = Drawing(f"{scene}_opposite_sides")
    foot = drawing.point((0.0, 0.0))
    top = drawing.point((0.0, height))
    left = drawing.point((-reach[0], 0.0))
    right = drawing.point((reach[1], 0.0))
    drawing.line(left, right, gap_label)
    drawing.line(foot, top, height_label)
    drawing.line(left, top)
    drawing.line(right, top)
    drawing.angle(foot, right, top, right=True)
    for at, x, angle in ((left, -reach[0], angles[0]), (right, reach[1], angles[1])):
        if scene == "depression":
            level = drawing.point((x, height))
            drawing.line(top, level, dashed=True)
            drawing.angle(top, level, at, angle_label(angle))
        else:
            drawing.angle(at, foot, top, angle_label(angle))
    return drawing.spec()
