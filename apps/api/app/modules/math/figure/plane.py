"""Coordinate geometry drawn where the question puts it, as a ```graph ``points`` plane.

A segment between two stated points (its midpoint, its rise and run, its perpendicular
bisector), a polygon at its stated vertices (its exact right angles and equal sides
marked), a circle the question writes an equation of (its centre and radius worked out by
SymPy) or gives a centre and radius of, and the image of a stated transformation
(``transforms``) with primed letters, dashed in a second colour. Every point drawn for
the question's own shape is a pair it writes (``grounding``); every other point is worked
out here, exactly. The question writing a formula the picture would leave out draws
nothing, and so does a polygon whose stated order crosses itself.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from app.modules.math.figure import plane_parts, transforms
from app.modules.math.figure.drawing import length_label
from app.modules.math.figure.grounding import own_texts, unit_name, written_pairs
from app.modules.math.figure.plane_draw import Exact, Plane, centroid, side_from
from app.modules.math.figure.plane_text import point_label, primes
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import PlaneRole

# Parts a segment between two points is drawn with, as the read names them.
SEGMENT_PARTS = frozenset(
    {"midpoint", "gradient", "slope", "distance", "length", "perpendicular_bisector", "bisector"}
)
_CENTRE_WORD = re.compile(r"\bcent(?:re|er)\b", re.IGNORECASE)
_CIRCLE_WORD = re.compile(r"\bcircle\b", re.IGNORECASE)
# A circle through a stated point: its radius is the distance to it.
_THROUGH = re.compile(r"\bpass(?:es|ing)? through\b|\bthrough the point\b", re.IGNORECASE)
Stated = list[tuple[str, Exact]]


def is_plane(request: FigureRequest, texts: Sequence[str]) -> bool:
    """The reading is coordinate geometry this draws: its points joined, a part asked of
    them, a transformation, a circle's equation, a polygon or a circle placed at pairs."""
    if request.kind not in {"points", "polygon", "circle"}:
        return False
    if request.equation.strip() or request.transforms:
        return True
    if _circle_asked(request, own_texts(texts)):
        return _centre_pair(own_texts(texts)) is not None
    if request.kind == "polygon":
        return len(request.points) >= 3
    return bool(request.join) or any(part in SEGMENT_PARTS for part in request.parts)


def _circle_asked(request: FigureRequest, texts: Sequence[str]) -> bool:
    """A circle on the plane: one written as an equation, or one the question gives a
    centre pair of (with a radius, a diameter or a point it passes through)."""
    if request.equation.strip():
        return True
    if request.kind == "circle" or request.first("radius", "diameter") is not None:
        return request.kind in {"circle", "points"}
    return request.kind == "points" and _centre_pair(texts) is not None


def _stated(request: FigureRequest, texts: Sequence[str]) -> Stated | None:
    found: Stated = []
    for point in request.points:
        pair = transforms.exact_pair(point.x, point.y, texts)
        if pair is None:
            return None
        found.append((point.name.strip(), pair))
    names = [name for name, _ in found if name]
    return found if len(set(names)) == len(names) else None


def _without(stated: Stated, pairs: Sequence[Exact], texts: Sequence[str]) -> Stated:
    """The stated points less a vector or centre the read listed among them: an unnamed
    point at a pair the question writes only once, as that vector or centre."""
    return [
        (name, at)
        for name, at in stated
        if name or at not in pairs or not transforms.stated_pair_only_once(at, texts)
    ]


def _centre_pair(texts: Sequence[str]) -> Exact | None:
    """The pair the question writes right after "centre" ("centre (2, -1)", "center C(0,
    3)"), when it writes a circle."""
    for text in texts:
        if not _CIRCLE_WORD.search(text):
            continue
        for word in _CENTRE_WORD.finditer(text):
            after = text[word.end() : word.end() + 24]
            pairs = written_pairs(after)
            if pairs and after.find("(") <= 12:
                return pairs[0]
    return None


def _groups(stated: Stated) -> list[Stated]:
    """The stated points by their primes: a shape and the image the question states of it
    ("A, B, C" and "A', B', C'") are two shapes."""
    groups: dict[int, Stated] = {}
    for name, at in stated:
        groups.setdefault(primes(name) if name else 0, []).append((name, at))
    return [groups[key] for key in sorted(groups)]


def _join(request: FigureRequest, size: int) -> str:
    if request.join:
        return request.join
    if request.transforms or request.kind == "polygon":
        return "polygon" if size >= 3 else "segment" if size == 2 else ""
    return "segment" if size == 2 and any(p in SEGMENT_PARTS for p in request.parts) else ""


def _draw_group(plane: Plane, request: FigureRequest, group: Stated, *, image: bool) -> bool:
    """One shape: its points labelled away from its middle, joined as the read says."""
    corners = [at for _, at in group]
    middle = centroid(corners)
    role: PlaneRole = "image" if image else "shape"
    for name, at in group:
        plane.point(at, point_label(name, at), role, side_from(at, middle))
        plane.names.add(name)
    join = _join(request, len(group))
    if join == "polygon" and len(group) >= 3:
        return plane_parts.polygon(plane, corners, role, request.parts)
    if join in {"segment", "polygon"} and len(group) >= 2:
        for a, b in itertools.pairwise(corners):
            plane.segment(a, b, role=role, dashed=image)
    return True


def _circle_from_equation(written: str, texts: Sequence[str]) -> tuple[Exact, Fraction] | None:
    """A circle the question writes ("x² + y² - 6x + 4y - 12 = 0", "(x - 2)² + (y + 1)² =
    25"): its centre and squared radius, exactly, when the read's equation is that one."""
    from app.modules.math.tool_check import written_relations

    relations = written_relations(written)
    if len(relations) != 1 or relations[0][1] != "=":
        return None
    read = _circle(relations[0][0] - relations[0][2])
    if read is None:
        return None
    for text in texts:
        for lhs, op, rhs in written_relations(text):
            own = _circle(lhs - rhs) if op == "=" else None
            if own is not None and own[0] == read[0] and own[1] == read[1]:
                return own
    return None


