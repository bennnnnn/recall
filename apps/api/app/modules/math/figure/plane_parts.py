"""The parts of a coordinate plane worked out from the stated points: a polygon's marks, a
segment's midpoint, rise and run or bisector, a circle's centre and radius, and the image
of each stated transformation with what shows how it was made."""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from fractions import Fraction

from app.modules.math.figure.plane_draw import Exact, Plane, as_float, centroid, side_from
from app.modules.math.figure.plane_text import coordinate_text, pair_text, point_label, primed
from app.modules.math.figure.transforms import Line, Mapping
from app.modules.math.schemas.figure import PlaneCircle, PlanePolygon, PlaneRole, PlaneSegment

_MAX_TICKS = 3
# The most vertices whose path to their image a reflection draws: more crowd the picture.
_MAX_PATHS = 4


def _turn(o: Exact, a: Exact, b: Exact) -> Fraction:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _crosses(p: Exact, q: Exact, r: Exact, s: Exact) -> bool:
    """Segments pq and rs meet (touching or overlapping counts)."""
    d1, d2, d3, d4 = _turn(r, s, p), _turn(r, s, q), _turn(p, q, r), _turn(p, q, s)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and 0 not in (d1, d2, d3, d4):
        return True

    def on(a: Exact, b: Exact, c: Exact) -> bool:
        within = min(a[0], b[0]) <= c[0] <= max(a[0], b[0])
        return within and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])

    return (
        (d1 == 0 and on(r, s, p))
        or (d2 == 0 and on(r, s, q))
        or (d3 == 0 and on(p, q, r))
        or (d4 == 0 and on(p, q, s))
    )


