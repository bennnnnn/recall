"""Where a scene in space is seen from: true projection, and the clearest honest view.

The scene is seen in true (orthographic) projection, from as far above as ``figure.solids``
draws its round solids (a circle lying flat is an ellipse 0.3 as tall as it is wide), with
z up. In true projection a sphere's outline is a circle of its radius, so a point inside the
sphere is drawn inside it. The view turns about z. A view must be honest: no two of the
scene's points fall together, and a point outside a sphere is drawn outside its outline;
a scene no view shows that way is not drawn. Among honest views the clearest is taken,
nearest the textbook's (the x-axis coming toward the reader, down and to the left): no
arrow drawn much shorter than it is, none lying along an axis or another arrow it is not
on, and each marked angle drawn near its size.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from app.modules.math.drawing.question import Triple
from app.modules.math.drawing.scene import ORIGIN, Scene
from app.modules.math.figure.drawing import Point, angle_at
from app.modules.math.figure.solids import ELLIPSE

_ELEVATION = math.asin(ELLIPSE)
_OTHER_HEIGHTS = tuple(math.radians(degrees) for degrees in (28.0, 38.0, 10.0))
_TEXTBOOK = 30.0
_TURNS = sorted(
    range(0, 360, 10),
    key=lambda turn: (min(abs(turn - _TEXTBOOK), 360 - abs(turn - _TEXTBOOK)), turn),
)
# An axis runs past the farthest point by this share, and at least this share of the
# scene's reach; it starts a little behind the origin.
_PAST = 0.15
_LEAST = 0.35
_BEHIND = 0.12
# Two points closer than this share of the drawing fall together.
_APART = 0.03
# A point outside a sphere is drawn at least this far outside its outline, as a share of
# the radius.
_OUTSIDE = 0.03
# The phone sets a point's letter about this share of the drawing from it; letters nearer
# each other than the next share, or a letter this near another point, read as one another's.
_LETTER_GAP = 0.045
_LABELS_APART = 0.06
_CLEAR_OF_DOTS = 0.035
# Where along an arrow its name sits: by its head.
NAME_AT = 0.85
# Axes nearer each other than this in the drawing read as one line.
_AXES_APART = math.radians(25)
# An axis drawn shorter than this share of its length is seen end on.
_END_ON = 0.45
# An arrow drawn shorter than this share of its length reads as another length.
_SHORTEST = 0.6
# Arrows from one point closer than this in direction read as one.
_CROWDED = math.radians(15)
# A marked angle drawn this far from its size reads as another angle.
_ANGLE_SLACK = 25.0
_AXES = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


class View:
    """Orthographic projection seen from ``azimuth`` degrees round from the x-axis, from
    ``elevation`` above (the solids' own height by default)."""

    def __init__(self, azimuth: float, elevation: float = _ELEVATION) -> None:
        turn = math.radians(azimuth)
        self._sin, self._cos = math.sin(turn), math.cos(turn)
        self._up, self._flat = math.sin(elevation), math.cos(elevation)
        # Toward the reader.
        self.toward = (self._flat * self._cos, self._flat * self._sin, self._up)

    def __call__(self, xyz: Iterable[float]) -> Point:
        x, y, z = xyz
        across = -x * self._sin + y * self._cos
        up = -(x * self._cos + y * self._sin) * self._up + z * self._flat
        return (across, up)


def floats(xyz: Triple) -> tuple[float, float, float]:
    return (float(xyz[0]), float(xyz[1]), float(xyz[2]))


def span(scene: Scene, view: View) -> float:
    flat = [view(floats(p)) for p in scene.points.values()]
    for sphere in scene.spheres:
        cx, cy = view(floats(scene.points[sphere.centre]))
        r = math.sqrt(float(sphere.radius_squared))
        flat += [(cx - r, cy - r), (cx + r, cy + r)]
    xs, ys = [p[0] for p in flat], [p[1] for p in flat]
    return max(max(xs) - min(xs), max(ys) - min(ys), 1e-9)


def _honest(scene: Scene, view: View) -> bool:
    if scene.axes and any(_short(view, axis) > _SHORTEST - _END_ON for axis in _AXES):
        return False  # an axis seen end on: a dot, its letter on the origin
    if scene.axes:
        ways = [view(axis) for axis in _AXES]
        # Two axes drawn along one line (or opposite ways on it) read as one.
        for i, a in enumerate(ways):
            for b in ways[i + 1 :]:
                turn = _turn(a, b)
                if min(turn, math.pi - turn) < _AXES_APART:
                    return False
    size = span(scene, view)
    own = {floats(scene.points[name]) for name in scene.dots | scene.shown}
    flat = [view(xyz) for xyz in own]
    for i, a in enumerate(flat):
        if any(math.dist(a, b) < _APART * size for b in flat[i + 1 :]):
            return False
    for sphere in scene.spheres:
        centre = scene.points[sphere.centre]
        r = math.sqrt(float(sphere.radius_squared))
        for xyz in scene.points.values():
            gap = [a - b for a, b in zip(xyz, centre, strict=True)]
            if sum(g * g for g in gap) > sphere.radius_squared:
                drawn = math.dist(view(floats(xyz)), view(floats(centre)))
                if drawn < r * (1 + _OUTSIDE):
                    return False
    return True


def _rays(scene: Scene) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Each arrow as (start, direction), and the axes from the origin when drawn."""
    rays = []
    for start, tip, _ in scene.arrows:
        a, b = floats(scene.points[start]), floats(scene.points[tip])
        rays.append((a, (b[0] - a[0], b[1] - a[1], b[2] - a[2])))
    if scene.axes:
        origin = floats(scene.points[ORIGIN])
        for axis in _AXES:
            rays += [(origin, (float(axis[0]), float(axis[1]), float(axis[2])))]
            rays += [(origin, (-float(axis[0]), -float(axis[1]), -float(axis[2])))]
    return rays


def _turn(a: Point, b: Point) -> float:
    cosine = (a[0] * b[0] + a[1] * b[1]) / max(math.hypot(*a) * math.hypot(*b), 1e-12)
    return math.acos(max(-1.0, min(1.0, cosine)))


def _lines(scene: Scene) -> list[tuple[float, float, float]]:
    """The scene's segments and box diagonals, each as the way from one end to the other."""
    pairs = [(a, b) for a, b, _label in scene.segments]
    pairs += [(box.corners[i], box.corners[j]) for box in scene.boxes for i, j in box.diagonals]
    ways = []
    for a, b in pairs:
        p, q = floats(scene.points[a]), floats(scene.points[b])
        ways.append((q[0] - p[0], q[1] - p[1], q[2] - p[2]))
    return ways


def _short(view: View, way: tuple[float, float, float]) -> float:
    """How much shorter than it is a line is drawn, past what reads as its length."""
    length = math.sqrt(sum(w * w for w in way))
    return max(0.0, _SHORTEST - math.hypot(*view(way)) / length) if length else 0.0


def axis_ends(scene: Scene) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Each axis's two ends: past the farthest point (and sphere) on it, at least a share of
    the scene's reach, starting a little behind the origin."""
    values = [floats(p) for p in scene.points.values()]
    for sphere in scene.spheres:
        r = math.sqrt(float(sphere.radius_squared))
        cx, cy, cz = floats(scene.points[sphere.centre])
        values += [(cx - r, cy - r, cz - r), (cx + r, cy + r, cz + r)]
    reach = max(max(abs(v) for v in xyz) for xyz in values) or 1.0
    ends = []
    for i in range(3):
        high = max(max(xyz[i] for xyz in values) * (1 + _PAST), _LEAST * reach)
        low = min(min(xyz[i] for xyz in values) * (1 + _PAST), -_BEHIND * reach)
        start, end = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
        start[i], end[i] = low, high
        ends.append(((start[0], start[1], start[2]), (end[0], end[1], end[2])))
    return ends


def _away(point: Point, middle: Point, gap: float) -> Point:
    dx, dy = point[0] - middle[0], point[1] - middle[1]
    length = math.hypot(dx, dy) or 1.0
    return (point[0] + dx / length * gap, point[1] + dy / length * gap)


def _crowded_labels(scene: Scene, view: View) -> float:
    """Letters the phone would set on one another or on another point: each point's letter
    away from the drawing's middle, each arrow's name beside its head."""
    size = span(scene, view)
    flat = {name: view(floats(xyz)) for name, xyz in scene.points.items()}
    # The phone's middle is all the drawing's points': the axes' ends among them.
    spread = list(flat.values())
    if scene.axes:
        spread += [view(end) for pair in axis_ends(scene) for end in pair]
    middle = (sum(p[0] for p in spread) / len(spread), sum(p[1] for p in spread) / len(spread))
    shown = scene.shown | ({ORIGIN} if scene.axes else set())
    labels = [(name, _away(flat[name], middle, _LETTER_GAP * size)) for name in shown]
    if scene.axes:
        # Each axis's letter beside its head.
        labels += [
            ("", _away(view(end), middle, _LETTER_GAP * size)) for _s, end in axis_ends(scene)
        ]
    for start, tip, name in scene.arrows:
        if name:
            a, b = flat[start], flat[tip]
            at = (a[0] + (b[0] - a[0]) * NAME_AT, a[1] + (b[1] - a[1]) * NAME_AT)
            labels.append((tip, _away(at, middle, _LETTER_GAP * size)))
    dots = {name: flat[name] for name in scene.dots | shown}
    penalty = 0.0
    for i, (own, label) in enumerate(labels):
        penalty += sum(
            1.0 for _o, other in labels[i + 1 :] if math.dist(label, other) < _LABELS_APART * size
        )
        penalty += sum(
            0.5
            for name, dot in dots.items()
            if name != own and math.dist(label, dot) < _CLEAR_OF_DOTS * size
        )
    return penalty


def _penalty(scene: Scene, view: View) -> float:
    """How far a view falls short of clear: 0 for none."""
    penalty = sum(_short(view, way) for way in _lines(scene)) + _crowded_labels(scene, view)
    if scene.axes:
        # An axis seen end-on is a dot with its letter on the origin.
        penalty += sum(_short(view, axis) for axis in _AXES)
    rays = _rays(scene)
    arrows = len(scene.arrows)
    for i, (start, way) in enumerate(rays[:arrows]):
        flat = view(way)
        length = math.sqrt(sum(w * w for w in way))
        penalty += _short(view, way)
        for other_start, other in rays[:i] + rays[i + 1 :]:
            if other_start != start:
                continue
            same = all(
                abs(w / length - o / math.sqrt(sum(v * v for v in other))) < 1e-9
                for w, o in zip(way, other, strict=True)
            )
            if not same and _turn(flat, view(other)) < _CROWDED:
                penalty += 2.0
    for at, a, b, _label, _right in scene.angles:
        drawn = angle_at(*(view(floats(scene.points[n])) for n in (at, a, b)))
        u, v = (
            [p - q for p, q in zip(floats(scene.points[n]), floats(scene.points[at]), strict=True)]
            for n in (a, b)
        )
        cosine = sum(p * q for p, q in zip(u, v, strict=True)) / math.sqrt(
            sum(p * p for p in u) * sum(q * q for q in v)
        )
        size = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
        penalty += max(0.0, abs(drawn - size) - _ANGLE_SLACK) / 90.0
    return penalty


def clearest_view(scene: Scene) -> View | None:
    """The clearest honest view, nearest the textbook's; None when no view is honest."""
    best: tuple[float, View] | None = None
    # A sphere's equator is the solids' flat ellipse, seen from their height; a scene with
    # none may be seen from higher or lower, where its arrows stand clear of each other.
    heights = [_ELEVATION] if scene.spheres else [_ELEVATION, *_OTHER_HEIGHTS]
    for height, turn in ((height, turn) for height in heights for turn in _TURNS):
        view = View(float(turn), height)
        if not _honest(scene, view):
            continue
        penalty = _penalty(scene, view)
        if penalty == 0:
            return view
        if best is None or penalty < best[0]:
            best = (penalty, view)
    return best[1] if best is not None else None
