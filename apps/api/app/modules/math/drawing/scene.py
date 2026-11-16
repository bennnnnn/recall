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
from app.modules.math.drawing.lengths import (
    ROUNDED,
    dot,
    exact,
    minus,
    states_size,
    worked_length,
)
from app.modules.math.drawing.question import Question, Triple
from app.modules.math.drawing.roles import stated_on
from app.modules.math.drawing.shapes import worked_value
from app.modules.math.drawing.spheres import the_sphere
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
from app.modules.math.figure.projection import BOX_CORNERS
from app.modules.math.figure.shape_names import names_shape

MAIN = frozenset({"box", "sphere", "polygon", "plane"})
# "√34", "√ 12": a root the reply writes on a length.
_ROOT = re.compile(r"^\u221a\s*(\d+)$")
_DEGREES = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:°|\u00ba|deg|degrees?)$")
ORIGIN = "O"
_BOX_SIZE = (Fraction(3), Fraction(4), Fraction(2))
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
    # The unit of length a stated box size is written in: a worked length is shown in it.
    unit: str = ""
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
    # What a vector's name stands for in an angle: its tip, and the point it starts from.
    tips: dict[str, str] = field(default_factory=dict)
    tails: dict[str, str] = field(default_factory=dict)

    def place(self, xyz: Triple, name: str = "") -> str:
        label = name or f"_{len(self.points)}"
        self.points[label] = xyz
        return label


def _named(name: str, question: Question, at: Triple | None = None) -> bool:
    """A name shown on the picture: letters the question or the reply names, and never the
    name the question gives another triple ("A(0, 0, 3)": (2, 8, 1) is no A)."""
    lettered = all(letter in question.letters for letter in name if letter.isalpha())
    return lettered and (at is None or question.names_right(name, at))


def _its_value(letter: str, size: float, question: Question, slack: float) -> bool:
    """A letter on a length or an angle is the reply's name for it: the reply works that
    letter out to this size. Round 3's c079 labelled P to the centre "d", the reply's
    shortest distance, which is only the part outside the sphere."""
    return any(
        abs(value - size) <= slack * max(1.0, abs(size)) for value in question.value_of(letter)
    )


def _point(item: SpacePoint, scene: Scene, question: Question) -> bool:
    at = exact(item.at)
    if not question.states_triple(at) or (item.name in scene.points and item.name != ORIGIN):
        return False
    if item.name == ORIGIN and any(at):
        return False
    scene.place(at, item.name)
    scene.dots.add(item.name)
    if _named(item.name, question, at):
        scene.shown.add(item.name)
    if item.guides and any(at):
        scene.guides.append(item.name)
    return True


def _box(item: SpaceBox, scene: Scene, question: Question) -> bool:
    if not names_shape([question.words], "box"):
        return False
    labels: dict[tuple[int, int], str] = {}
    size = _BOX_SIZE
    if item.size is not None:
        size = exact(item.size)
        units = [states_size(question, value) for value in size]
        if any(unit is None or value <= 0 for unit, value in zip(units, size, strict=True)):
            return False
        # Along x and y its length and width, either way round; up z its height.
        roles = ({"length", "width"}, {"length", "width"}, {"height"})
        every = ("length", "width", "height")
        if not all(
            stated_on(r, float(v), every, question) for r, v in zip(roles, size, strict=True)
        ):
            return False
        for edge, value, unit in zip(_SIZE_EDGES, size, units, strict=True):
            labels[edge] = length_label(float(value), unit or "")
            scene.unit = scene.unit or unit or ""
    names = [""] * 8
    for name, written in item.corners.items():
        place = _corner_of(exact(written), size)
        if place is None or names[place]:
            return False  # a letter on no corner, or two on one: the lettering is not the box's
        names[place] = name
    corners: list[str] = []
    for (i, j, k), name in zip(BOX_CORNERS, names, strict=True):
        corner = (size[0] * i, size[1] * j, size[2] * k)
        # A letter the question puts elsewhere, or writes without saying where, is no
        # corner's: round 2's review drew "G(5, 4, 3)" at (5, 0, 3), OG a face diagonal.
        if (
            name
            and not (name == ORIGIN and not any(corner))
            and not question.confirms(name, corner)
        ):
            name = ""
        # A corner the scene already holds there (the origin O) is that point.
        if name and name in scene.points and scene.points[name] != corner:
            return False
        corners.append(scene.place(corner, name))
        if name and _named(name, question, corner):
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
    return BOX_CORNERS.index((flags[0], flags[1], flags[2]))


def _sphere(item: SpaceSphere, scene: Scene, question: Question) -> bool:
    if not names_shape([question.words], "sphere"):
        return False
    found = the_sphere(item, question)
    if found is None:
        return False
    centre, radius_squared, label = found
    if any(centre):
        name = item.name if item.name and item.name not in scene.points else ""
        if name and _named(name, question, centre):
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
        components = exact(item.end)
        base = scene.points[start]
        # From a point the origin is not, only a vector the question writes as one: from A
        # to "B(4, 5, 6)" is no arrow of (4, 5, 6) (round 2's review drew A to A + B).
        held = question.vectors if any(base) else question.triples
        if components not in held:
            return False
        tip = scene.place(
            (base[0] + components[0], base[1] + components[1], base[2] + components[2])
        )
    if start == tip:
        return False
    way = minus(scene.points[tip], scene.points[start])
    scene.arrows.append((start, tip, item.name if _named(item.name, question, way) else None))
    scene.tips[item.name] = tip
    scene.tails[item.name] = start
    return True


