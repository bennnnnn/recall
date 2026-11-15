"""A scene in space, checked item by item against the question.

Every point is one the question places, its foot on an axis or a coordinate plane, or the
origin; a vector's components are ones the question writes, or the difference of two of its
points; a box's size and a sphere's centre and radius are values it states, or the sphere is
the one its equation writes (SymPy completes the square). A label is a stated value true
where it sits (a segment's length), or a letter the question or the reply names. An item
that fails is left out, with whatever rests on it; when the scene's main object (its first
box, sphere, polygon or plane) fails, nothing is drawn. Coordinates stay exact here: a
right angle is marked only where the dot product is 0.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from app.modules.math.drawing.labels import read_angle, read_length
from app.modules.math.drawing.question import Question, Triple
from app.modules.math.drawing.vocabulary import (
    Axes,
    SpaceAngle,
    SpaceBox,
    SpacePlane,
    SpacePoint,
    SpacePolygon,
    SpaceSegment,
    SpaceSphere,
    SpaceVector,
)
from app.modules.math.figure.drawing import length_label
from app.modules.math.figure.shape_names import names_shape

MAIN = frozenset({"box", "sphere", "polygon", "plane"})
_PART_LABEL = re.compile(r"\(\s*[a-z]\s*\)|(?<![\w)])[a-z]\)")
ORIGIN = "O"
_BOX_SIZE = (Fraction(3), Fraction(4), Fraction(2))
# A box's corners: the bottom four from the origin round, then the top four above them.
_CORNERS = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
BOX_FACES = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [3, 2, 6, 7], [0, 3, 7, 4], [1, 2, 6, 5]]
# The edges a box's length, width and height are labelled on.
_SIZE_EDGES = ((0, 1), (1, 2), (0, 4))


@dataclass
class Box:
    corners: list[str]
    labels: dict[tuple[int, int], str]
    # Diagonals by their corners' places in ``corners``.
    diagonals: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class Sphere:
    centre: str
    radius_squared: Fraction
    label: str | None


@dataclass
class Scene:
    """What a checked scene draws, in exact coordinates."""

    points: dict[str, Triple] = field(default_factory=lambda: {ORIGIN: (Fraction(0),) * 3})
    shown: set[str] = field(default_factory=set)
    # The points drawn as dots: the question's own, and a sphere's centre.
    dots: set[str] = field(default_factory=set)
    guides: list[str] = field(default_factory=list)
    # (start, tip, label): an arrow from one named point to another.
    arrows: list[tuple[str, str, str | None]] = field(default_factory=list)
    segments: list[tuple[str, str, str | None]] = field(default_factory=list)
    faces: list[list[str]] = field(default_factory=list)
    boxes: list[Box] = field(default_factory=list)
    spheres: list[Sphere] = field(default_factory=list)
    # (at, a, b, label, right)
    angles: list[tuple[str, str, str, str | None, bool]] = field(default_factory=list)
    axes: bool = False
    # What a vector's name stands for in an angle: its tip.
    tips: dict[str, str] = field(default_factory=dict)

    def place(self, xyz: Triple, name: str = "") -> str:
        label = name or f"_{len(self.points)}"
        self.points[label] = xyz
        return label


def _exact(values: tuple[float, ...]) -> Triple:
    x, y, z = (Fraction(value).limit_denominator(10_000) for value in values)
    return (x, y, z)


def _minus(a: Triple, b: Triple) -> Triple:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Triple, b: Triple) -> Fraction:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _named(name: str, question: Question) -> bool:
    return all(letter in question.letters for letter in name if letter.isalpha())


def _point(item: SpacePoint, scene: Scene, question: Question) -> bool:
    at = _exact(item.at)
    if not question.states_triple(at) or (item.name in scene.points and item.name != ORIGIN):
        return False
    if item.name == ORIGIN and any(at):
        return False
    scene.place(at, item.name)
    scene.dots.add(item.name)
    if _named(item.name, question):
        scene.shown.add(item.name)
    if item.guides and any(at):
        scene.guides.append(item.name)
    return True


def _states_size(question: Question, value: Fraction) -> str | None:
    """The unit a stated length is written with ("" for none), or None when it is unstated
    (a rate, a size at one moment of a changing shape)."""
    if value in question.changing:
        return None
    for written in question.numbers:
        if written.in_formula or written.unit in {"deg", "area", "other"}:
            continue
        if written.value == value:
            return written.unit
    return None


def _box(item: SpaceBox, scene: Scene, question: Question) -> bool:
    if not names_shape([question.words], "box"):
        return False
    labels: dict[tuple[int, int], str] = {}
    size = _BOX_SIZE
    if item.size is not None:
        size = _exact(item.size)
        units = [_states_size(question, value) for value in size]
        if any(unit is None or value <= 0 for unit, value in zip(units, size, strict=True)):
            return False
        for edge, value, unit in zip(_SIZE_EDGES, size, units, strict=True):
            labels[edge] = length_label(float(value), unit or "")
    names = [""] * 8
    for name, written in item.corners.items():
        place = _corner_of(_exact(written), size)
        if place is None or names[place]:
            return False  # a letter on no corner, or two on one: the lettering is not the box's
        names[place] = name
    corners: list[str] = []
    for (i, j, k), name in zip(_CORNERS, names, strict=True):
        corner = (size[0] * i, size[1] * j, size[2] * k)
        # A corner the scene already holds there (the origin O) is that point.
        if name and name in scene.points and scene.points[name] != corner:
            return False
        corners.append(scene.place(corner, name))
        if name and _named(name, question):
            scene.shown.add(name)
    box = Box(corners, labels)
    for diagonal in item.diagonals:
        if all(letter in corners for letter in diagonal) and diagonal[0] != diagonal[1]:
            box.diagonals.append((corners.index(diagonal[0]), corners.index(diagonal[1])))
    scene.boxes.append(box)
    return True


def _corner_of(at: Triple, size: Triple) -> int | None:
    """Which of the box's corners ``at`` is (each coordinate 0 or the box's size)."""
    flags = []
    for value, extent in zip(at, size, strict=True):
        if value not in {0, extent}:
            return None
        flags.append(int(value == extent and extent != 0))
    return _CORNERS.index((flags[0], flags[1], flags[2]))


def _written_spheres(question: Question) -> list[tuple[Any, Triple, Fraction]]:
    """Each sphere the question writes an equation of: the equation (its sides' difference),
    its centre and its squared radius (SymPy completes the square). An equation of no real
    sphere (a radius squared of 0 or less) is none."""
    import sympy

    from app.modules.math.tool_check import written_relations

    # "(a) x² + y² + z² - 2y = 4 (b) ...": each part's equation on its own, its letter left out.
    texts = [_PART_LABEL.sub(";\n", text) for text in question.texts]
    x, y, z = sympy.symbols("x y z")
    found: list[tuple[Any, Triple, Fraction]] = []
    for text in texts:
        for lhs, op, rhs in written_relations(text):
            expr = sympy.expand(lhs - rhs)
            if op != "=" or not expr.free_symbols <= {x, y, z}:
                continue
            poly = sympy.Poly(expr, x, y, z)
            if poly.total_degree() != 2 or not all(c.is_Rational for c in poly.coeffs()):
                continue
            square = poly.coeff_monomial(x**2)
            cross = [poly.coeff_monomial(m) for m in (x * y, x * z, y * z)]
            if (
                square == 0
                or any(cross)
                or {poly.coeff_monomial(y**2), poly.coeff_monomial(z**2)} != {square}
            ):
                continue
            a = Fraction(str(square))
            linear = [Fraction(str(poly.coeff_monomial(v))) / a for v in (x, y, z)]
            centre = (-linear[0] / 2, -linear[1] / 2, -linear[2] / 2)
            radius_squared = sum(c * c for c in centre) - Fraction(str(poly.coeff_monomial(1))) / a
            if radius_squared > 0:
                found.append((expr, centre, radius_squared))
    return found


def _sphere_of(item: SpaceSphere, question: Question) -> tuple[Triple, Fraction] | None:
    """The question's own sphere the item is: the one whose equation it copies, or whose
    centre (and radius, when it gives one) it worked out from that equation."""
    import sympy

    from app.modules.math.tool_check import parse_formula, same_value

    spheres = _written_spheres(question)
    if item.equation.strip():
        sides = item.equation.split("=")
        parsed = [parse_formula(side) for side in sides] if len(sides) == 2 else []
        if len(parsed) != 2 or parsed[0] is None or parsed[1] is None:
            return None
        mine = sympy.expand(parsed[0] - parsed[1])
        matches = [s for s in spheres if same_value(mine, s[0]) or same_value(mine, -s[0])]
    elif item.center is not None:
        centre = _exact(item.center)
        radius = item.radius if isinstance(item.radius, int | float) else None
        matches = [
            s
            for s in spheres
            if s[1] == centre and (radius is None or abs(float(s[2]) - radius**2) < 1e-6)
        ]
    else:
        return None
    return (matches[0][1], matches[0][2]) if len(matches) == 1 else None


def _sphere(item: SpaceSphere, scene: Scene, question: Question) -> bool:
    if not names_shape([question.words], "sphere"):
        return False
    label: str | None = None
    given = item.radius if isinstance(item.radius, int | float) and item.radius > 0 else None
    radius = Fraction(given).limit_denominator(10_000) if given is not None else None
    unit = _states_size(question, radius) if radius is not None else None
    centre = _exact(item.center) if item.center is not None else None
    if centre is not None and radius is not None and unit is not None:
        held = question.states_triple(centre)
    else:
        held = False
    if held and centre is not None and radius is not None and unit is not None:
        radius_squared = radius * radius
        label = length_label(float(radius), unit)
    else:
        # Not stated: the question's own sphere, its centre and radius worked from its equation.
        found = _sphere_of(item, question)
        if found is None:
            return False
        centre, radius_squared = found
    if any(centre):
        name = item.name if item.name and item.name not in scene.points else ""
        if name and _named(name, question):
            scene.shown.add(name)
        name = scene.place(centre, name)
    else:
        name = ORIGIN
    scene.dots.add(name)
    scene.spheres.append(Sphere(name, radius_squared, label))
    return True


def _vector(item: SpaceVector, scene: Scene, question: Question) -> bool:
    start = item.start or ORIGIN
    if start not in scene.points:
        return False
    if isinstance(item.end, str):
        if item.end not in scene.points:
            return False
        tip = item.end
    else:
        components = _exact(item.end)
        if components not in question.triples:
            return False
        base = scene.points[start]
        tip = scene.place(
            (base[0] + components[0], base[1] + components[1], base[2] + components[2])
        )
    if start == tip:
        return False
    scene.arrows.append((start, tip, item.name if _named(item.name, question) else None))
    scene.tips[item.name] = tip
    return True


def _segment(item: SpaceSegment, scene: Scene, question: Question) -> bool:
    if item.start not in scene.points or item.end not in scene.points or item.start == item.end:
        return False
    label = read_length(item.label, question) if item.label else None
    text = label.text if label is not None else None
    if label is not None and label.value is not None:
        gap = _minus(scene.points[item.end], scene.points[item.start])
        if abs(float(_dot(gap, gap)) - label.value**2) > 1e-6 * max(1.0, label.value**2):
            text = None  # a stated value that is not this segment's length
    elif label is not None and label.coefficient != 1:
        text = None
    scene.segments.append((item.start, item.end, text))
    return True


def _polygon(item: SpacePolygon | SpacePlane, scene: Scene) -> bool:
    names = item.vertices if isinstance(item, SpacePolygon) else item.through
    if len(set(names)) != len(names) or not all(name in scene.points for name in names):
        return False
    a, b, c = (scene.points[name] for name in names[:3])
    u, v = _minus(b, a), _minus(c, a)
    normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    if not any(normal):
        return False  # three points on one line make no polygon and fix no plane
    corners = list(names)
    if isinstance(item, SpacePlane):
        # The patch of the plane with A, B and C at three of its corners.
        corners.append(scene.place((a[0] + c[0] - b[0], a[1] + c[1] - b[1], a[2] + c[2] - b[2])))
    elif any(_dot(normal, _minus(scene.points[name], a)) for name in names[3:]):
        return False  # its corners are not in one plane
    scene.faces.append(corners)
    return True


def _angle(item: SpaceAngle, scene: Scene, question: Question) -> bool:
    ends = [scene.tips.get(name, name) for name in item.between]
    if item.at not in scene.points or not all(end in scene.points for end in ends):
        return False
    u, v = (_minus(scene.points[end], scene.points[item.at]) for end in ends)
    if not any(u) or not any(v) or ends[0] == ends[1]:
        return False
    cosine = float(_dot(u, v)) / math.sqrt(float(_dot(u, u)) * float(_dot(v, v)))
    size = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
    right = _dot(u, v) == 0
    label = None if right else read_angle(item.label, question, size)
    scene.angles.append((item.at, ends[0], ends[1], label, right))
    return True


def _add(item: Any, scene: Scene, question: Question) -> bool:
    if isinstance(item, Axes):
        scene.axes = True
        return True
    if isinstance(item, SpacePoint):
        return _point(item, scene, question)
    if isinstance(item, SpaceBox):
        return _box(item, scene, question)
    if isinstance(item, SpaceSphere):
        return _sphere(item, scene, question)
    if isinstance(item, SpaceVector):
        return _vector(item, scene, question)
    if isinstance(item, SpaceSegment):
        return _segment(item, scene, question)
    if isinstance(item, SpacePolygon | SpacePlane):
        return _polygon(item, scene)
    if isinstance(item, SpaceAngle):
        return _angle(item, scene, question)
    return False


# The order items are placed in: the points and solids first, then what rests on them.
_ORDER = {"point": 0, "box": 0, "sphere": 0, "vector": 1, "segment": 2, "polygon": 2, "plane": 2}


def checked_scene(items: list[tuple[str, Any | None]], question: Question) -> Scene | None:
    """The scene the items describe, each one checked; None when its main object fails or
    nothing but its axes is left."""
    scene = Scene()
    main = next((index for index, (name, _) in enumerate(items) if name in MAIN), None)
    ordered = sorted(enumerate(items), key=lambda pair: _ORDER.get(pair[1][0], 3))
    for index, (_name, item) in ordered:
        held = item is not None and _add(item, scene, question)
        if index == main and not held:
            return None
    drawn = scene.arrows or scene.boxes or scene.spheres or scene.faces or len(scene.points) > 1
    return scene if drawn else None
