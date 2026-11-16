"""Electric field lines traced from the charges: the server's numbers, the phone's polylines.

A line follows E step by step (fourth-order Runge-Kutta along the arc), so it starts on a
positive charge and ends on a negative one, or runs off the picture. Each charge sends out
lines in proportion to its size, so their crowding shows the field's strength. A point
charge's field is Coulomb's, falling as 1/r^2; a plate's is that of a uniform strip across
the picture, written in closed form, so the gap between two plates holds the uniform field
and the ends fringe a little, as they do.

Nothing here knows what the question said: ``field_lines.picture`` lays the sources out.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable
from dataclasses import dataclass

Point = tuple[float, float]
Polyline = list[Point]

# The step along a line, and the most steps one takes, in the picture's units.
_STEP = 0.025
_MAX_STEPS = 900
# The circle the phone draws for a charge; a line ends on it.
CHARGE_RADIUS = 0.16
_REACHED = CHARGE_RADIUS
# The field is this weak (of its strength at a charge's edge) at a neutral point.
_STILL = 1e-4
# A line simplified to within this much of its traced path.
_TOLERANCE = 0.004


@dataclass(frozen=True)
class PointCharge:
    at: Point
    # Signed, relative to the others: +2 is twice a charge of +1.
    q: float


@dataclass(frozen=True)
class Strip:
    """A charged plate seen edge-on: a uniform strip from ``start`` to ``end`` on y = ``y``."""

    y: float
    start: float
    end: float
    # Charge per unit length, signed.
    density: float


@dataclass(frozen=True)
class Sources:
    charges: tuple[PointCharge, ...] = ()
    strips: tuple[Strip, ...] = ()

    def field(self, x: float, y: float) -> Point:
        ex = ey = 0.0
        for charge in self.charges:
            dx, dy = x - charge.at[0], y - charge.at[1]
            r2 = dx * dx + dy * dy
            if r2 < 1e-12:
                return (0.0, 0.0)
            scale = charge.q / (r2 * math.sqrt(r2))
            ex += scale * dx
            ey += scale * dy
        for strip in self.strips:
            sx, sy = _strip_field(strip, x, y)
            ex += sx
            ey += sy
        return ex, ey


def _strip_field(strip: Strip, x: float, y: float) -> Point:
    """The field of a uniform line charge from ``start`` to ``end``, in the plane, falling
    as 1/r from each element: integral of λ (p - s)/|p - s|^2 ds, integrated exactly."""
    dy = y - strip.y
    a, b = x - strip.start, x - strip.end
    if abs(dy) < 1e-9:
        dy = 1e-9 if dy >= 0 else -1e-9
    ex = 0.5 * math.log((a * a + dy * dy) / max(b * b + dy * dy, 1e-18))
    ey = math.atan(a / dy) - math.atan(b / dy)
    return strip.density * ex, strip.density * ey


@dataclass(frozen=True)
class Box:
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def holds(self, point: Point) -> bool:
        return self.x_min <= point[0] <= self.x_max and self.y_min <= point[1] <= self.y_max

    def grown(self, by: float) -> Box:
        dx = (self.x_max - self.x_min) * by
        dy = (self.y_max - self.y_min) * by
        return Box(self.x_min - dx, self.x_max + dx, self.y_min - dy, self.y_max + dy)


@dataclass(frozen=True)
class Traced:
    points: Polyline
    # How the line ended: on a charge of this index, on a plate, or nowhere (it left the
    # picture or the field died away).
    on_charge: int | None = None
    on_plate: bool = False


def _direction(sources: Sources, point: Point, sign: float) -> Point | None:
    ex, ey = sources.field(*point)
    size = math.hypot(ex, ey)
    if size == 0 or not math.isfinite(size):
        return None
    return sign * ex / size, sign * ey / size


def _rk4(sources: Sources, point: Point, sign: float) -> Point | None:
    h = _STEP

    def at(p: Point) -> Point | None:
        return _direction(sources, p, sign)

    k1 = at(point)
    if k1 is None:
        return None
    k2 = at((point[0] + h / 2 * k1[0], point[1] + h / 2 * k1[1]))
    if k2 is None:
        return None
    k3 = at((point[0] + h / 2 * k2[0], point[1] + h / 2 * k2[1]))
    if k3 is None:
        return None
    k4 = at((point[0] + h * k3[0], point[1] + h * k3[1]))
    if k4 is None:
        return None
    return (
        point[0] + h / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]),
        point[1] + h / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]),
    )


def trace(
    sources: Sources,
    start: Point,
    sign: float,
    outer: Box,
    ends: Callable[[Point], Traced | None] | None = None,
) -> Traced:
    """The line from ``start`` along E (``sign`` 1) or against it (-1), until it reaches a
    charge it runs into, a plate (``ends``), the edge of ``outer``, or a point where the
    field dies away."""
    points: Polyline = [start]
    strength = _strength_near(sources, start)
    point = start
    for _ in range(_MAX_STEPS):
        step = _rk4(sources, point, sign)
        if step is None:
            break
        point = step
        points.append(point)
        for index, charge in enumerate(sources.charges):
            if math.dist(point, charge.at) <= _REACHED and charge.q * sign < 0:
                return Traced(points, on_charge=index)
        ended = ends(point) if ends is not None else None
        if ended is not None:
            return Traced(points, on_charge=ended.on_charge, on_plate=ended.on_plate)
        if not outer.holds(point):
            break
        if math.hypot(*sources.field(*point)) < _STILL * strength:
            break
    return Traced(points)


def _strength_near(sources: Sources, point: Point) -> float:
    return max(math.hypot(*sources.field(*point)), 1e-12)


def clipped(points: Polyline, box: Box) -> list[Polyline]:
    """The runs of a polyline inside ``box``, each ending where it crosses the edge."""
    runs: list[Polyline] = []
    run: Polyline = []
    for a, b in itertools.pairwise(points):
        piece = _clip_segment(a, b, box)
        if piece is None:
            if len(run) >= 2:
                runs.append(run)
            run = []
            continue
        start, end = piece
        if not run or run[-1] != start:
            if len(run) >= 2:
                runs.append(run)
            run = [start]
        run.append(end)
        if end != b:
            runs.append(run)
            run = []
    if len(run) >= 2:
        runs.append(run)
    return runs


def _clip_segment(a: Point, b: Point, box: Box) -> tuple[Point, Point] | None:
    """Liang-Barsky: the part of the segment inside ``box``."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in (
        (-dx, a[0] - box.x_min),
        (dx, box.x_max - a[0]),
        (-dy, a[1] - box.y_min),
        (dy, box.y_max - a[1]),
    ):
        if p == 0:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    start = a if t0 == 0 else (a[0] + t0 * dx, a[1] + t0 * dy)
    end = b if t1 == 1 else (a[0] + t1 * dx, a[1] + t1 * dy)
    return start, end


