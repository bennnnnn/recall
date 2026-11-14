"""A triangle drawn from what the question states, and nothing it does not.

``triangle_read`` places the question's sides and angles (by the letters it uses, or by
their roles: a base, legs, the equal sides). The triangle's laws work out what they decide;
what they leave open is chosen so every stated value and the named kind still hold (an
obtuse triangle obtuse, a scalene one with three different sides): each free choice is
tried in turn until one does. Only stated values are labelled, each once: a length the
question asks for is drawn to its size, unlabelled. A statement the triangle cannot meet
(sides 2, 3, 9; legs 5 and hypotenuse 4; angles summing past 180°) draws nothing.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass

from app.modules.math.figure.drawing import Drawing, angle_at, angle_label, length_label
from app.modules.math.figure.request import FigureRequest
from app.modules.math.figure.triangle_read import Placed, Triangle, place
from app.modules.math.schemas.figure import FigureSpec

TRIANGLES = frozenset(
    {
        "triangle",
        "right_triangle",
        "isosceles_triangle",
        "equilateral_triangle",
        "scalene_triangle",
        "acute_triangle",
        "obtuse_triangle",
    }
)
_DEFAULT_BASE = 5.0
_TOLERANCE = 1e-6
# A kind's angles told apart from a right angle, and its sides from equal ones.
_KIND_ANGLE = 0.5
_KIND_SIDE = 1e-3


@dataclass(frozen=True)
class _Choice:
    """The values a picture picks for what the question leaves open: the angle between two
    given sides, the share of what is left for one of two unknown angles, three angles for a
    triangle with none, where the apex stands over a base with a height, and an isosceles
    triangle's base angles."""

    included: float
    share: float
    angles: tuple[float, float, float]
    apex_share: float
    base_angle: float


_CHOICES = (
    _Choice(65.0, 0.55, (58.0, 72.0, 50.0), 0.35, 65.0),
    _Choice(115.0, 0.8, (115.0, 35.0, 30.0), -0.3, 30.0),
    _Choice(40.0, 0.5, (40.0, 60.0, 80.0), 0.5, 50.0),
    _Choice(140.0, 0.2, (35.0, 120.0, 25.0), 1.3, 75.0),
)


def _law_step(t: Triangle) -> bool:
    """One deduction the triangle's laws allow; False when none is left."""
    s, a = t.sides, t.angles
    known_angles = [x for x in a if x is not None]
    if len(known_angles) == 2:
        a[a.index(None)] = 180.0 - sum(known_angles)
        return True
    if t.isosceles:
        for i, j in ((0, 1), (1, 0)):
            if s[i] is not None and s[j] is None:
                s[j] = s[i]
                return True
            if a[i] is not None and a[j] is None:
                a[j] = a[i]
                return True
    known_sides = [x for x in s if x is not None]
    if len(known_sides) == 2 and t.perimeter is not None:
        s[s.index(None)] = t.perimeter - sum(known_sides)
        return True
    if t.isosceles and s[2] is not None and s[0] is None and t.perimeter is not None:
        s[0] = s[1] = (t.perimeter - s[2]) / 2
        return True
    if t.isosceles and s[0] is not None and s[2] is None and t.perimeter is not None:
        s[2] = t.perimeter - 2 * s[0]
        return True
    if t.isosceles and s[2] is not None and s[0] is None and t.height is not None:
        s[0] = s[1] = math.hypot(t.height, s[2] / 2)
        return True
    return _height_step(t) or _cosine_step(t) or _sine_step(t)


def _height_step(t: Triangle) -> bool:
    """The height to the base, with a base angle, is the side beside that angle times its
    sine."""
    s, a, h = t.sides, t.angles, t.height
    if h is None:
        return False
    for side, angle in ((1, 0), (0, 1)):
        value = a[angle]
        if s[side] is None and value is not None and 0 < value < 180:
            s[side] = h / math.sin(math.radians(value))
            return True
    return False


