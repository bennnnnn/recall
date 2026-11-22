"""A right triangle with the altitude from its right angle to the hypotenuse.

The altitude cuts the hypotenuse c into two parts, p and q, and the triangle into two
similar to it: c = p + q, the altitude h² = pq, and each leg² = c times the part beside it.
So any two values the question states (both parts, the hypotenuse and a part, the altitude
and a part, two legs, ...) decide the whole figure; what it asks for (the legs, the
altitude) is drawn to its size, unlabelled. Two values that leave which part is which open
in a way that changes the triangle (an unnamed leg and an unnamed part: beside each other,
or not) draw nothing, and so do values no such triangle has (parts that do not add up to the
hypotenuse, an altitude over half of it).

The hypotenuse lies along the bottom, the right angle above it, the altitude dashed down
to its foot with both right angles marked. A hypotenuse stated beside its parts is labelled
on a dashed line under the triangle, its whole length, clear of the parts' labels.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import pairwise, product

from app.modules.math.figure.drawing import Drawing, length_label
from app.modules.math.figure.request import FigureRequest, Measure
from app.modules.math.figure.triangles import TRIANGLES
from app.modules.math.schemas.figure import FigureSpec

# Each length the figure has, at the shape where the left part is ``t`` of the hypotenuse
# and the hypotenuse is 1: the two parts, the hypotenuse, the altitude, the left leg (beside
# the left part) and the right leg.
_LENGTHS: dict[str, Callable[[float], float]] = {
    "p": lambda t: t,
    "q": lambda t: 1 - t,
    "c": lambda t: 1.0,
    "h": lambda t: math.sqrt(t * (1 - t)),
    "a": lambda t: math.sqrt(t),
    "b": lambda t: math.sqrt(1 - t),
}
# What each measure of the reading may be: a part of the hypotenuse is either part.
_ROLES = {"hypotenuse": ("c",), "height": ("h",), "length": ("p", "q"), "leg": ("a", "b")}
# The shape drawn when the question states one value: its parts 9 to 16 (legs 3 to 4).
_SHARE = 0.36
_SCALE = 5.0
_STEPS = 2000
_TOLERANCE = 1e-4
# Under the hypotenuse, this far against it: where its whole length is labelled.
_BELOW = 0.12
# "height" alone is a leg ("base 6, height 8 and hypotenuse 10"): only the altitude words.
_WORDS = re.compile(r"\b(?:altitude|perpendicular)\b")
_HYPOTENUSE = re.compile(r"\bhypotenuse\b")


def wanted(request: FigureRequest) -> bool:
    """The reading is a right triangle with the altitude to its hypotenuse drawn."""
    return request.has_part("altitude") and (
        request.shape == "right_triangle" or request.first("hypotenuse") is not None
    )


def as_said(request: FigureRequest, texts: Sequence[str]) -> FigureRequest:
    """A right triangle the question draws the altitude of, onto its hypotenuse ("the
    altitude from the right angle divides the hypotenuse into 9 cm and 16 cm"), marked so:
    the read gave the parts as lengths and named no altitude (2026-11-21)."""
    if request.kind != "polygon" or request.shape not in TRIANGLES or request.has_part("altitude"):
        return request
    if request.shape != "right_triangle" and request.first("hypotenuse") is None:
        return request
    words = " ".join(texts).lower()
    if not (_WORDS.search(words) and _HYPOTENUSE.search(words)):
        return request
    return request.model_copy(update={"parts": [*request.parts, "altitude"]})


@dataclass(frozen=True)
class _Letters:
    """The corners' letters: the hypotenuse's left and right ends, the right angle, the
    altitude's foot ("" when the question letters none); ``show`` when they are the
    question's."""

    left: str = "A"
    right: str = "B"
    corner: str = "C"
    foot: str = "D"
    show: bool = False

    def role(self, name: str) -> str | None:
        """The length a two-letter name is: "AD" the left part, "BC" the right leg."""
        ends = set(name.strip())
        names = {
            frozenset({self.left, self.foot}): "p",
            frozenset({self.foot, self.right}): "q",
            frozenset({self.left, self.right}): "c",
            frozenset({self.corner, self.foot}): "h",
            frozenset({self.left, self.corner}): "a",
            frozenset({self.corner, self.right}): "b",
        }
        return names.get(frozenset(ends)) if len(ends) == 2 else None


def _vertex(name: str) -> str:
    """The corner an angle's name puts it at: "C" and "ACB" are at C; "" for none."""
    letters = name.strip()
    return letters[1] if len(letters) == 3 else letters if len(letters) == 1 else ""


def _letters(request: FigureRequest) -> _Letters:
    """The question's letters: three corners (the right angle where an angle of 90° is, or
    off the hypotenuse it names) and the foot (a fourth letter, or the one the parts' names
    add); the drawing's own, hidden, when they leave a corner open."""
    corners = request.vertices.strip()[:3]
    if len(corners) != 3 or len(set(corners)) != 3 or not corners.isalpha():
        return _Letters()
    right = [_vertex(m.name) for m in request.given("angle") if abs(m.value - 90) < 1e-9]
    for m in request.given("hypotenuse"):
        right += [c for c in corners if c not in m.name and len(m.name.strip()) == 2]
    right = [c for c in right if c]
    if len(set(right)) != 1 or right[0] not in corners:
        return _Letters()
    corner = right[0]
    left, far = (c for c in corners if c != corner)
    named = "".join(m.name.strip() for m in request.measures)
    extra = {c for c in request.vertices.strip()[3:] + named if c.isalpha()} - set(corners)
    if len(extra) > 1:
        return _Letters()
    return _Letters(left, far, corner, extra.pop() if extra else "", show=True)


def _items(request: FigureRequest, letters: _Letters) -> list[tuple[tuple[str, ...], Measure]]:
    """Each stated length with the parts of the figure it may be. A value of no part of
    this figure (an acute angle, a perimeter) raises: the figure is not this one."""
    items: list[tuple[tuple[str, ...], Measure]] = []
    for m in request.measures:
        if m.what == "angle" and abs(m.value - 90) < 1e-9:
            continue  # the right angle, boxed
        roles = _ROLES.get(m.what)
        if roles is None:
            raise ValueError(f"no {m.what} in a right triangle's altitude figure")
        named = letters.role(m.name) if letters.show else None
        # A length is any part its letters name ("AC" a leg); another value is its own.
        if named is not None and named not in roles and m.what != "length":
            raise ValueError(f"{m.name} is no {m.what}")
        items.append(((named,) if named else roles, m))
    return items


def _shares(first: tuple[str, float], second: tuple[str, float]) -> list[float]:
    """Every shape (the left part's share of the hypotenuse) at which the two values hold
    together: where their lengths' ratio is the stated one."""

    def gap(t: float) -> float:
        return _LENGTHS[first[0]](t) * second[1] - _LENGTHS[second[0]](t) * first[1]

    grid = [(i + 0.5) / _STEPS for i in range(_STEPS)]
    found: list[float] = []
    for low, high in pairwise(grid):
        if gap(low) == 0 or gap(low) * gap(high) < 0:
            found.append(_bisect(gap, low, high))
    for i in range(1, len(grid) - 1):
        # A double root (an altitude exactly half the hypotenuse) touches zero: no sign change.
        here = abs(gap(grid[i]))
        if here <= abs(gap(grid[i - 1])) and here <= abs(gap(grid[i + 1])):
            t = _lowest(gap, grid[i - 1], grid[i + 1])
            if abs(gap(t)) < 1e-9 * max(first[1], second[1]):
                found.append(t)
    unique: list[float] = []
    for t in sorted(found):
        if not unique or t - unique[-1] > 1e-6:
            unique.append(t)
    return unique


def _bisect(gap: Callable[[float], float], low: float, high: float) -> float:
    for _ in range(60):
        middle = (low + high) / 2
        if gap(low) * gap(middle) <= 0:
            high = middle
        else:
            low = middle
    return (low + high) / 2


def _lowest(gap: Callable[[float], float], low: float, high: float) -> float:
    for _ in range(100):
        a, b = low + (high - low) / 3, high - (high - low) / 3
        if abs(gap(a)) < abs(gap(b)):
            high = b
        else:
            low = a
    return (low + high) / 2


@dataclass(frozen=True)
class _Solved:
    share: float
    scale: float
    roles: tuple[str, ...]


def _fits(items: list[tuple[tuple[str, ...], Measure]], roles: tuple[str, ...]) -> list[_Solved]:
    """The figures in which each item is the part ``roles`` gives it."""
    values = [(role, m.value) for role, (_, m) in zip(roles, items, strict=True)]
    pair = next(((x, y) for x in values for y in values if x[0] != y[0]), None)
    shares = _shares(*pair) if pair else [_SHARE]
    solved: list[_Solved] = []
    for t in shares:
        scale = values[0][1] / _LENGTHS[values[0][0]](t) if values else _SCALE
        if all(abs(_LENGTHS[r](t) * scale - v) <= _TOLERANCE * v for r, v in values):
            solved.append(_Solved(t, scale, roles))
    return solved


def _solve(items: list[tuple[tuple[str, ...], Measure]]) -> _Solved | None:
    """The one figure the stated values decide, its left and right free to swap; None when
    they decide none, or two different ones."""
    found: list[_Solved] = []
    for roles in product(*(choices for choices, _ in items)):
        if _shares_a_part(items, roles):
            continue
        found += _fits(items, roles)
    shapes = {round(min(s.share, 1 - s.share), 6) for s in found}
    return found[0] if len(shapes) == 1 else None


def _shares_a_part(items: list[tuple[tuple[str, ...], Measure]], roles: tuple[str, ...]) -> bool:
    """Two values given one part that either could be another: two legs of 6 are both legs
    (an isosceles right triangle), two parts of 8 both parts (the altitude at the middle),
    never one part twice, the other unlabelled (review, #2522). A part stated twice (the
    hypotenuse, a side its letters name) is that part both times."""
    open_roles = [role for role, (choices, _) in zip(roles, items, strict=True) if len(choices) > 1]
    return len(set(open_roles)) < len(open_roles)


def build_right_altitude(request: FigureRequest) -> FigureSpec | None:
    letters = _letters(request)
    try:
        items = _items(request, letters)
    except ValueError:
        return None
    solved = _solve(items)
    if solved is None or not 0 < solved.share < 1:
        return None
    t, c = solved.share, solved.scale
    labels: dict[str, str] = {}
    for role, (_, m) in zip(solved.roles, items, strict=True):
        labels.setdefault(role, length_label(m.value, request.unit))
    return _draw(request, letters, (t * c, c, math.sqrt(t * (1 - t)) * c), labels)


def _draw(
    request: FigureRequest,
    letters: _Letters,
    size: tuple[float, float, float],
    labels: dict[str, str],
) -> FigureSpec:
    p, c, h = size
    drawing = Drawing(request.shape or "right_triangle")
    show = letters.show
    a = drawing.point((0.0, 0.0), letters.left, show=show)
    b = drawing.point((c, 0.0), letters.right, show=show)
    top = drawing.point((p, h), letters.corner, show=show)
    foot = drawing.point((p, 0.0), letters.foot, show=show and bool(letters.foot))
    drawing.outline([a, b, top])
    drawing.label_side(a, top, labels.get("a"))
    drawing.label_side(top, b, labels.get("b"))
    drawing.line(top, foot, labels.get("h"), dashed=True)
    for ends, role in (((a, foot), "p"), ((foot, b), "q")):
        if role in labels:
            drawing.line(*ends, labels[role])
    whole = labels.get("c")
    if whole is not None and ({"p", "q"} & labels.keys()) and not show:
        # Its whole length under it, clear of the parts' labels on it.
        low, high = drawing.point((0.0, -_BELOW * c)), drawing.point((c, -_BELOW * c))
        drawing.line(low, high, whole, dashed=True)
        drawing.line(a, low, dashed=True)
        drawing.line(b, high, dashed=True)
    else:
        drawing.label_side(a, b, whole)
    drawing.angle(top, a, b, right=True)
    drawing.angle(foot, b, top, right=True)
    return drawing.spec()
