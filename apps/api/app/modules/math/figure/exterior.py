"""A triangle's exterior angle: one side drawn on past a corner, the angle outside marked.

The exterior angle at C (between CA and BC drawn on to D) is the sum of the two interior
angles opposite it, A and B. The question states the exterior angle and one or both of
those: what it leaves open is worked out (the other opposite angle, C itself) and drawn to
size, unlabelled; a stated angle at C must be 180° less the exterior one. Opposite angles
that add up to more than it, or to another sum when both are stated, draw nothing. Angles
written with a letter ("x", "2x + 10") are solved where the exterior angle decides them,
and labelled as written.
"""

from __future__ import annotations

import math

from app.modules.math.figure.angle_terms import sized_angles
from app.modules.math.figure.drawing import Drawing, angle_label, polar
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec

_BASE = 5.0
# How far the side runs on past the corner, against the base; how what is left is shared.
_RUN_ON = 0.5
_SHARE = 0.45
_TOLERANCE = 1e-6


def _letters(request: FigureRequest) -> tuple[str, str, str, str, bool]:
    """A, B, C (the corner outside which the angle is), D (the side drawn on), shown."""
    letters = request.vertices.strip()
    outside = next((m.name.strip() for m in request.given("exterior_angle")), "")
    if len(letters) == 3 and len(set(letters)) == 3 and letters.isalpha():
        corner = outside[1] if len(outside) == 3 else outside[:1]
        if corner not in letters:
            corner = letters[2]
        a, b = (letter for letter in letters if letter != corner)
        if len(outside) == 3 and outside[0] in letters and outside[0] != corner:
            a = outside[0]
            b = next(letter for letter in letters if letter not in {a, corner})
        extra = outside[2] if len(outside) == 3 and outside[2] not in letters else "D"
        return a, b, corner, extra, True
    return "A", "B", "C", "D", False


def _opposite(
    request: FigureRequest, names: tuple[str, str, str], exterior: float
) -> dict[str, float] | None:
    """The interior angles stated opposite the exterior one, at A and B: each where its
    letter puts it, an unnamed one at A first. None when one at C disagrees with the
    exterior angle, or more are stated than fit."""
    a, b, c = names
    found: dict[str, float] = {}
    unnamed: list[float] = []
    outside = request.given("exterior_angle")[0]
    for m in request.given("angle"):
        name = m.name.strip()
        vertex = name[1] if len(name) == 3 else name[:1]
        if name and name == outside.name.strip() and m.value == outside.value:
            continue  # the exterior angle read twice, once as a plain angle
        if vertex == c:
            if abs(m.value + exterior - 180) > _TOLERANCE:
                return None
        elif vertex in {a, b} and vertex not in found:
            found[vertex] = m.value
        elif vertex:
            return None
        else:
            unnamed.append(m.value)
    for value in unnamed:
        free = next((letter for letter in (a, b) if letter not in found), None)
        if free is None:
            return None
        found[free] = value
    return found


def build_exterior(request: FigureRequest) -> FigureSpec | None:
    if len(request.given("exterior_angle")) != 1 or any(
        m.what not in {"angle", "exterior_angle"} for m in request.measures
    ):
        return None
    a, b, c, d, shown = _letters(request)
    exterior = request.given("exterior_angle")[0].value
    if not 0 < exterior < 180:
        return None
    labels: dict[str, str] = {}
    if request.angle_terms:
        sized = sized_angles(
            request.model_copy(update={"measures": request.given("angle")}), exterior
        )
        if sized is None or len(sized) != 2:
            return None
        sizes = [angle.size for angle in sized]
        labels = {a: sized[0].label or angle_label(sizes[0])}
        labels[b] = sized[1].label or angle_label(sizes[1])
    else:
        opposite = _opposite(request, (a, b, c), exterior)
        if opposite is None:
            return None
        if len(opposite) == 2 and abs(sum(opposite.values()) - exterior) > _TOLERANCE:
            return None
        if any(value >= exterior for value in opposite.values()):
            return None
        at_a = opposite.get(a)
        if at_a is None:
            at_a = exterior - opposite[b] if b in opposite else exterior * _SHARE
        sizes = [at_a, exterior - at_a]
        labels = {letter: angle_label(value) for letter, value in opposite.items()}
    return _draw(request, (a, b, c, d), shown, sizes, exterior, labels)


def _draw(
    request: FigureRequest,
    names: tuple[str, str, str, str],
    shown: bool,
    sizes: list[float],
    exterior: float,
    labels: dict[str, str],
) -> FigureSpec:
    a, b, c, d = names
    at_a, at_b = sizes
    # B bottom left, C bottom right, A over them: AB from the law of sines on BC.
    side_ab = _BASE * math.sin(math.radians(180 - exterior)) / math.sin(math.radians(at_a))
    drawing = Drawing("triangle_exterior_angle")
    drawing.point(polar(side_ab, at_b), a, show=shown)
    drawing.point((0.0, 0.0), b, show=shown)
    drawing.point((_BASE, 0.0), c, show=shown)
    drawing.point((_BASE * (1 + _RUN_ON), 0.0), d, show=shown)
    drawing.outline([a, b, c])
    drawing.line(c, d)
    drawing.angle(c, a, d, angle_label(exterior))
    drawing.angle(a, b, c, labels.get(a))
    drawing.angle(b, c, a, labels.get(b))
    return drawing.spec()