def _cosine_step(t: Triangle) -> bool:
    s, a = t.sides, t.angles
    if all(x is not None for x in s) and any(x is None for x in a):
        s0, s1, s2 = (float(x) for x in s if x is not None)
        for i, (opp, p, q) in enumerate(((s0, s1, s2), (s1, s0, s2), (s2, s0, s1))):
            if a[i] is None:
                cosine = (p * p + q * q - opp * opp) / (2 * p * q)
                if not -1 < cosine < 1:
                    return False
                a[i] = math.degrees(math.acos(cosine))
        return True
    for i in range(3):
        j, k = (i + 1) % 3, (i + 2) % 3
        sj, sk, ai = s[j], s[k], a[i]
        if s[i] is None and sj is not None and sk is not None and ai is not None:
            s[i] = math.sqrt(max(0.0, sj * sj + sk * sk - 2 * sj * sk * math.cos(math.radians(ai))))
            return True
    return False


def _sine_step(t: Triangle) -> bool:
    s, a = t.sides, t.angles
    pairs = [i for i in range(3) if s[i] is not None and a[i] is not None]
    if not pairs:
        return False
    ratio = float(s[pairs[0]] or 0) / math.sin(math.radians(float(a[pairs[0]] or 0)))
    for i in range(3):
        angle, side = a[i], s[i]
        if side is None and angle is not None:
            s[i] = ratio * math.sin(math.radians(angle))
            return True
        # The opposite angle from a side is decided only beside a right or obtuse angle.
        if angle is None and side is not None and max(x or 0 for x in a) >= 90:
            sine = side / ratio
            if not 0 < sine <= 1:
                return False
            a[i] = math.degrees(math.asin(sine))
            return True
    return False


def solve(t: Triangle) -> None:
    for _ in range(12):
        if not _law_step(t):
            return


def _default_step(t: Triangle, choice: _Choice) -> bool:
    """Choose one value the question leaves open, keeping every stated one."""
    s, a = t.sides, t.angles
    known = [i for i in range(3) if a[i] is not None]
    if t.isosceles and a[0] is None and a[2] is None:
        a[0] = a[1] = choice.base_angle
        return True
    sides = [i for i in range(3) if s[i] is not None]
    if not known and len(sides) == 2:
        a[3 - sides[0] - sides[1]] = choice.included
        return True
    if t.height is not None and s[2] is not None and not known:
        apex = (s[2] * choice.apex_share, t.height)
        s[1] = math.hypot(*apex)
        s[0] = math.hypot(s[2] - apex[0], apex[1])
        return True
    if len(known) == 1:
        rest = 180.0 - float(a[known[0]] or 0)
        free = [i for i in range(3) if i != known[0]]
        a[free[0]] = rest * 0.5 if t.isosceles else rest * choice.share
        return True
    if not known:
        a[:] = [*choice.angles]
        return True
    if all(x is None for x in s):
        s[2] = _DEFAULT_BASE
        return True
    return False


def _complete(t: Triangle, choice: _Choice) -> list[float] | None:
    solve(t)
    for _ in range(4):
        if all(x is not None for x in t.sides) and all(x is not None for x in t.angles):
            break
        if not _default_step(t, choice):
            break
        solve(t)
    return _sides(t)


def _sides(t: Triangle) -> list[float] | None:
    if any(x is None for x in t.sides):
        return None
    s0, s1, s2 = (float(x or 0) for x in t.sides)
    if min(s0, s1, s2) <= 0 or s0 + s1 <= s2 or s0 + s2 <= s1 or s1 + s2 <= s0:
        return None
    return [s0, s1, s2]


def _corners(sides: list[float]) -> list[tuple[float, float]]:
    s0, s1, s2 = sides
    x = (s2 * s2 + s1 * s1 - s0 * s0) / (2 * s2)
    return [(0.0, 0.0), (s2, 0.0), (x, math.sqrt(max(0.0, s1 * s1 - x * x)))]


