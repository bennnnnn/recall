"""A triangle drawn from what the question states, and nothing it does not.

The question's sides and angles are placed on the triangle (by the letters it uses, or by
their roles: a base, legs, the equal sides); the rest is worked out by the triangle's laws
when they decide it, and otherwise chosen so the stated values still hold (an isosceles
triangle's base angles, an angle the question leaves open). Only stated values are
labelled: a length the question asks for is drawn to its size, unlabelled. A statement the
triangle cannot meet (sides 2, 3, 9; angles summing past 180°) draws nothing.

Vertex 0 sits bottom left, vertex 1 bottom right, vertex 2 on top; side i is the one
opposite vertex i, so the base is side 2. A right angle is at vertex 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.modules.math.figure.drawing import Drawing, angle_label, length_label
from app.modules.math.figure.request import FigureRequest, Measure
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
_SIDE_ROLES = frozenset({"side", "base", "leg", "hypotenuse", "equal_side"})
# Shapes chosen for what the question leaves open: a scalene triangle's angles, an
# isosceles one's base angles, the angle between two sides given without it.
_SCALENE = (58.0, 72.0, 50.0)
_BASE_ANGLE = 65.0
_INCLUDED = 65.0
_DEFAULT_BASE = 5.0
# A base-and-height triangle's apex, as a share of the base from its left end.
_APEX_SHARE = 0.35
_TOLERANCE = 1e-6


@dataclass
class _Triangle:
    sides: list[float | None] = field(default_factory=lambda: [None, None, None])
    angles: list[float | None] = field(default_factory=lambda: [None, None, None])
    height: float | None = None
    perimeter: float | None = None
    isosceles: bool = False
    # What the question stated, for the labels and the final check.
    stated_sides: dict[int, float] = field(default_factory=dict)
    stated_angles: dict[int, float] = field(default_factory=dict)


def _names(request: FigureRequest) -> tuple[list[str], bool]:
    letters = request.vertices.strip()
    if len(letters) == 3 and len(set(letters)) == 3 and letters.isalpha():
        return list(letters), True
    return ["A", "B", "C"], False


def _right_vertex(request: FigureRequest, names: list[str]) -> str | None:
    for measure in request.given("angle"):
        if abs(measure.value - 90) < _TOLERANCE:
            name = _vertex_name(measure.name)
            return name if name in names else names[0]
    return names[0] if request.shape == "right_triangle" else None


def _vertex_name(name: str) -> str:
    """ "A" for angle A; the middle letter of "ABC" (the angle at B)."""
    letters = name.strip()
    return letters[1] if len(letters) == 3 else letters[:1]


def _rotated(names: list[str], first: str) -> list[str]:
    at = names.index(first)
    return names[at:] + names[:at]


def _set_side(triangle: _Triangle, index: int, value: float) -> bool:
    known = triangle.stated_sides.get(index)
    if known is not None and abs(known - value) > _TOLERANCE * max(1.0, value):
        return False
    triangle.sides[index] = value
    triangle.stated_sides[index] = value
    return True


def _place_side(triangle: _Triangle, measure: Measure, names: list[str], order: list[int]) -> bool:
    letters = measure.name.strip()
    if len(letters) == 2 and set(letters) <= set(names) and letters[0] != letters[1]:
        index = ({0, 1, 2} - {names.index(letters[0]), names.index(letters[1])}).pop()
        return _set_side(triangle, index, measure.value)
    free = [index for index in order if index not in triangle.stated_sides]
    return bool(free) and _set_side(triangle, free[0], measure.value)


def _unnamed_order(measure: Measure, right: bool) -> list[int]:
    """Where an unnamed side goes: a base on the bottom, legs at the right angle."""
    if measure.what == "hypotenuse":
        return [0]
    if measure.what == "base":
        return [2]
    if measure.what == "equal_side":
        return [0, 1]
    if right:
        return [2, 1] if measure.what == "leg" else [2, 1, 0]
    return [2, 0, 1]


def _read(request: FigureRequest, names: list[str], right: bool) -> _Triangle | None:
    triangle = _Triangle(isosceles=request.shape in {"isosceles_triangle", "equilateral_triangle"})
    for measure in request.measures:
        if measure.what in _SIDE_ROLES:
            order = _unnamed_order(measure, right)
            if request.shape == "equilateral_triangle":
                for index in range(3):
                    if not _set_side(triangle, index, measure.value):
                        return None
            elif not _place_side(triangle, measure, names, order):
                return None
            if measure.what == "equal_side" and not measure.name:
                if not _set_side(triangle, 1, measure.value):
                    return None
        elif measure.what == "angle":
            vertex = _vertex_name(measure.name)
            if vertex in names:
                index = names.index(vertex)
            else:
                free = [i for i in (1, 2, 0) if i not in triangle.stated_angles]
                if not free:
                    return None
                index = free[0]
            triangle.angles[index] = measure.value
            triangle.stated_angles[index] = measure.value
        elif measure.what == "height":
            triangle.height = measure.value
        elif measure.what == "perimeter":
            triangle.perimeter = measure.value
        else:
            return None
    if right:
        triangle.angles[0] = 90.0
    if request.shape == "equilateral_triangle":
        triangle.angles = [60.0, 60.0, 60.0]
    return triangle


def _law_step(t: _Triangle) -> bool:
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


def _height_step(t: _Triangle) -> bool:
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


def _cosine_step(t: _Triangle) -> bool:
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


def _sine_step(t: _Triangle) -> bool:
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


def _solve(t: _Triangle) -> None:
    for _ in range(12):
        if not _law_step(t):
            return


def _default_step(t: _Triangle) -> bool:
    """Choose one value the question leaves open, keeping every stated one."""
    s, a = t.sides, t.angles
    known = [i for i in range(3) if a[i] is not None]
    if t.isosceles and a[0] is None and a[2] is None:
        a[0] = a[1] = _BASE_ANGLE
        return True
    sides = [i for i in range(3) if s[i] is not None]
    if not known and len(sides) == 2:
        a[3 - sides[0] - sides[1]] = _INCLUDED
        return True
    if t.height is not None and s[2] is not None and not known:
        apex = (s[2] * _APEX_SHARE, t.height)
        s[1] = math.hypot(*apex)
        s[0] = math.hypot(s[2] - apex[0], apex[1])
        return True
    if len(known) == 1:
        rest = 180.0 - float(a[known[0]] or 0)
        free = [i for i in range(3) if i != known[0]]
        a[free[0]] = rest * 0.5 if t.isosceles else rest * 0.55
        return True
    if not known:
        a[:] = [*_SCALENE]
        return True
    if all(x is None for x in s):
        s[2] = _DEFAULT_BASE
        return True
    return False


def _complete(t: _Triangle) -> list[float] | None:
    _solve(t)
    for _ in range(4):
        if all(x is not None for x in t.sides) and all(x is not None for x in t.angles):
            break
        if not _default_step(t):
            break
        _solve(t)
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


def _holds(t: _Triangle, corners: list[tuple[float, float]], sides: list[float]) -> bool:
    from app.modules.math.figure.drawing import angle_at

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


def _apex(request: FigureRequest, names: list[str]) -> str | None:
    """An isosceles triangle's apex by the letters its equal sides or base are named with:
    the equal sides meet there, and the base is the side opposite it."""
    for measure in request.measures:
        letters = measure.name.strip()
        if len(letters) != 2 or not set(letters) <= set(names):
            continue
        if measure.what == "base":
            return (set(names) - set(letters)).pop()
        if measure.what == "equal_side":
            others = [m.name.strip() for m in request.given("equal_side") if m is not measure]
            shared = [c for other in others for c in other if c in letters]
            if shared:
                return shared[0]
    return None


def _arranged(request: FigureRequest, names: list[str]) -> tuple[list[str], str | None]:
    """The letters in drawing order: a right angle at vertex 0, an apex at vertex 2."""
    right_at = _right_vertex(request, names)
    if right_at is not None:
        return _rotated(names, right_at), right_at
    if request.shape == "isosceles_triangle":
        apex = _apex(request, names)
        if apex is not None:
            return [*_rotated(names, apex)[1:], apex], None
    return names, None


def build_triangle(request: FigureRequest) -> FigureSpec | None:
    names, lettered = _names(request)
    names, right_at = _arranged(request, names)
    triangle = _read(request, names, right_at is not None)
    if triangle is None:
        return None
    named = any(len(m.name.strip()) == 2 for m in request.measures)
    if right_at is not None and not named and sorted(triangle.stated_sides) == [1, 2]:
        # Two legs: the longer lies along the bottom, as a textbook draws it.
        legs = sorted(triangle.stated_sides.values(), reverse=True)
        triangle.stated_sides = {2: legs[0], 1: legs[1]}
        triangle.sides = [None, legs[1], legs[0]]
    sides = _complete(triangle)
    if sides is None:
        return None
    corners = _corners(sides)
    if not _holds(triangle, corners, sides):
        return None
    return _draw(request, triangle, names, lettered, corners, right_at is not None)


def _draw(
    request: FigureRequest,
    t: _Triangle,
    names: list[str],
    lettered: bool,
    corners: list[tuple[float, float]],
    right: bool,
) -> FigureSpec:
    drawing = Drawing(request.shape or "triangle")
    for name, corner in zip(names, corners, strict=True):
        drawing.point(corner, name, show=lettered)
    drawing.outline(names)
    equal = _equal_sides(request, t)
    for index in range(3):
        a, b = names[(index + 1) % 3], names[(index + 2) % 3]
        value = t.stated_sides.get(index)
        label = length_label(value, request.unit) if value is not None else None
        drawing.label_side(a, b, label, ticks=1 if index in equal else 0)
    for index in range(3):
        others = (names[(index + 1) % 3], names[(index + 2) % 3])
        if index == 0 and right:
            drawing.angle(names[0], *others, right=True)
        elif index in t.stated_angles:
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


def _equal_sides(request: FigureRequest, t: _Triangle) -> set[int]:
    if request.shape == "equilateral_triangle":
        return {0, 1, 2}
    if t.isosceles:
        return {0, 1}
    return set()
