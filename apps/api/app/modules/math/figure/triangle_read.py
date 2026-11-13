"""Where a triangle's stated values go: which corner is right, which is the apex, and which
side or angle each value is.

A right angle sits where the question puts it: at the corner it names ("right-angled at
Q", angle C = 90°), opposite a hypotenuse it names, where two named legs meet, or opposite
the longest of three sides. An isosceles triangle's apex is where its equal sides meet: the
letter the question gives, the one two equal named sides share, or the corner opposite a
named base. A value whose place the question leaves open between two that differ (an
unnamed 40° in an isosceles triangle, apex or base; two sides of a right triangle, legs or
not) has no place, and nothing is drawn: a picture may choose what the question leaves
free, never which of its values is which.

Vertex 0 sits bottom left, vertex 1 bottom right, vertex 2 on top; side i is opposite
vertex i, so side 2 is the base. A right angle is at vertex 0, an apex at vertex 2 (a right
isosceles triangle's right angle is its apex).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.math.figure.request import FigureRequest, Measure

SIDE_ROLES = frozenset({"side", "base", "leg", "hypotenuse", "equal_side"})
ANGLE_ROLES = frozenset({"angle", "apex_angle", "base_angle"})
_TOLERANCE = 1e-6
# Named values first, then the roles that fix a place before those that take what is left.
_ROLE_ORDER = ("hypotenuse", "base", "equal_side", "leg", "side")


@dataclass
class Triangle:
    sides: list[float | None] = field(default_factory=lambda: [None, None, None])
    angles: list[float | None] = field(default_factory=lambda: [None, None, None])
    height: float | None = None
    perimeter: float | None = None
    isosceles: bool = False  # sides 0 and 1 equal, the apex at vertex 2
    equilateral: bool = False
    right: int | None = None
    # What the question stated, for the final check, and where each value is labelled.
    stated_sides: dict[int, float] = field(default_factory=dict)
    stated_angles: dict[int, float] = field(default_factory=dict)
    side_labels: set[int] = field(default_factory=set)
    angle_labels: set[int] = field(default_factory=set)


@dataclass
class Placed:
    triangle: Triangle
    names: list[str]  # the letters in drawing order
    show: bool  # letters shown: the picture claims nothing about letters the question leaves open


def _letters(request: FigureRequest) -> tuple[list[str], bool]:
    letters = request.vertices.strip()
    if len(letters) == 3 and len(set(letters)) == 3 and letters.isalpha():
        return list(letters), True
    return ["A", "B", "C"], False


def _vertex(name: str) -> str:
    """ "A" for angle A; the middle letter of "ABC" (the angle at B)."""
    letters = name.strip()
    return letters[1] if len(letters) == 3 else letters[:1]


def _opposite(name: str, letters: list[str]) -> str | None:
    pair = name.strip()
    if len(pair) != 2 or pair[0] == pair[1] or not set(pair) <= set(letters):
        return None
    return (set(letters) - set(pair)).pop()


def _single(found: set[str], banned: set[str], letters: list[str]) -> tuple[bool, str | None]:
    if len(found) > 1 or found & banned or not found <= set(letters):
        return False, None
    return True, (next(iter(found)) if found else None)


def _right_letter(request: FigureRequest, letters: list[str]) -> tuple[bool, str | None]:
    found: set[str] = set()
    legs: list[set[str]] = []
    for m in request.measures:
        name = m.name.strip()
        if m.what in ANGLE_ROLES and abs(m.value - 90) < _TOLERANCE and name:
            found.add(_vertex(name))
        elif m.what == "hypotenuse" and (opposite := _opposite(name, letters)):
            found.add(opposite)
        elif m.what == "leg" and _opposite(name, letters):
            legs.append(set(name))
    if len(legs) >= 2:
        found |= legs[0] & legs[1]
    named = [m for m in request.measures if m.what == "side" and _opposite(m.name, letters)]
    if not found and request.shape == "right_triangle" and len(named) == 3:
        longest = max(named, key=lambda m: m.value)
        if sum(abs(m.value - longest.value) < _TOLERANCE for m in named) == 1:
            found.add(_opposite(longest.name, letters) or "")
    return _single(found, set(), letters)


def _apex_letter(request: FigureRequest, letters: list[str]) -> tuple[bool, str | None]:
    found = {request.apex} if request.apex else set()
    banned: set[str] = set()
    pairs = [
        (set(m.name.strip()), m.value)
        for m in request.measures
        if m.what in {"side", "equal_side"} and _opposite(m.name, letters)
    ]
    for i, (pair, value) in enumerate(pairs):
        for other, other_value in pairs[i + 1 :]:
            if abs(value - other_value) < _TOLERANCE:
                found |= pair & other
    for m in request.measures:
        name = m.name.strip()
        if m.what == "base" and (opposite := _opposite(name, letters)):
            found.add(opposite)
        elif m.what == "apex_angle" and name:
            found.add(_vertex(name))
        elif m.what == "base_angle" and name:
            banned.add(_vertex(name))
    if len(found) == 3:
        found = set()  # three equal sides: any corner is an apex
    return _single(found, banned, letters)


def _rotated(names: list[str], first: str) -> list[str]:
    at = names.index(first)
    return names[at:] + names[:at]


def place(request: FigureRequest) -> Placed | None:
    letters, lettered = _letters(request)
    shape = request.shape
    named = any(m.name.strip() for m in request.measures)
    right = shape == "right_triangle" or any(
        m.what in ANGLE_ROLES and abs(m.value - 90) < _TOLERANCE for m in request.measures
    )
    isosceles = shape == "isosceles_triangle"
    ok, right_at = _right_letter(request, letters)
    apex_ok, apex = _apex_letter(request, letters) if isosceles else (True, None)
    if not (ok and apex_ok):
        return None
    show = lettered
    if isosceles:
        if right_at is not None and apex is not None and right_at != apex:
            return None
        top = apex or right_at
        if top is None and lettered and named:
            return None
        show = lettered and top is not None
        names = [*_rotated(letters, top)[1:], top] if top else letters
        right_index = 2 if right else None
    elif right:
        if right_at is None and lettered and named:
            return None
        show = lettered and right_at is not None
        names = _rotated(letters, right_at) if right_at else letters
        right_index = 0
    else:
        names, right_index = letters, None
    t = Triangle(
        isosceles=isosceles or shape == "equilateral_triangle",
        equilateral=shape == "equilateral_triangle",
        right=right_index,
    )
    if right_index is not None:
        t.angles[right_index] = t.stated_angles[right_index] = 90.0
    if shape == "equilateral_triangle":
        t.angles = [60.0, 60.0, 60.0]
    return Placed(t, names, show) if _read(request, t, names) else None


def _order(measure: Measure) -> tuple[int, int]:
    role = _ROLE_ORDER.index(measure.what) if measure.what in _ROLE_ORDER else len(_ROLE_ORDER)
    return (0 if measure.name.strip() else 1, role)


def _read(request: FigureRequest, t: Triangle, names: list[str]) -> bool:
    plain: list[float] = []
    for m in sorted(request.measures, key=_order):
        if m.what == "side" and not m.name.strip() and not t.equilateral:
            plain.append(m.value)
        elif m.what == "height":
            t.height = m.value
        elif m.what == "perimeter":
            t.perimeter = m.value
        elif m.what in SIDE_ROLES:
            if not _side(t, m, names):
                return False
        elif m.what not in ANGLE_ROLES or not _angle(t, m, names):
            return False
    return _plain_sides(t, plain)


def _set_side(t: Triangle, index: int, value: float, *, label: bool = True) -> bool:
    known = t.stated_sides.get(index)
    if known is not None and abs(known - value) > _TOLERANCE * max(1.0, value):
        return False
    t.sides[index] = t.stated_sides[index] = value
    if label and known is None:
        t.side_labels.add(index)
    return True


def _free(t: Triangle, order: tuple[int, ...]) -> int | None:
    return next((i for i in order if i not in t.stated_sides), None)


def _side(t: Triangle, m: Measure, names: list[str]) -> bool:
    if t.equilateral:
        labelled = bool(t.side_labels)
        return all(_set_side(t, i, m.value, label=i == 2 and not labelled) for i in range(3))
    opposite = _opposite(m.name, names)
    if opposite is not None:
        index = names.index(opposite)
        if (m.what == "hypotenuse" and index != t.right) or (
            m.what == "leg" and (t.right is None or index == t.right)
        ):
            return False
        if t.isosceles and (
            (m.what == "base" and index != 2) or (m.what == "equal_side" and index == 2)
        ):
            return False
        return _set_side(t, index, m.value)
    if m.name.strip():
        return False
    if m.what == "hypotenuse":
        return t.right is not None and _set_side(t, t.right, m.value)
    if m.what == "leg":
        leg = _free(t, tuple(i for i in (2, 1, 0) if i != t.right)) if t.right is not None else None
        return leg is not None and _set_side(t, leg, m.value)
    if m.what == "equal_side":
        return t.isosceles and _set_side(t, 1, m.value)
    base = 2 if t.isosceles else _free(t, (2,))
    return base is not None and _set_side(t, base, m.value)


def _plain_sides(t: Triangle, plain: list[float]) -> bool:
    """Sides the question gives without a role, placed only where their roles are certain."""
    if not plain:
        return True
    if t.isosceles:
        if 2 in t.stated_sides:
            return all(_set_side(t, i, v, label=i == 1) for v in plain for i in (1, 0))
        if 1 in t.stated_sides and len(plain) == 1:
            return _set_side(t, 2, plain[0])
        values = sorted(plain)
        if len(values) == 1:
            return _set_side(t, 1, values[0])
        pairs = [v for v in values if sum(abs(v - w) < _TOLERANCE for w in values) >= 2]
        odd = [v for v in values if v not in pairs]
        if not pairs or len(odd) > 1:
            return False
        rest = pairs[2:] + odd  # three equal sides, or the base
        return (
            _set_side(t, 1, pairs[0])
            and _set_side(t, 0, pairs[1])
            and all(_set_side(t, 2, v) for v in rest)
        )
    if t.right is not None:
        legs = tuple(i for i in (2, 1, 0) if i != t.right)
        if len(plain) == 3 and not t.stated_sides:
            values = sorted(plain)
            return _set_side(t, t.right, values[2]) and all(
                _set_side(t, i, v) for i, v in zip(legs, reversed(values[:2]), strict=True)
            )
        if t.right not in t.stated_sides:
            return False  # legs or a hypotenuse: the question does not say
        for value in sorted(plain, reverse=True):
            index = _free(t, legs)
            if index is None or not _set_side(t, index, value):
                return False
        return True
    for value in plain:
        index = _free(t, (2, 0, 1))
        if index is None or not _set_side(t, index, value):
            return False
    return True


def _angle(t: Triangle, m: Measure, names: list[str]) -> bool:
    name = m.name.strip()
    if name:
        vertex = _vertex(name)
        if vertex not in names:
            return False
        index = names.index(vertex)
        if (m.what == "apex_angle" and index != 2) or (m.what == "base_angle" and index == 2):
            return False
    elif t.right is not None and abs(m.value - 90) < _TOLERANCE and t.right not in t.angle_labels:
        return True  # the right angle, drawn as its box
    elif m.what == "apex_angle" or (t.isosceles and m.what == "angle" and m.value >= 90):
        index = 2  # an isosceles triangle's right or obtuse angle is its apex
    elif m.what == "base_angle":
        index = 0
    elif t.isosceles and not t.equilateral:
        return False  # apex or base: the question does not say
    else:
        free = [i for i in (1, 2, 0) if i not in t.stated_angles]
        if not free:
            return False
        index = free[0]
    if m.what in {"apex_angle", "base_angle"} and not t.isosceles:
        return False
    known = t.stated_angles.get(index)
    if known is not None and abs(known - m.value) > _TOLERANCE:
        return False
    t.angles[index] = t.stated_angles[index] = m.value
    if index != t.right:
        t.angle_labels.add(index)
    return True