def _circle(difference: Any) -> tuple[Exact, Fraction] | None:
    import sympy

    x, y = sympy.symbols("x y")
    expanded = sympy.expand(difference)
    if expanded.free_symbols != {x, y}:
        return None
    try:
        poly = sympy.Poly(expanded, x, y)
    except sympy.PolynomialError:
        return None
    coeff = poly.coeff_monomial
    a = coeff(x**2)
    if poly.total_degree() != 2 or a == 0 or coeff(y**2) != a or coeff(x * y) != 0:
        return None
    values = [coeff(x) / a, coeff(y) / a, coeff(1) / a]
    if not all(isinstance(value, sympy.Rational) for value in values):
        return None
    d, e, f = (Fraction(str(value)) for value in values)
    centre = (-d / 2, -e / 2)
    squared = centre[0] ** 2 + centre[1] ** 2 - f
    return (centre, squared) if squared > 0 else None


@dataclass(frozen=True)
class _Circle:
    centre: Exact
    squared: Fraction
    # The radius's label: a stated radius, or "r" for one worked out (the answer).
    radius_label: str
    # The question states the centre (its coordinates are labelled) or an equation does.
    centre_stated: bool
    # The stated point a radius is drawn to, when the circle passes through one.
    towards: Exact | None = None


def _circle_part(request: FigureRequest, texts: Sequence[str], stated: Stated) -> _Circle | None:
    """The circle to draw, from the question's equation or its stated centre and radius,
    diameter or a point it passes through. From an equation the centre and radius are the
    answer, left unlabelled."""
    if request.equation.strip():
        found = _circle_from_equation(request.equation, texts)
        return None if found is None else _Circle(found[0], found[1], "r", False)
    centre = _centre_pair(texts)
    if centre is None:
        return None
    radius = request.first("radius")
    if radius is None and (diameter := request.first("diameter")) is not None:
        radius = diameter / 2
    if radius is not None:
        exact = Fraction(radius).limit_denominator(10_000)
        label = length_label(radius, unit_name(request.unit))
        return _Circle(centre, exact * exact, label, True)
    others = [at for _, at in stated if at != centre]
    if len(others) != 1 or not any(_THROUGH.search(text) for text in texts):
        return None
    dx, dy = others[0][0] - centre[0], others[0][1] - centre[1]
    return _Circle(centre, dx * dx + dy * dy, "r", True, others[0])


def _formulas_are_its_own(
    texts: Sequence[str], lines: list[transforms.Line], circle: tuple[Exact, Fraction] | None
) -> bool:
    """Every formula the question writes is one the picture draws: a mirror line or the
    circle. A plane beside any other would leave it out."""
    from app.modules.math.tool_check import written_expressions, written_relations

    for text in texts:
        if written_expressions(text):
            return False
        for lhs, op, rhs in written_relations(text):
            if not (lhs.free_symbols or rhs.free_symbols):
                continue
            line = transforms.line_of(lhs, rhs) if op == "=" else None
            if line is not None and any(transforms.same_line(line, other) for other in lines):
                continue
            own = _circle(lhs - rhs) if op == "=" else None
            if circle is not None and own == circle:
                continue
            return False
    return True


_Read = tuple[Stated, list[transforms.Mapping], "_Circle | None"]


def _read(request: FigureRequest, own: list[str]) -> _Read | None:
    """The stated points, the stated transformations and the circle, each the question's;
    None when any is not, or when the question writes a formula the plane leaves out."""
    stated = _stated(request, own)
    maps = transforms.mappings(request.transforms, own) if request.transforms else []
    if stated is None or maps is None:
        return None
    stated = _without(stated, [p for m in maps for p in (m.vector, m.centre) if p], own)
    circle = None
    if _circle_asked(request, own):
        circle = _circle_part(request, own, stated)
        if circle is None:
            return None
    lines = [m.mirror for m in maps if m.mirror is not None]
    held = None if circle is None else (circle.centre, circle.squared)
    if not _formulas_are_its_own(own, lines, held):
        return None
    if (maps or circle is None) and not stated:
        return None
    return stated, maps, circle


def plane_graph(request: FigureRequest, texts: list[str]) -> dict[str, object] | None:
    """The plane's ```graph spec, or None when the reading is not the question's."""
    read = _read(request, own_texts(texts))
    if read is None:
        return None
    stated, maps, circle = read
    centre_name = ""
    if circle is not None:
        centre_name = next((name for name, at in stated if at == circle.centre), "")
        stated = [(name, at) for name, at in stated if at != circle.centre]
    groups = _groups(stated)
    if maps and len(groups) != 1:
        return None  # a stated image beside one worked out: two answers to one question
    plane = Plane()
    for index, group in enumerate(groups):
        if not _draw_group(plane, request, group, image=index > 0):
            return None
    if len(groups) == 1 and len(groups[0]) == 2 and not maps:
        plane_parts.segment_parts(plane, groups[0][0][1], groups[0][1][1], request.parts)
    if circle is not None:
        letter = centre_name or request.center
        label = plane_parts.centre_label(plane, circle.centre, letter, circle.centre_stated)
        plane_parts.circle(
            plane, circle.centre, circle.squared, circle.radius_label, label, circle.towards
        )
    if maps:
        plane_parts.images(plane, groups[0], maps, _join(request, len(groups[0])))
    return plane.spec().model_dump()