def simple(corners: Sequence[Exact]) -> bool:
    """The corners in their stated order make a polygon: distinct, enclosing an area, and
    no side crossing another."""
    n = len(corners)
    if len(set(corners)) != n:
        return False
    area = sum(
        _turn((Fraction(0), Fraction(0)), corners[i], corners[(i + 1) % n]) for i in range(n)
    )
    if area == 0:
        return False
    edges = [(corners[i], corners[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            if _crosses(*edges[i], *edges[j]):
                return False
    return True


def _dot(at: Exact, a: Exact, b: Exact) -> Fraction:
    return (a[0] - at[0]) * (b[0] - at[0]) + (a[1] - at[1]) * (b[1] - at[1])


def _squared(a: Exact, b: Exact) -> Fraction:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _ticks(edges: list[tuple[Exact, Exact]]) -> list[int]:
    """Equal sides marked alike (one tick, two, three), each set only when it is exact."""
    lengths = [_squared(a, b) for a, b in edges]
    marks: dict[Fraction, int] = {}
    for length in lengths:
        if lengths.count(length) > 1 and length not in marks and len(marks) < _MAX_TICKS:
            marks[length] = len(marks) + 1
    return [marks.get(length, 0) for length in lengths]


def polygon(plane: Plane, corners: list[Exact], role: PlaneRole, parts: Sequence[str]) -> bool:
    """A polygon at its corners, in their order; False when that order is no polygon."""
    if not simple(corners):
        return False
    image = role == "image"
    plane.polygons.append(PlanePolygon(points=[as_float(c) for c in corners], role=role))
    n = len(corners)
    edges = [(corners[i], corners[(i + 1) % n]) for i in range(n)]
    ticks = [0] * n if image else _ticks(edges)
    for (a, b), tick in zip(edges, ticks, strict=True):
        plane.segment(a, b, role=role, dashed=image, ticks=tick)
    if not image:
        for i, at in enumerate(corners):
            before, after = corners[i - 1], corners[(i + 1) % n]
            dot = (before[0] - at[0]) * (after[0] - at[0]) + (before[1] - at[1]) * (
                after[1] - at[1]
            )
            if dot == 0:
                plane.right_angle(at, before, after)
    if n == 4 and not image and any("diagonal" in part for part in parts):
        _diagonals(plane, corners, "midpoint" in parts)
    return True


def _free_letter(plane: Plane, *letters: str) -> str:
    return next((letter for letter in letters if letter not in plane.names), "")


def _diagonals(plane: Plane, corners: list[Exact], midpoints: bool) -> None:
    a, b, c, d = corners
    plane.segment(a, c, role="guide", dashed=True)
    plane.segment(b, d, role="guide", dashed=True)
    across = (c[0] - a[0]) * (d[1] - b[1]) - (c[1] - a[1]) * (d[0] - b[0])
    square = (c[0] - a[0]) * (d[0] - b[0]) + (c[1] - a[1]) * (d[1] - b[1]) == 0
    if across and square:  # diagonals at right angles (a rhombus, a kite): marked where they meet
        t = ((b[0] - a[0]) * (d[1] - b[1]) - (b[1] - a[1]) * (d[0] - b[0])) / across
        meet = (a[0] + t * (c[0] - a[0]), a[1] + t * (c[1] - a[1]))
        plane.right_angle(meet, c if meet != c else a, d if meet != d else b)
    if not midpoints:
        return
    first, second = _middle(a, c), _middle(b, d)
    for at in dict.fromkeys([first, second]):
        letter = _free_letter(plane, "M", "N", "K")
        if letter:
            plane.names.add(letter)
            plane.point(at, letter, "shape", "se")


def _middle(a: Exact, b: Exact) -> Exact:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def segment_parts(plane: Plane, a: Exact, b: Exact, parts: Sequence[str]) -> None:
    """What is asked of the segment AB: its midpoint (the halves marked equal), the rise
    and run of its gradient, the legs of its length by Pythagoras, its perpendicular
    bisector through the midpoint at a right angle."""
    asked = set(parts)
    bisector = bool(asked & {"perpendicular_bisector", "bisector"})
    if bisector or "midpoint" in asked:
        _midpoint(plane, a, b, bisector)
    gradient = bool(asked & {"gradient", "slope"})
    if gradient or asked & {"distance", "length"}:
        _legs(plane, a, b, gradient)


def _midpoint(plane: Plane, a: Exact, b: Exact, bisector: bool) -> None:
    middle = _middle(a, b)
    plane.segments = [s for s in plane.segments if {s.start, s.end} != {as_float(a), as_float(b)}]
    plane.segment(a, middle, ticks=1)
    plane.segment(middle, b, ticks=1)
    rising = (b[0] - a[0]) * (b[1] - a[1]) > 0
    letter = _free_letter(plane, "M", "N", "K")
    if letter:
        plane.names.add(letter)
        plane.point(middle, letter, "shape", "se" if rising else "ne")
    if bisector:
        across = (a[1] - b[1], b[0] - a[0])
        plane.line(middle, across, None, "guide")
        plane.right_angle(middle, a, (middle[0] + across[0], middle[1] + across[1]))


def _legs(plane: Plane, a: Exact, b: Exact, gradient: bool) -> None:
    """The run along x then the rise along y from the left end: labelled Δx and Δy for a
    gradient, their lengths for a distance, the corner square."""
    left, right = (a, b) if a[0] <= b[0] else (b, a)
    run, rise = right[0] - left[0], right[1] - left[1]
    if run == 0 or rise == 0:
        return
    corner = (right[0], left[1])
    run_label = f"Δx = {coordinate_text(run)}" if gradient else coordinate_text(run)
    rise_label = f"Δy = {coordinate_text(rise)}" if gradient else coordinate_text(abs(rise))
    plane.segment(left, corner, role="guide", dashed=True, label=run_label)
    plane.segment(corner, right, role="guide", dashed=True, label=rise_label)
    plane.right_angle(corner, left, right)


def circle(
    plane: Plane,
    centre: Exact,
    squared: Fraction,
    radius_label: str,
    centre_label: str,
    towards: Exact | None = None,
) -> None:
    """The circle, its centre marked and a radius drawn: to the stated point it passes
    through, or to its right."""
    radius = math.sqrt(float(squared))
    x, y = as_float(centre)
    plane.circles.append(PlaneCircle(center=(x, y), radius=radius))
    plane.point(centre, centre_label, "shape", "sw")
    end = as_float(towards) if towards is not None else (x + radius, y)
    plane.segments.append(PlaneSegment(start=(x, y), end=end, label=radius_label, dashed=True))


def centre_label(plane: Plane, centre: Exact, letter: str, stated: bool) -> str:
    """A circle's centre: its letter, the question's or C, with its coordinates when the
    question states them (worked out from an equation, they are the answer: left off)."""
    letter = letter.strip() or _free_letter(plane, "C", "O", "M", "K")
    plane.names.add(letter)
    return point_label(letter, centre) if stated else letter or pair_text(centre)


def _image_label(name: str, step: int, at: Exact, alone: bool) -> str:
    """An image's letter (A'), or for an unnamed lone point its coordinates."""
    letter = primed(name, step)
    return letter or (point_label("", at) if alone else "")


def images(plane: Plane, group: list[tuple[str, Exact]], maps: list[Mapping], join: str) -> None:
    """Each transformation's image of the shape, worked out exactly, primed and dashed;
    with one transformation, what shows how it was made."""
    current = group
    for step, mapping in enumerate(maps, start=1):
        current = [(name, mapping.apply(at)) for name, at in current]
        corners = [at for _, at in current]
        middle = centroid(corners)
        for (name, _), at in zip(group, corners, strict=True):
            label = _image_label(name, step, at, len(group) == 1)
            if label:
                plane.point(at, label, "image", side_from(at, middle))
        if join == "polygon" and len(corners) >= 3:
            plane.polygons.append(PlanePolygon(points=[as_float(c) for c in corners], role="image"))
            corners = [*corners, corners[0]]
        if join in {"segment", "polygon"}:
            for a, b in itertools.pairwise(corners):
                plane.segment(a, b, role="image", dashed=True)
        if mapping.mirror is not None and mapping.mirror_text:
            _mirror_line(plane, mapping.mirror, mapping.mirror_text)
    if len(maps) == 1:
        _how(plane, [at for _, at in group], maps[0])


def _mirror_line(plane: Plane, mirror: Line, text: str) -> None:
    a, b, c = mirror
    at = (Fraction(0), c / b) if b else (c / a, Fraction(0))
    plane.line(at, (b, -a), text, "guide")


def _how(plane: Plane, corners: list[Exact], mapping: Mapping) -> None:
    """What shows the transformation: the paths a reflection's points take, a rotation's
    arms from its centre, a translation's vector, an enlargement's rays."""
    moved = [(at, mapping.apply(at)) for at in corners if mapping.apply(at) != at]
    if mapping.centre is not None and mapping.centre_stated:
        plane.point(mapping.centre, pair_text(mapping.centre), "guide", "sw")
    if not moved:
        return
    if mapping.kind == "reflection" and len(corners) <= _MAX_PATHS:
        for at, image in moved:
            plane.segment(at, image, role="guide", dashed=True)
    elif mapping.kind == "translation" and mapping.vector is not None:
        at, image = moved[0]
        plane.segment(
            at, image, role="guide", dashed=True, arrow=True, label=pair_text(mapping.vector)
        )
    elif mapping.kind == "rotation" and mapping.centre is not None:
        moved = [(at, image) for at, image in moved if at != mapping.centre]
        if not moved:
            return
        at, image = moved[0]
        plane.segment(mapping.centre, at, role="guide", dashed=True)
        plane.segment(mapping.centre, image, role="guide", dashed=True)
        if mapping.turn in {90, 270}:
            plane.right_angle(mapping.centre, at, image)
    elif mapping.kind == "enlargement" and mapping.centre is not None and mapping.factor:
        for at, image in moved:
            if mapping.factor > 0:
                far = image if abs(mapping.factor) > 1 else at
                plane.segment(mapping.centre, far, role="guide", dashed=True)
            else:
                plane.segment(mapping.centre, at, role="guide", dashed=True)
                plane.segment(mapping.centre, image, role="guide", dashed=True)
