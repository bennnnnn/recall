"""The circle theorems about angles, each drawn true to the angles the question states.

- The angle at the centre is twice the angle at the circumference on the same arc: the
  arc's ends, the centre and one or two points on the circle (angles in the same segment),
  each angle marked, the stated ones labelled. An angle at the circumference of 90° or more
  stands on a reflex angle at the centre, which no mark can show: its centre is left
  unmarked.
- The angle in a semicircle is a right angle: the diameter's ends and a point on the circle,
  the right angle boxed, the triangle drawn from the sides or angles the question states.
- Opposite angles of a cyclic quadrilateral add to 180°: its four corners on the circle,
  each corner's angle true, the stated ones labelled and the asked ones marked.

Values that cannot hold together (an angle at the centre that is not twice the one at the
circumference, opposite angles that do not add to 180°) draw nothing.
"""

from __future__ import annotations

import math

from app.modules.math.figure.circle_frame import (
    DEFAULT_RADIUS,
    close,
    corner_of,
    letter,
    letters,
    right_triangle,
    start,
    stated_size,
)
from app.modules.math.figure.drawing import angle_label, polar
from app.modules.math.figure.request import FigureRequest, Measure
from app.modules.math.schemas.figure import FigureSpec

_SIZES = frozenset({"radius", "diameter"})
# A length named by two letters, or a part a triangle on a diameter is measured by.
_LENGTHS = frozenset({"side", "length", "chord", "leg", "hypotenuse", "base", "width"})
# A cyclic quadrilateral's free pair of opposite angles, when the question states neither.
_FREE_ANGLE = 100.0


def build_angle_at_centre(request: FigureRequest) -> FigureSpec | None:
    """The arc's ends A and B, the centre and the points on the circle the arc's angles
    stand at, every angle on the arc true."""
    holds, size = stated_size(request)
    request = _with_centre(request)
    centre_letter = letter(request.center)
    central: list[Measure] = []
    inscribed: list[Measure] = []
    for m in request.measures:
        vertex = corner_of(m.name.strip())
        if m.what in _SIZES:
            continue
        if m.what == "central_angle" or (m.what == "angle" and vertex and vertex == centre_letter):
            central.append(m)
        elif m.what == "inscribed_angle" or (m.what == "angle" and vertex):
            inscribed.append(m)
        else:
            return None
    if not holds or len(central) > 1 or len({m.value for m in inscribed}) > 1:
        return None
    stated = central[0].value if central else None
    at_circle = inscribed[0].value if inscribed else None
    theta = stated or (2 * at_circle if at_circle else 100.0)
    if (stated is not None and stated > 180) or theta >= 360:
        return None
    if stated is not None and at_circle is not None and not close(stated, 2 * at_circle):
        return None
    ends, apexes = _arc_letters(request, central, inscribed)
    r = size or DEFAULT_RADIUS
    figure = start(request, "circle_angle_at_centre", r)
    drawing = figure.drawing
    a = figure.named(polar(r, -90 - theta / 2), ends[0])
    b = figure.named(polar(r, -90 + theta / 2), ends[1])
    drawing.arc(figure.centre, r)
    drawing.line(figure.centre, a, figure.length(request.first("radius")))
    drawing.line(figure.centre, b)
    spread = 180 - theta / 2
    # One point a little off the top, so neither of its chords runs close by the centre.
    turns = [90 + 0.15 * spread] if len(apexes) < 2 else [90 + 0.5 * spread, 90 - 0.5 * spread]
    for turn, apex in zip(turns, apexes or [""], strict=False):
        point = figure.named(polar(r, turn), apex)
        drawing.line(point, a)
        drawing.line(point, b)
        drawing.angle(point, a, b, angle_label(at_circle) if at_circle is not None else None)
        # One stated angle at the circumference is labelled once: the others are its equals.
        at_circle = None if len(inscribed) < 2 else at_circle
    if stated is not None or theta < 180:
        drawing.angle(figure.centre, a, b, angle_label(stated) if stated is not None else None)
    figure.diameter(request.first("diameter"), 0.0)
    return drawing.spec()


