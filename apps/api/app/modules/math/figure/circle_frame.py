"""What every circle figure shares: its size from the stated radius or diameter, its centre
at the origin lettered as the question letters it, the letters of its named points, and a
right triangle worked out from the values a theorem's figure states.

A size the question does not state is drawn, never labelled: the asked radius of a chord's
circle is drawn to its true length from the chord and its distance, and carries no number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.modules.math.figure.drawing import Drawing, length_label, polar
from app.modules.math.figure.request import FigureRequest

DEFAULT_RADIUS = 3.0
TOLERANCE = 1e-6
# The lengths only a circle's own figure draws: a polygon drawn with a circle leaves them out.
CIRCLE_LENGTHS = frozenset({"radius", "diameter", "chord", "distance", "tangent"})
CIRCLE_ANGLES = frozenset({"central_angle", "inscribed_angle"})


def letter(text: str) -> str:
    found = text.strip()[:1]
    return found if found.isalpha() else ""


def letters(request: FigureRequest, count: int) -> list[str]:
    """The question's ``count`` letters for the points on the circle, or none."""
    named = request.vertices.strip()
    if len(named) == count and len(set(named)) == count and named.isalpha():
        return list(named)
    return []


def corner_of(name: str) -> str:
    """The letter an angle's name puts its corner at: "ACB" and "C" are at C."""
    return name[1] if len(name) == 3 else name[:1]


def close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))


def stated_size(request: FigureRequest) -> tuple[bool, float | None]:
    """(holds, radius): the radius the question states, by its radius or its diameter;
    holds is False when the two disagree."""
    radius, diameter = request.first("radius"), request.first("diameter")
    if radius is not None and diameter is not None and not close(2 * radius, diameter):
        return False, None
    return True, radius if radius is not None else (diameter / 2 if diameter else None)


@dataclass
class CircleFigure:
    """A drawing with the circle's centre placed; ``taken`` holds the letters in use."""

    drawing: Drawing
    centre: str
    r: float
    unit: str
    taken: set[str]

    def named(self, xy: tuple[float, float], name: str = "") -> str:
        """A point lettered ``name`` when that letter is free, otherwise unlettered."""
        free = bool(name) and name.isalpha() and name not in self.taken
        if free:
            self.taken.add(name)
        return self.drawing.point(xy, name if free else "", show=free)

    def length(self, value: float | None) -> str | None:
        return length_label(value, self.unit) if value is not None else None

    def diameter(self, value: float | None, turn: float) -> None:
        """A stated diameter drawn across the circle at ``turn``, clear of the centre."""
        if value is None:
            return
        a = self.drawing.point(polar(self.r, turn + 180))
        b = self.drawing.point(polar(self.r, turn))
        self.drawing.line(a, b, self.length(value), label_at=0.75)


def start(request: FigureRequest, shape: str, r: float) -> CircleFigure:
    """The drawing with the circle about its centre at the origin."""
    drawing = Drawing(shape)
    used: set[str] = set()
    name = letter(request.center)
    named = bool(name) and name not in used
    if named:
        used.add(name)
    centre = drawing.point((0.0, 0.0), name if named else "", show=named, dot=True)
    return CircleFigure(drawing, centre, r, request.unit, used)


def right_triangle(
    leg: float | None, other: float | None, hypotenuse: float | None, angle: float | None
) -> tuple[float, float, float] | None:
    """(leg, other leg, hypotenuse) of a right triangle from what is stated, ``angle`` in
    degrees opposite ``leg``; None when the stated values cannot hold together. Fewer than
    two values leave the shape free: one value sets its size, none draws a default."""
    stated = [v for v in (leg, other, hypotenuse) if v is not None]
    if angle is not None and not 0 < angle < 90:
        return None
    if angle is None and len(stated) < 2:
        angle = 35.0
    turn = math.radians(angle) if angle is not None else 0.0
    sine, cosine = math.sin(turn), math.cos(turn)
    if hypotenuse is not None and leg is not None and other is None and angle is None:
        if leg >= hypotenuse:
            return None
        other = math.sqrt(hypotenuse**2 - leg**2)
    elif hypotenuse is not None and other is not None and leg is None and angle is None:
        if other >= hypotenuse:
            return None
        leg = math.sqrt(hypotenuse**2 - other**2)
    elif hypotenuse is None and leg is not None and other is not None and angle is None:
        pass
    elif angle is not None:
        h = _hypotenuse(leg, other, hypotenuse, sine, cosine)
        leg, other, hypotenuse = (
            _agree(leg, h * sine),
            _agree(other, h * cosine),
            _agree(hypotenuse, h),
        )
        if None in (leg, other, hypotenuse):
            return None
    if leg is None or other is None:
        return None
    h = math.hypot(leg, other)
    if hypotenuse is not None and not close(h, hypotenuse):
        return None
    return leg, other, h


def _hypotenuse(
    leg: float | None, other: float | None, hypotenuse: float | None, sine: float, cosine: float
) -> float:
    if hypotenuse is not None:
        return hypotenuse
    if leg is not None:
        return leg / sine
    if other is not None:
        return other / cosine
    return 2 * DEFAULT_RADIUS


def _agree(stated: float | None, worked: float) -> float | None:
    """The worked value, or None when a stated one differs from it."""
    if stated is not None and not close(stated, worked):
        return None
    return worked
