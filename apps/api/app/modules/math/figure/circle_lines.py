"""Lines that meet a circle, each drawn true to the values the question states.

- A tangent from a point P outside the circle meets the radius at a right angle where it
  touches (T): the radius, the tangent and OP make a right triangle, so any two of them (or
  one and an angle) draw the rest; what the question asks is drawn, unlabelled.
- Two tangents from one point are equal: both drawn with matching marks, the right angles
  where they touch boxed, OP dashed between them as the line of symmetry.
- Two chords crossing inside the circle at E cut each other so that AE·EB = CE·ED: the parts
  the question states are labelled, the one it asks for is worked out from them and drawn
  unlabelled, and the circle is the one through the chords' four ends.

Values that cannot hold together (a point inside the circle, a tangent longer than OP,
chord parts whose products differ) draw nothing.
"""

from __future__ import annotations

import math

from app.modules.math.figure.circle_frame import (
    CircleFigure,
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
_PARTS = frozenset({"length", "side", "chord", "segment"})
# The angle the two chords cross at, when the question states none.
_CROSSING = 65.0


def _point_letter(request: FigureRequest, centre: str) -> str:
    """The outside point: as the read letters it, or the letter OP names besides O."""
    found = letter(request.point)
    if found:
        return found
    for m in request.given("distance"):
        rest = [c for c in m.name.strip() if c != centre and c.isalpha()]
        if len(m.name.strip()) == 2 and len(rest) == 1:
            return rest[0]
    return ""


def _tangent_values(
    request: FigureRequest, centre: str, point: str, *, two: bool
) -> tuple[float, float, float] | None:
    """(radius, tangent, distance OP) from what is stated; ``two``: the angle at P is the
    angle between the two tangents, and the angle at O the one between the radii."""
    holds, size = stated_size(request)
    at_point = at_centre = None
    for m in request.measures:
        name = m.name.strip()
        if m.what in _SIZES | {"distance", "tangent"}:
            continue
        if m.what not in {"angle", "central_angle"}:
            return None
        vertex = corner_of(name)
        half = two and not (len(name) == 3 and {centre, point} & {name[0], name[2]})
        if m.what == "central_angle" or (vertex and vertex == centre):
            at_centre = m.value / 2 if half else m.value
        elif not vertex or vertex == point:
            at_point = m.value / 2 if half else m.value
        else:
            return None
    if not holds:
        return None
    if at_point is not None and at_centre is not None and not close(at_point + at_centre, 90):
        return None
    if at_point is None and at_centre is not None:
        at_point = 90 - at_centre
    return right_triangle(size, request.first("tangent"), request.first("distance"), at_point)


def build_tangent(request: FigureRequest) -> FigureSpec | None:
    """The circle, the point P outside it, the tangent PT and the radius OT at right angles,
    and OP."""
    centre = letter(request.center)
    point = _point_letter(request, centre)
    found = _tangent_values(request, centre, point, two=False)
    if found is None:
        return None
    r, _, reach = found
    figure = start(request, "circle_tangent", r)
    drawing = figure.drawing
    turn = math.degrees(math.acos(r / reach))
    contact = (letters(request, 1) or _contacts(request, point, 1))[0]
    p = figure.named((reach, 0.0), point)
    t = figure.named(polar(r, turn), contact)
    drawing.arc(figure.centre, r)
    drawing.line(figure.centre, t, figure.length(request.first("radius")))
    drawing.line(t, p, figure.length(request.first("tangent")))
    drawing.line(figure.centre, p, figure.length(request.first("distance")))
    drawing.angle(t, figure.centre, p, right=True)
    _angles(figure, request, p, (figure.centre, t), (t, p))
    figure.diameter(request.first("diameter"), 180.0)
    return drawing.spec()


def build_two_tangents(request: FigureRequest) -> FigureSpec | None:
    """Two tangents from P touching at A and B: equal, at right angles to the radii OA and
    OB, with OP between them."""
    centre = letter(request.center)
    point = _point_letter(request, centre)
    found = _tangent_values(request, centre, point, two=True)
    if found is None:
        return None
    r, _, reach = found
    figure = start(request, "circle_two_tangents", r)
    drawing = figure.drawing
    turn = math.degrees(math.acos(r / reach))
    names = letters(request, 2) or _contacts(request, point, 2)
    p = figure.named((reach, 0.0), point)
    a = figure.named(polar(r, turn), names[0])
    b = figure.named(polar(r, -turn), names[1])
    drawing.arc(figure.centre, r)
    drawing.line(figure.centre, a, figure.length(request.first("radius")))
    drawing.line(figure.centre, b)
    drawing.line(a, p, figure.length(request.first("tangent")), ticks=1)
    drawing.line(b, p, ticks=1)
    drawing.line(figure.centre, p, figure.length(request.first("distance")), dashed=True)
    drawing.angle(a, figure.centre, p, right=True)
    drawing.angle(b, figure.centre, p, right=True)
    _angles(figure, request, p, (a, b), (a, b))
    # The angles between the tangents and between the radii are the figure's own (they add
    # to 180°): each is marked even when it is the one asked.
    for at in (p, figure.centre):
        if not any(m.at == at and {m.a, m.b} == {a, b} for m in drawing.angles):
            drawing.angle(at, a, b)
    figure.diameter(request.first("diameter"), 180.0)
    return drawing.spec()


def _contacts(request: FigureRequest, point: str, count: int) -> list[str]:
    """The points of contact the tangents' names letter ("PA", "PB"), or none."""
    found = [
        c for m in request.given("tangent") for c in m.name.strip() if c.isalpha() and c != point
    ]
    found = list(dict.fromkeys(found))
    return found if len(found) == count else [""] * count


def _angles(
    figure: CircleFigure,
    request: FigureRequest,
    outside: str,
    at_point: tuple[str, str],
    at_centre: tuple[str, str],
) -> None:
    """Each stated angle marked where it is: at the outside point (between OP and the
    tangent, or between the tangents) and at the centre, along the rays its name gives."""
    centre = letter(request.center)
    shown = {p.name for p in figure.drawing.points if p.show}
    for m in request.measures:
        if m.what not in {"angle", "central_angle"}:
            continue
        name = m.name.strip()
        vertex = corner_of(name)
        at_o = m.what == "central_angle" or (bool(vertex) and vertex == centre)
        rays = at_centre if at_o else at_point
        if len(name) == 3 and {name[0], name[2]} <= shown:
            rays = (name[0], name[2])
        figure.drawing.angle(figure.centre if at_o else outside, *rays, angle_label(m.value))


def build_intersecting_chords(request: FigureRequest) -> FigureSpec | None:
    """Chords AB and CD crossing at E, each part true (AE·EB = CE·ED), the circle through
    their four ends."""
    names = letters(request, 4) or ["A", "B", "C", "D"]
    cross = letter(request.point) or "E"
    lettered = bool(letters(request, 4)) and bool(letter(request.point))
    holds, size = stated_size(request)
    if not holds or size is not None:
        return None  # a stated radius fixes the angle the chords cross at: not drawn
    parts, wholes, stated_angle = _chord_values(request.measures, names, cross)
    if parts is None:
        return None
    # The angle BED the chords cross at, and the stated one with the ends it is between.
    angle, value, rays = None, None, (1, 3)
    if stated_angle is not None:
        value, rays = stated_angle
        # AED and BEC are BED's neighbours; AEC is its vertical angle.
        angle = 180 - value if set(rays) in ({0, 3}, {1, 2}) else value
    stated = dict(parts)
    if not _solve_parts(parts, wholes, names):
        return None
    gamma = angle if angle is not None else _CROSSING
    if not 0 < gamma < 180:
        return None
    along = (math.cos(math.radians(gamma)), math.sin(math.radians(gamma)))
    a, b = (-parts[names[0]], 0.0), (parts[names[1]], 0.0)
    c = (-parts[names[2]] * along[0], -parts[names[2]] * along[1])
    d = (parts[names[3]] * along[0], parts[names[3]] * along[1])
    centre = _through(a, b, c)
    if centre is None:
        return None
    reach = math.dist(centre, a)
    figure = start(request, "circle_intersecting_chords", reach)
    shift = [(x - centre[0], y - centre[1]) for x, y in (a, b, c, d, (0.0, 0.0))]
    ends = [figure.named(xy, names[i] if lettered else "") for i, xy in enumerate(shift[:4])]
    e = figure.named(shift[4], cross if lettered else "")
    figure.drawing.arc(figure.centre, reach)
    for i, end in enumerate(ends):
        figure.drawing.line(end, e, figure.length(stated.get(names[i])))
    for index, whole in wholes.items():
        # A whole chord stated is labelled along its full length, its parts beside it.
        figure.drawing.line(ends[2 * index], ends[2 * index + 1], figure.length(whole))
    if value is not None:
        figure.drawing.angle(e, ends[rays[0]], ends[rays[1]], angle_label(value))
    return figure.drawing.spec()


# A stated angle at the crossing: its value and the ends (by index) it is between.
_StatedAngle = tuple[float, tuple[int, int]]


def _chord_values(
    measures: list[Measure], names: list[str], cross: str
) -> tuple[dict[str, float] | None, dict[int, float], _StatedAngle | None]:
    """Each stated part by its end ("AE": A), each whole chord by its index, the angle and
    where it is: an angle named AED is marked between A and D, never as BED at 180° less."""
    parts: dict[str, float] = {}
    wholes: dict[int, float] = {}
    angle: _StatedAngle | None = None
    for m in measures:
        name = m.name.strip()
        if m.what == "angle" and corner_of(name) in {cross, ""}:
            ends = (name[0], name[2]) if len(name) == 3 else (names[1], names[3])
            rays = [names.index(end) for end in ends if end in names]
            if len(rays) != 2 or {rays[0] // 2, rays[1] // 2} != {0, 1}:
                return None, {}, None  # not between the two chords
            angle = (m.value, (rays[0], rays[1]))
        elif m.what in _PARTS and len(name) == 2 and cross in name:
            end = name.replace(cross, "", 1)
            if end not in names or end in parts:
                return None, {}, None
            parts[end] = m.value
        elif m.what in _PARTS and set(name) in ({names[0], names[1]}, {names[2], names[3]}):
            wholes[0 if names[0] in name else 1] = m.value
        else:
            return None, {}, None
    return parts, wholes, angle


def _solve_parts(parts: dict[str, float], wholes: dict[int, float], names: list[str]) -> bool:
    """Fill in every part from the stated ones: a whole chord less its known part, the
    product of one chord's parts shared by the other's (a whole chord whose parts are both
    asked splits by that product: the longer part first). True when all four are known and
    hold together."""
    pairs = [(names[0], names[1]), (names[2], names[3])]
    for _ in range(3):
        for index, (x, y) in enumerate(pairs):
            whole, other = wholes.get(index), pairs[1 - index]
            if whole is None or x in parts or y in parts or not set(other) <= parts.keys():
                continue
            root = whole**2 - 4 * parts[other[0]] * parts[other[1]]
            if root < 0:
                return False
            parts[x] = (whole + math.sqrt(root)) / 2
            parts[y] = whole - parts[x]
        for index, (x, y) in enumerate(pairs):
            whole = wholes.get(index)
            if whole is None:
                continue
            if x in parts and y not in parts:
                parts[y] = whole - parts[x]
            elif y in parts and x not in parts:
                parts[x] = whole - parts[y]
        for (x, y), (u, v) in (pairs, pairs[::-1]):
            if x in parts and y in parts and (u in parts) != (v in parts):
                known, missing = (u, v) if u in parts else (v, u)
                parts[missing] = parts[x] * parts[y] / parts[known]
    if len(parts) != 4 or any(value <= 0 for value in parts.values()):
        return False
    products = parts[names[0]] * parts[names[1]], parts[names[2]] * parts[names[3]]
    sums_hold = all(
        close(parts[x] + parts[y], wholes[i]) for i, (x, y) in enumerate(pairs) if i in wholes
    )
    return close(*products) and sums_hold


def _through(
    a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]
) -> tuple[float, float] | None:
    (ax, ay), (bx, by), (cx, cy) = a, b, c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:
        return None
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    return (
        (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d,
        (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d,
    )