def simplified(points: Polyline, tolerance: float = _TOLERANCE) -> Polyline:
    """Ramer-Douglas-Peucker, iteratively: the fewest points within ``tolerance``."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        far, at = 0.0, -1
        for index in range(first + 1, last):
            gap = _gap(points[index], points[first], points[last])
            if gap > far:
                far, at = gap, index
        if at >= 0 and far > tolerance:
            keep[at] = True
            stack.extend(((first, at), (at, last)))
    return [point for point, kept in zip(points, keep, strict=True) if kept]


def _gap(point: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return math.dist(point, a)
    return abs(dy * (point[0] - a[0]) - dx * (point[1] - a[1])) / length


def midpoint_arrow(
    points: Polyline, avoid: tuple[Point, ...], clear: float
) -> tuple[Point, Point] | None:
    """Where a line's arrowhead goes and which way it points: halfway along the line, moved
    along it until it clears every point of ``avoid`` (the charges) by ``clear``."""
    lengths = [math.dist(a, b) for a, b in itertools.pairwise(points)]
    total = sum(lengths)
    if total <= 0:
        return None
    for fraction in (0.5, 0.4, 0.6, 0.3, 0.7):
        point, direction = _at_length(points, lengths, total * fraction)
        if all(math.dist(point, other) >= clear for other in avoid):
            return point, direction
    return None


def _at_length(points: Polyline, lengths: list[float], target: float) -> tuple[Point, Point]:
    walked = 0.0
    for (a, b), length in zip(itertools.pairwise(points), lengths, strict=True):
        if length > 0 and walked + length >= target:
            t = (target - walked) / length
            point = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            return point, ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
        walked += length
    a, b = points[-2], points[-1]
    length = max(math.dist(a, b), 1e-12)
    return b, ((b[0] - a[0]) / length, (b[1] - a[1]) / length)


def neutral_points(sources: Sources, box: Box) -> list[Point]:
    """Where the field of point charges in a row on y = 0 is zero, on the row: between two
    like charges, and beyond the smaller of two unlike ones. Each found by bisection on E_x
    between two charges (or a charge and the picture's edge), and kept only when the field
    there is zero to within ``_STILL`` of its strength near a charge."""
    xs = sorted(charge.at[0] for charge in sources.charges)
    if not xs or any(charge.at[1] != 0 for charge in sources.charges):
        return []
    edges = [box.x_min, *xs, box.x_max]
    near = max(_strength_near(sources, (x + _REACHED, 0.0)) for x in xs)
    found: list[Point] = []
    for left, right in itertools.pairwise(edges):
        lo, hi = left + _REACHED, right - _REACHED
        if hi <= lo:
            continue
        # An odd count: two equal like charges have their zero halfway, never on a sample.
        samples = 61
        previous = None
        for step in range(samples + 1):
            x = lo + (hi - lo) * step / samples
            value = sources.field(x, 0.0)[0]
            if previous is not None and previous[1] * value < 0:
                root = _bisect(sources, previous[0], x)
                if math.hypot(*sources.field(root, 0.0)) < _STILL * near:
                    found.append((root, 0.0))
            previous = (x, value)
    return found


def _bisect(sources: Sources, lo: float, hi: float) -> float:
    f_lo = sources.field(lo, 0.0)[0]
    for _ in range(60):
        mid = (lo + hi) / 2
        f_mid = sources.field(mid, 0.0)[0]
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2
