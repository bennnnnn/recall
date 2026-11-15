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
_TEXTBOOK = 30.0
_TURNS = sorted(
    range(0, 360, 10),
    key=lambda turn: (min(abs(turn - _TEXTBOOK), 360 - abs(turn - _TEXTBOOK)), turn),
)
# Two points closer than this share of the drawing fall together.
_APART = 0.03
# A point outside a sphere is drawn at least this far outside its outline, as a share of
# the radius.
_OUTSIDE = 0.03
# Named points nearer than this share of the drawing crowd each other's letters.
_NAMES_APART = 0.08
# An arrow drawn shorter than this share of its length reads as another length.
_SHORTEST = 0.6
# Arrows from one point closer than this in direction read as one.
_CROWDED = math.radians(9)
# A marked angle drawn this far from its size reads as another angle.
_ANGLE_SLACK = 25.0
_AXES = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


class View:
    """Orthographic projection seen from ``azimuth`` degrees round from the x-axis."""

    def __init__(self, azimuth: float) -> None:
        turn = math.radians(azimuth)
        self._sin, self._cos = math.sin(turn), math.cos(turn)
        self._up, self._flat = math.sin(_ELEVATION), math.cos(_ELEVATION)
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


def _crowded_names(scene: Scene, view: View) -> float:
    """Named points drawn so near each other that their letters read as one another's."""
    flat = [view(floats(scene.points[name])) for name in scene.shown]
    size = span(scene, view)
    return sum(
        1.0
        for i, a in enumerate(flat)
        for b in flat[i + 1 :]
        if math.dist(a, b) < _NAMES_APART * size
    )


def _penalty(scene: Scene, view: View) -> float:
    """How far a view falls short of clear: 0 for none."""
    penalty = sum(_short(view, way) for way in _lines(scene)) + _crowded_names(scene, view)
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
                penalty += 1.0
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
    for turn in _TURNS:
        view = View(float(turn))
        if not _honest(scene, view):
            continue
        penalty = _penalty(scene, view)
        if penalty == 0:
            return view
        if best is None or penalty < best[0]:
            best = (penalty, view)
    return best[1] if best is not None else None
