"""A frustum of a cone or of a square pyramid, and a regular tetrahedron.

A cone's frustum is drawn as the round solids are (``solids``): two flat circles as
ellipses, the bottom's back half dashed, the top whole, the slanting sides between them.
Its two radii (or diameters) are the ends' (the larger at the bottom), and its height or its
slant height decides the other; both stated must agree. A pyramid's frustum and a
tetrahedron are drawn in the solids' one projection (``projection``), hidden edges dashed,
each stated size on its own edge. Only stated sizes are labelled; one left open is drawn in
proportion.
"""

from __future__ import annotations

import math

from app.modules.math.figure.drawing import Drawing, length_label
from app.modules.math.figure.projection import ELLIPSE, TEXTBOOK, draw_polyhedron
from app.modules.math.figure.request import FigureRequest
from app.modules.math.figure.solids import round_base
from app.modules.math.schemas.figure import FigureSpec

FRUSTUMS = frozenset({"frustum", "cone_frustum", "frustum_of_a_cone", "truncated_cone"})
PYRAMID_FRUSTUMS = frozenset(
    {"square_frustum", "pyramid_frustum", "frustum_of_a_pyramid", "truncated_pyramid"}
)
TETRAHEDRA = frozenset({"tetrahedron", "regular_tetrahedron"})
_TOLERANCE = 1e-4
# What a frustum leaves open: its height against its larger end.
_HEIGHT = 0.9
_EDGE = 4.0


def _height(request: FigureRequest, run: float) -> tuple[float, str | None, str | None] | None:
    """The height, and the labels of the stated height and slant height, from either; the
    slant runs ``run`` across as it rises."""
    unit = request.unit
    height, slant = request.first("height"), request.first("slant_height")
    if slant is not None:
        if slant <= run:
            return None
        rise = math.sqrt(slant * slant - run * run)
        if height is not None and abs(rise - height) > _TOLERANCE * height:
            return None
        height = rise
    if height is None:
        return None
    return (
        height,
        length_label(height, unit) if request.first("height") is not None else None,
        length_label(slant, unit) if slant is not None else None,
    )


_End = tuple[float, str, bool]


def _radii(request: FigureRequest) -> tuple[_End, _End] | None:
    """The ends, larger first: each one's radius, its label, and whether that label is a
    diameter's (drawn across the end, never on a radius)."""
    unit = request.unit
    ends = [(m.value, length_label(m.value, unit), False) for m in request.given("radius")]
    ends += [(m.value / 2, length_label(m.value, unit), True) for m in request.given("diameter")]
    if len(ends) != 2 or abs(ends[0][0] - ends[1][0]) < _TOLERANCE:
        return None
    big, small = sorted(ends, key=lambda end: -end[0])
    return big, small


def build_frustum(request: FigureRequest) -> FigureSpec | None:
    radii = _radii(request)
    if radii is None:
        return None
    (big, big_label, big_across), (small, small_label, small_across) = radii
    found = _height(request, big - small)
    if found is None and request.first("height", "slant_height") is None:
        found = (big * 2 * _HEIGHT, None, None)
    if found is None:
        return None
    h, height_label, slant_label = found
    drawing = Drawing("frustum")
    bottom = drawing.point((0.0, 0.0), dot=not big_across)
    top = drawing.point((0.0, h), dot=not small_across)
    round_base(drawing, bottom, big)
    drawing.arc(top, small, small * ELLIPSE)
    left_low, left_high = drawing.point((-big, 0.0)), drawing.point((-small, h))
    right_low, right_high = drawing.point((big, 0.0)), drawing.point((small, h))
    drawing.line(left_low, left_high)
    drawing.line(right_low, right_high, slant_label)
    if big_across:
        drawing.line(left_low, right_low, big_label, dashed=True, label_at=0.75)
    else:
        drawing.line(bottom, right_low, big_label, dashed=True)
    if small_across:
        drawing.line(left_high, right_high, small_label, label_at=0.75)
    else:
        drawing.line(top, right_high, small_label)
    drawing.line(top, bottom, height_label, dashed=True)
    return drawing.spec()


def build_pyramid_frustum(request: FigureRequest) -> FigureSpec | None:
    """A square pyramid's frustum: its base and top edges, the larger at the bottom."""
    edges = sorted(
        (m.value for m in request.measures if m.what in {"edge", "side", "base"}), reverse=True
    )
    if len(edges) != 2 or edges[0] - edges[1] < _TOLERANCE:
        return None
    a, b = edges
    # A slant height rises up the middle of a face: it runs half the edges' difference.
    found = _height(request, (a - b) / 2)
    if found is None and request.first("height", "slant_height") is None:
        found = (a * _HEIGHT, None, None)
    if found is None:
        return None
    h, height_label, slant_label = found
    inset = (a - b) / 2
    vertices = [(0.0, 0.0, 0.0), (a, 0.0, 0.0), (a, a, 0.0), (0.0, a, 0.0)]
    vertices += [(inset, inset, h), (a - inset, inset, h), (a - inset, a - inset, h)]
    vertices += [(inset, a - inset, h)]
    faces = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    unit = request.unit
    labels = {(0, 1): length_label(a, unit), (4, 5): length_label(b, unit)}
    drawing = draw_polyhedron("square_frustum", vertices, faces, labels)
    if height_label is not None:
        low = drawing.point(TEXTBOOK((a / 2, a / 2, 0.0)), dot=True)
        high = drawing.point(TEXTBOOK((a / 2, a / 2, h)), dot=True)
        drawing.line(high, low, height_label, dashed=True)
    if slant_label is not None:
        # Up the face in sight, from its base edge's middle to its top edge's.
        low = drawing.point(TEXTBOOK((a, a / 2, 0.0)))
        high = drawing.point(TEXTBOOK((a - inset, a / 2, h)))
        drawing.line(low, high, slant_label)
    return drawing.spec()


def build_tetrahedron(request: FigureRequest) -> FigureSpec | None:
    """A regular tetrahedron on one face: every edge the stated edge."""
    edges = [m.value for m in request.measures if m.what in {"edge", "side", "length"}]
    if len(edges) != len(request.measures) or len(set(edges)) > 1:
        return None
    a = edges[0] if edges else _EDGE
    vertices = [
        (0.0, 0.0, 0.0),
        (a, 0.0, 0.0),
        (a / 2, a * math.sqrt(3) / 2, 0.0),
        (a / 2, a * math.sqrt(3) / 6, a * math.sqrt(2 / 3)),
    ]
    faces = [[0, 1, 2], [0, 1, 3], [1, 2, 3], [2, 0, 3]]
    drawing = draw_polyhedron("tetrahedron", vertices, faces, {})
    if edges:
        # Every edge is the stated one: it is labelled on an edge in sight.
        seen = next(segment for segment in drawing.segments if not segment.dashed)
        seen.label = length_label(a, request.unit)
    return drawing.spec()