def _with_centre(request: FigureRequest) -> FigureRequest:
    """A centre the question letters only in its angle's name ("angle AOB")."""
    if letter(request.center):
        return request
    for m in request.given("central_angle"):
        if len(m.name.strip()) == 3:
            return request.model_copy(update={"center": m.name.strip()[1]})
    return request


def _arc_letters(
    request: FigureRequest, central: list[Measure], inscribed: list[Measure]
) -> tuple[list[str], list[str]]:
    """The arc's ends and the points on the circle, as the angles' names letter them
    ("AOB", "ACB"), else as the question's letters run (the ends, then the points)."""
    ends: list[str] = []
    apexes: list[str] = []
    for m in [*central, *inscribed]:
        name = m.name.strip()
        if len(name) == 3 and not ends:
            ends = [name[0], name[2]]
        if m in inscribed and corner_of(name) and corner_of(name) not in apexes:
            apexes.append(corner_of(name))
    named = [c for c in request.vertices.strip() if c.isalpha()]
    if not ends and not apexes and len(named) >= 3:
        return named[:2], named[2:4]
    centre = letter(request.center)
    rest = [c for c in named if c not in {*ends, *apexes, centre}]
    apexes += rest[: max(0, 2 - len(apexes))] if ends else []
    return (ends or ["", ""]), apexes[:2]


def build_angle_in_semicircle(request: FigureRequest) -> FigureSpec | None:
    """The diameter AB, C on the circle and the right angle at C, the triangle ABC drawn
    from its stated sides or angles."""
    holds, size = stated_size(request)
    # Unlettered, the points are kept apart by marks no letter is ("1", "2", "3").
    a, b, c = _semicircle_letters(request) or ("1", "2", "3")
    sides: dict[frozenset[str], float] = {}
    unnamed: list[float] = []
    at_a = at_b = None
    for m in request.measures:
        name = m.name.strip()
        if m.what in _SIZES:
            continue
        if m.what in {"angle", "inscribed_angle"}:
            vertex = corner_of(name)
            if vertex == c and close(m.value, 90):
                continue
            if vertex in {a, ""} and at_a is None:
                at_a = m.value
            elif vertex == b:
                at_b = m.value
            else:
                return None
        elif m.what in _LENGTHS and len(name) == 2 and set(name) <= {a, b, c}:
            sides[frozenset(name)] = m.value
        elif m.what in _LENGTHS and not name:
            unnamed.append(m.value)
        else:
            return None
    if unnamed:
        if sides or len(unnamed) > 2:
            return None
        sides = dict(zip((frozenset((a, c)), frozenset((b, c))), unnamed, strict=False))
    diameter = size * 2 if size is not None else None
    ab = sides.get(frozenset((a, b)))
    if not holds or (ab is not None and diameter is not None and not close(ab, diameter)):
        return None
    ac, bc = sides.get(frozenset((a, c))), sides.get(frozenset((b, c)))
    if at_a is not None and at_b is not None and not close(at_a + at_b, 90):
        return None
    hyp = ab if ab is not None else diameter
    if at_a is None and at_b is not None:
        solved = right_triangle(ac, bc, hyp, at_b)
    else:
        solved = right_triangle(bc, ac, hyp, at_a)
        solved = None if solved is None else (solved[1], solved[0], solved[2])
    if solved is None:
        return None
    side_ac, _, side_ab = solved
    return _semicircle_figure(request, (a, b, c), side_ac, side_ab, (at_a, at_b), sides)


def _semicircle_figure(
    request: FigureRequest,
    names: tuple[str, str, str],
    side_ac: float,
    side_ab: float,
    angles: tuple[float | None, float | None],
    sides: dict[frozenset[str], float],
) -> FigureSpec:
    r = side_ab / 2
    figure = start(request, "circle_semicircle_angle", r)
    drawing = figure.drawing
    turn = math.acos(min(1.0, side_ac / side_ab))
    a = figure.named((-r, 0.0), names[0])
    b = figure.named((r, 0.0), names[1])
    c = figure.named((-r + side_ac * math.cos(turn), side_ac * math.sin(turn)), names[2])
    drawing.arc(figure.centre, r)
    stated_ab = sides.get(frozenset(names[:2])) or request.first("diameter")
    drawing.line(a, b, figure.length(stated_ab), label_at=0.75)
    drawing.line(a, c, figure.length(sides.get(frozenset((names[0], names[2])))))
    drawing.line(b, c, figure.length(sides.get(frozenset((names[1], names[2])))))
    drawing.angle(c, a, b, right=True)
    if request.first("radius") is not None:
        drawing.line(figure.centre, c, figure.length(request.first("radius")))
    for at, other, value in ((a, b, angles[0]), (b, a, angles[1])):
        if value is not None:
            drawing.angle(at, other, c, angle_label(value))
    return drawing.spec()


