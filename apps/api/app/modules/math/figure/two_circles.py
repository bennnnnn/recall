"""Two circles with different centres, drawn true to their radii and the distance between
their centres.

Circles that cross meet at two points, and the chord between them (their common chord) is
cut in half at right angles by the line of the centres: so the two radii and either the
distance or the common chord draw the rest. Circles that touch, or lie apart, are drawn as
they are, each with its radius. A stated value is labelled; one the question asks for (the
chord, the distance) is drawn to its size, unlabelled. Values that cannot hold together (a
common chord longer than a circle's diameter, a chord of circles that never meet) draw
nothing. A reading that gives one circle two different radii and a distance between centres
is this figure, whatever the read named it: one circle has one radius (2026-11-21, read as
"intersecting_chords").
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence

from app.modules.math.figure.circle_frame import close
from app.modules.math.figure.drawing import Drawing, length_label, polar
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec

SHAPES = frozenset(
    {"two_circles", "intersecting_circles", "touching_circles", "common_chord", "circles"}
)
_SIZES = frozenset({"radius", "diameter"})
_ALLOWED = _SIZES | {"distance", "chord"}
# Where each radius points when the circles do not cross: up, clear of the centres' line.
_UP = 90.0
_TOLERANCE = 1e-6
# Circles the question says touch: their centres the radii's sum apart, or their difference.
_OUTSIDE = re.compile(
    r"\b(?:touch\w*|tangent)\b[^.;?!]{0,24}\bexternally\b|\bexternally (?:touch\w*|tangent)\b"
)
_INSIDE = re.compile(
    r"\b(?:touch\w*|tangent)\b[^.;?!]{0,24}\binternally\b|\binternally (?:touch\w*|tangent)\b"
)
TOUCHING = {"outside": "touch_outside", "inside": "touch_inside"}


def as_said(request: FigureRequest, texts: Sequence[str]) -> FigureRequest:
    """Two circles the question says touch (externally, internally): so marked in ``parts``,
    their centres the radii's sum (or difference) apart, drawn unlabelled. Two circles it
    says neither of, with no distance and no common chord, draw nothing: they may cross,
    touch or lie apart."""
    if request.kind != "circle" or not (reads_two(request) or len(_radii(request)) == 2):
        return request
    words = " ".join(texts).lower()
    found = [TOUCHING[w] for w, rule in (("outside", _OUTSIDE), ("inside", _INSIDE))
             if rule.search(words)]  # fmt: skip
    if len(found) != 1:
        return request
    # Two radii of circles that touch are two circles, never a ring about one centre.
    shape = request.shape if request.shape in SHAPES else "two_circles"
    return request.model_copy(update={"shape": shape, "parts": [*request.parts, found[0]]})


def reads_two(request: FigureRequest) -> bool:
    """The reading is two circles: the read names them, or it gives two different radii and
    a distance between centres (one circle has one radius; two about one centre, a ring,
    have no distance between them)."""
    if request.shape in SHAPES:
        return True
    radii = {round(r, 9) for r, _, _ in _radii(request)}
    return len(radii) == 2 and request.first("distance") is not None


def _radii(request: FigureRequest) -> list[tuple[float, str, float]]:
    """Each stated size: (radius, "radius" or "diameter", the value as stated)."""
    found: list[tuple[float, str, float]] = []
    for m in request.measures:
        if m.what == "radius":
            found.append((m.value, "radius", m.value))
        elif m.what == "diameter":
            found.append((m.value / 2, "diameter", m.value))
    return found


def _centres_apart(
    request: FigureRequest, r1: float, r2: float, chord: float | None, gap: float | None
) -> float | None:
    """The distance between the centres: as stated, as the circles touch, or from the common
    chord (the centres on either side of it, as a textbook draws them); None when the values
    cannot hold or leave it open."""
    touching = r1 + r2 if request.has_part(TOUCHING["outside"]) else None
    if request.has_part(TOUCHING["inside"]):
        touching = abs(r1 - r2)
    if touching is not None:
        holds = chord is None and (gap is None or close(gap, touching))
        return touching if holds else None
    if chord is not None and chord / 2 >= min(r1, r2) - _TOLERANCE:
        return None
    if chord is None:
        return gap
    half = chord / 2
    near, far = math.sqrt(r1 * r1 - half * half), math.sqrt(r2 * r2 - half * half)
    if gap is None:
        return near + far
    return gap if close(gap, near + far) or close(gap, abs(near - far)) else None


def build_two_circles(request: FigureRequest) -> FigureSpec | None:
    if any(m.what not in _ALLOWED for m in request.measures) or len(request.given("distance")) > 1:
        return None
    sizes = _radii(request)
    if len(sizes) == 1 and request.shape in SHAPES:
        sizes = [sizes[0], (sizes[0][0], sizes[0][1], 0.0)]  # equal circles, stated once
    if len(sizes) != 2:
        return None
    (r1, what1, value1), (r2, what2, value2) = sizes
    chord, gap = request.first("chord"), request.first("distance")
    d = _centres_apart(request, r1, r2, chord, gap)
    if d is None or d <= _TOLERANCE:
        return None
    crosses = abs(r1 - r2) + _TOLERANCE < d < r1 + r2 - _TOLERANCE
    if chord is not None and not crosses:
        return None
    unit = request.unit
    drawing = Drawing("two_circles")
    first = drawing.point((0.0, 0.0), dot=True)
    second = drawing.point((d, 0.0), dot=True)
    drawing.arc(first, r1)
    drawing.arc(second, r2)
    # Where the common chord crosses the centres' line, measured from the first centre.
    x = (d * d + r1 * r1 - r2 * r2) / (2 * d)
    share = 0.75 if x / d < 0.5 else 0.25  # the distance's label clear of the chord
    gap_label = length_label(gap, unit) if gap is not None else None
    drawing.line(first, second, gap_label, dashed=True, label_at=share if crosses else 0.5)
    if crosses:
        h = math.sqrt(max(0.0, r1 * r1 - x * x))
        top, bottom = drawing.point((x, h)), drawing.point((x, -h))
        drawing.line(top, bottom, length_label(chord, unit) if chord is not None else None)
        middle = drawing.point((x, 0.0))
        drawing.angle(middle, second, top, right=True)
        ends = (top, top)
    else:
        ends = (drawing.point(polar(r1, _UP)), drawing.point(polar(r2, _UP, (d, 0.0))))
        if close(d, r1 + r2) or close(d, abs(r1 - r2)):
            # Where they touch, on the centres' line.
            drawing.point((r1 if close(d, r1 + r2) or r1 > r2 else -r1, 0.0), dot=True)
    for centre, end, r, what, value in (
        (first, ends[0], r1, what1, value1),
        (second, ends[1], r2, what2, value2),
    ):
        _size(drawing, centre, end, r, what, length_label(value, unit) if value else None)
    return drawing.spec()


def _size(drawing: Drawing, centre: str, end: str, r: float, what: str, label: str | None) -> None:
    """A circle's stated size: its radius to ``end``, or its diameter across it, upright."""
    if what == "radius":
        drawing.line(centre, end, label)
        return
    (cx, cy) = drawing.at(centre)
    low, high = drawing.point((cx, cy - r)), drawing.point((cx, cy + r))
    drawing.line(low, high, label, label_at=0.75)
    drawing.line(centre, end)