def _segment_label(text: str, squared: Fraction, scene: Scene, question: Question) -> str | None:
    """A segment's label as the server shows it: a stated value or the model's own number
    only where it is the segment's length (as the server works it out, √34 or 5.83), a
    letter only where the reply works that letter out to it ("d = √109")."""
    shown, length = worked_length(squared)
    unit = f" {scene.unit}" if scene.unit else ""
    root = _ROOT.match(text.strip())
    if root is not None:
        claimed: float | None = math.sqrt(float(root.group(1)))
        label = None
    else:
        label = read_length(text, question)
        if label is None:
            return None
        claimed = label.value if label.value is not None else label.claimed
    if claimed is not None:
        held = abs(length - claimed) <= ROUNDED * max(1.0, length)
        return f"{shown}{unit}" if held else None
    if label is None or label.letter is None or label.coefficient != 1:
        return None
    if not _its_value(label.letter, length, question, ROUNDED):
        return None
    return f"{label.letter} = {shown}{unit}"


def _segment(item: SpaceSegment, scene: Scene, question: Question) -> bool:
    if item.start not in scene.points or item.end not in scene.points or item.start == item.end:
        return False
    gap = minus(scene.points[item.end], scene.points[item.start])
    text = _segment_label(item.label, dot(gap, gap), scene, question) if item.label else None
    scene.segments.append((item.start, item.end, text))
    return True


def _polygon(item: SpacePolygon | SpacePlane, scene: Scene) -> bool:
    names = item.vertices if isinstance(item, SpacePolygon) else item.through
    if len(set(names)) != len(names) or not all(name in scene.points for name in names):
        return False
    a, b, c = (scene.points[name] for name in names[:3])
    u, v = minus(b, a), minus(c, a)
    normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    if not any(normal):
        return False  # three points on one line make no polygon and fix no plane
    corners = list(names)
    if isinstance(item, SpacePlane):
        # The patch of the plane with A, B and C at three of its corners.
        corners.append(scene.place((a[0] + c[0] - b[0], a[1] + c[1] - b[1], a[2] + c[2] - b[2])))
    elif any(dot(normal, minus(scene.points[name], a)) for name in names[3:]):
        return False  # its corners are not in one plane
    scene.faces.append(corners)
    return True


def _drawn(scene: Scene, a: str, b: str) -> bool:
    """A line from ``a`` to ``b`` is on the picture: an arrow, a segment, a face's side or a
    box's edge or diagonal."""
    lines = {(s, t) for s, t, _ in [*scene.arrows, *scene.segments]}
    lines |= {
        (face[i], face[(i + 1) % len(face)]) for face in scene.faces for i in range(len(face))
    }
    for box in scene.boxes:
        lines |= {(box.corners[i], box.corners[j]) for i, j in box.diagonals}
        lines |= {
            (box.corners[i], box.corners[j])
            for i in range(8)
            for j in range(8)
            if sum(x != y for x, y in zip(BOX_CORNERS[i], BOX_CORNERS[j], strict=True)) == 1
        }
    return (a, b) in lines or (b, a) in lines


def _angle(item: SpaceAngle, scene: Scene, question: Question) -> bool:
    ends = [scene.tips.get(name, name) for name in item.between]
    if item.at not in scene.points or not all(end in scene.points for end in ends):
        return False
    # Both arms start at the angle's vertex, and are drawn: an angle at O to an arrow drawn
    # from P is not the angle between them (round 2's review).
    for name, end in zip(item.between, ends, strict=True):
        tail = scene.tails.get(name)
        if (tail is not None and tail != item.at) or (
            tail is None and not _drawn(scene, item.at, end)
        ):
            return False
    u, v = (minus(scene.points[end], scene.points[item.at]) for end in ends)
    if not any(u) or not any(v) or ends[0] == ends[1]:
        return False
    cosine = float(dot(u, v)) / math.sqrt(float(dot(u, u)) * float(dot(v, v)))
    size = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
    right = dot(u, v) == 0
    label = None if right else _angle_label(item.label, size, question)
    scene.angles.append((item.at, ends[0], ends[1], label, right))
    return True


def _angle_label(text: str, size: float, question: Question) -> str | None:
    """An angle's label as the server shows it, its size worked out from the stated points:
    a number only where it is that size, a letter only where the reply works it out to it
    ("θ ≈ 70.53°")."""
    text = " ".join(text.split())
    if not text:
        return None
    shown, exact = worked_value(size)
    number = _DEGREES.match(text)
    if number is not None:
        return f"{shown}°" if abs(float(number.group(1)) - size) <= 0.05 else None
    letter = read_angle(text, question, size)
    if letter is None or letter[0].isdigit():
        return None
    # The mark names the angle it is drawn at, and the server gives its size: the letter
    # stands unless the reply works it out to another size.
    if question.value_of(letter) and not _its_value(letter, size, question, ROUNDED):
        return None
    return f"{letter} {'=' if exact else '≈'} {shown}°"


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
    # Something beside the axes: a point the origin is not, or a solid, an arrow or a face.
    placed = any(any(at) for at in scene.points.values())
    drawn = scene.arrows or scene.boxes or scene.spheres or scene.faces or placed
    return scene if drawn else None
