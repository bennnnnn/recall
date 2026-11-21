"""A part of a circle cut off by its angle at the centre, and two circles about one centre.

A sector (or an arc) is drawn as its two radii and the arc between them, the rest of the
circle dashed, the angle at the centre marked and labelled; a segment adds the chord across
the sector. An annulus is two circles about one centre, each with its stated radius (or
diameter) drawn and labelled. An angle mark shows an angle under 180°, so a larger sector
draws nothing rather than a mark that would say the wrong angle.
"""

from __future__ import annotations

from app.modules.math.figure.circle_frame import DEFAULT_RADIUS, close, letters, start, stated_size
from app.modules.math.figure.drawing import angle_label, polar
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec

# Where an annulus's two radii point: apart, so their labels never meet.
_INNER_TURN, _OUTER_TURN = 135.0, 20.0


def _centre_angle(request: FigureRequest) -> float | None:
    """The angle at the centre: as stated, or an angle the read left unplaced (a sector's
    angle is at its centre)."""
    found = request.first("central_angle")
    if found is not None:
        return found
    angles = [m for m in request.given("angle") if len(m.name) != 1 or m.name == request.center]
    return angles[0].value if len(angles) == 1 else None


def build_sector(request: FigureRequest, *, chord: bool = False) -> FigureSpec | None:
    """The sector (or arc) of the stated radius and angle at the centre; ``chord``: the
    segment between the chord and the arc."""
    holds, size = stated_size(request)
    angle = _centre_angle(request)
    if not holds or angle is None or not 0 < angle <= 180:
        return None
    if request.first("chord", "distance", "tangent", "inscribed_angle") is not None:
        return None
    r = size or DEFAULT_RADIUS
    figure = start(request, "circle_segment" if chord else "circle_sector", r)
    drawing = figure.drawing
    first, last = 90 - angle / 2, 90 + angle / 2
    names = letters(request, 2) or _ends(request)
    a, b = figure.named(polar(r, first), names[0]), figure.named(polar(r, last), names[1])
    drawing.arc(figure.centre, r, start=first, end=last)
    drawing.arc(figure.centre, r, start=last, end=first + 360, dashed=True)
    drawing.line(figure.centre, a, figure.length(request.first("radius")))
    drawing.line(figure.centre, b)
    if chord:
        drawing.line(a, b, dashed=False)
    drawing.angle(figure.centre, a, b, angle_label(angle))
    figure.diameter(request.first("diameter"), 0.0)
    return drawing.spec()


def _ends(request: FigureRequest) -> list[str]:
    """The radii's letters from the angle's name ("AOB"), or none."""
    for measure in request.measures:
        name = measure.name.strip()
        if measure.what in {"angle", "central_angle"} and len(name) == 3 and name.isalpha():
            return [name[0], name[2]]
    return ["", ""]


def build_segment(request: FigureRequest) -> FigureSpec | None:
    return build_sector(request, chord=True)


def build_annulus(request: FigureRequest) -> FigureSpec | None:
    """Two circles about one centre, each stated size drawn on its own circle."""
    sizes: list[tuple[float, str, float]] = []
    for measure in request.measures:
        if measure.what == "radius":
            sizes.append((measure.value, "radius", measure.value))
        elif measure.what == "diameter":
            sizes.append((measure.value / 2, "diameter", measure.value))
        else:
            return None
    radii = sorted({round(r, 9) for r, _, _ in sizes})
    if len(radii) != 2 or len(sizes) != 2 or close(radii[0], radii[1]):
        return None
    sizes.sort()
    inner, outer = radii
    figure = start(request, "annulus", outer)
    drawing = figure.drawing
    drawing.arc(figure.centre, inner)
    drawing.arc(figure.centre, outer)
    for (r, what, value), turn in zip(sizes, (_INNER_TURN, _OUTER_TURN), strict=True):
        if what == "radius":
            # The outer radius's label sits in the ring, clear of the inner circle.
            at = 0.5 if r == inner else 0.5 + 0.5 * inner / outer
            end = drawing.point(polar(r, turn))
            drawing.line(figure.centre, end, figure.length(value), label_at=min(0.9, at))
        else:
            ends = drawing.point(polar(r, turn + 180)), drawing.point(polar(r, turn))
            drawing.line(*ends, figure.length(value), label_at=0.75)
    return drawing.spec()