def _holds(t: Triangle, corners: list[tuple[float, float]], sides: list[float]) -> bool:
    for index, value in t.stated_sides.items():
        if abs(sides[index] - value) > 1e-4 * max(1.0, value):
            return False
    for index, value in t.stated_angles.items():
        others = [corners[j] for j in range(3) if j != index]
        if abs(angle_at(corners[index], *others) - value) > 0.05:
            return False
    if t.height is not None and abs(corners[2][1] - t.height) > 1e-4 * max(1.0, t.height):
        return False
    return t.perimeter is None or abs(sum(sides) - t.perimeter) <= 1e-4 * t.perimeter


def _is_kind(shape: str, sides: list[float], corners: list[tuple[float, float]]) -> bool:
    """The triangle is the kind the question names: obtuse, acute, scalene."""
    biggest = max(angle_at(corners[i], *(corners[j] for j in range(3) if j != i)) for i in range(3))
    if shape == "obtuse_triangle":
        return biggest > 90 + _KIND_ANGLE
    if shape == "acute_triangle":
        return biggest < 90 - _KIND_ANGLE
    if shape == "scalene_triangle":
        return all(
            abs(sides[i] - sides[j]) > _KIND_SIDE * max(sides) for i, j in ((0, 1), (1, 2), (0, 2))
        )
    return True


def determined(request: FigureRequest) -> tuple[Placed, list[float]] | None:
    """The triangle the stated values decide by its laws alone (three sides, two legs, two
    sides and the angle between them), or None when they leave it open: a prism's end is
    drawn only as stated."""
    placed = place(request)
    if placed is None:
        return None
    solve(placed.triangle)
    sides = _sides(placed.triangle)
    if sides is None or not _holds(placed.triangle, _corners(sides), sides):
        return None
    return placed, sides


def build_triangle(request: FigureRequest) -> FigureSpec | None:
    placed = place(request)
    if placed is None:
        return None
    for choice in _CHOICES:
        triangle = copy.deepcopy(placed.triangle)
        sides = _complete(triangle, choice)
        if sides is None:
            continue
        corners = _corners(sides)
        if _holds(triangle, corners, sides) and _is_kind(request.shape, sides, corners):
            return _draw(request, triangle, placed, corners)
    return None


def _draw(
    request: FigureRequest, t: Triangle, placed: Placed, corners: list[tuple[float, float]]
) -> FigureSpec:
    names = placed.names
    drawing = Drawing(request.shape or "triangle")
    for name, corner in zip(names, corners, strict=True):
        drawing.point(corner, name, show=placed.show)
    drawing.outline(names)
    equal = {0, 1, 2} if t.equilateral else {0, 1} if t.isosceles else set()
    for index in range(3):
        a, b = names[(index + 1) % 3], names[(index + 2) % 3]
        value = t.stated_sides.get(index) if index in t.side_labels else None
        label = length_label(value, request.unit) if value is not None else None
        drawing.label_side(a, b, label, ticks=1 if index in equal else 0)
    for index in range(3):
        others = (names[(index + 1) % 3], names[(index + 2) % 3])
        if index == t.right:
            drawing.angle(names[index], *others, right=True)
        elif index in t.angle_labels:
            drawing.angle(names[index], *others, angle_label(t.stated_angles[index]))
    if t.height is not None:
        _draw_height(drawing, request, t.height, names, corners)
    return drawing.spec()


def _draw_height(
    drawing: Drawing,
    request: FigureRequest,
    height: float,
    names: list[str],
    corners: list[tuple[float, float]],
) -> None:
    """The dashed height from the apex to the base, the base drawn on to meet it when the
    foot falls outside."""
    base = corners[1][0]
    x = corners[2][0]
    if abs(x) < _TOLERANCE or abs(x - base) < _TOLERANCE:
        # The height is a side: a right angle at the base.
        at = names[0] if abs(x) < _TOLERANCE else names[1]
        drawing.label_side(at, names[2], length_label(height, request.unit))
        return
    foot = drawing.point((x, 0.0))
    drawing.line(names[2], foot, length_label(height, request.unit), dashed=True)
    if x < 0:
        drawing.line(names[0], foot, dashed=True)
    elif x > base:
        drawing.line(names[1], foot, dashed=True)
    drawing.angle(foot, names[0] if x > base else names[1], names[2], right=True)