def _semicircle_letters(request: FigureRequest) -> tuple[str, str, str] | None:
    """The diameter's ends and the point on the circle: as the diameter's name gives them
    ("AB"), else as the question's letters run."""
    named = letters(request, 3)
    for m in request.measures:
        name = m.name.strip()
        if m.what in {"diameter", "hypotenuse"} and len(name) == 2 and named:
            if set(name) <= set(named):
                rest = next(x for x in named if x not in name)
                return name[0], name[1], rest
    return (named[0], named[1], named[2]) if named else None


def build_cyclic_quadrilateral(request: FigureRequest) -> FigureSpec | None:
    """ABCD with its corners on the circle, every corner's angle true: each is half the arc
    it stands on, so the four arcs are worked out from the stated angles."""
    holds, size = stated_size(request)
    names = letters(request, 4)
    corner: dict[int, float] = {}
    for m in request.measures:
        if m.what in _SIZES:
            continue
        index = _corner(m, names) if m.what in {"angle", "inscribed_angle"} else None
        if index is None or index in corner or not 0 < m.value < 180:
            return None
        corner[index] = m.value
    if not holds:
        return None
    for i, j in ((0, 2), (1, 3)):
        if i in corner and j in corner:
            if not close(corner[i] + corner[j], 180):
                return None
        elif j in corner:
            corner[i] = 180 - corner[j]
        else:
            corner.setdefault(i, _FREE_ANGLE)
            corner[j] = 180 - corner[i]
    arcs = _arcs(corner[0], corner[1])
    r = size or DEFAULT_RADIUS
    figure = start(request, "cyclic_quadrilateral", r)
    turn = 225.0
    corners = []
    for i in range(4):
        corners.append(figure.named(polar(r, turn), names[i] if names else ""))
        turn += arcs[i]
    figure.drawing.arc(figure.centre, r)
    figure.drawing.outline(corners)
    stated = {i for i in range(4) if _stated(request, names, i)}
    for i, name in enumerate(corners):
        label = angle_label(corner[i]) if i in stated else None
        figure.drawing.angle(name, corners[i - 1], corners[(i + 1) % 4], label)
    radius = request.first("radius")
    if radius is not None:
        top = figure.drawing.point(polar(r, 90))
        figure.drawing.line(figure.centre, top, figure.length(radius))
    figure.diameter(request.first("diameter"), 90.0)
    return figure.drawing.spec()


def _corner(m: Measure, names: list[str]) -> int | None:
    """Which corner an angle is at: by its letter, or the first corner when it has none."""
    name = m.name.strip()
    if not name:
        return 0
    if not names or corner_of(name) not in names:
        return None
    index = names.index(corner_of(name))
    if len(name) == 3 and {name[0], name[2]} != {names[index - 1], names[(index + 1) % 4]}:
        return None
    return index


def _stated(request: FigureRequest, names: list[str], index: int) -> bool:
    return any(
        m.what in {"angle", "inscribed_angle"} and _corner(m, names) == index
        for m in request.measures
    )


def _arcs(first: float, second: float) -> list[float]:
    """The arcs between consecutive corners (A to B, B to C, C to D, D to A) when the
    angles at A and B are ``first`` and ``second``: the angle at A stands on the arcs B to C
    and C to D, at B on C to D and D to A. One arc is free; it is chosen so the smallest
    arc is as large as it can be."""
    low, high = max(0.0, 2 * first + 2 * second - 360), min(2 * first, 2 * second)
    best: list[float] = []
    for step in range(1, 50):
        free = low + (high - low) * step / 50
        arcs = [360 - 2 * first - 2 * second + free, 2 * first - free, free, 2 * second - free]
        if not best or min(arcs) > min(best):
            best = arcs
    return best
