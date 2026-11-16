"""Solids drawn as a textbook draws them, from the sizes a question states.

A box, a prism or a pyramid is drawn in the one projection every solid figure keeps
(``projection``): seen from a little above, the edges hidden behind the solid dashed. A
cylinder, a cone and a sphere are drawn with ellipses, their back halves dashed. Only stated
sizes are labelled; a size left open is drawn in proportion. The round solids' drawers
take their sizes and labels (``cylinder_drawing``, ``cone_drawing``, ``sphere_drawing``), so a
word problem's solid (``math.drawing``) is drawn by the same code.
"""

from __future__ import annotations

import math

from app.modules.math.figure.drawing import Drawing, length_label
from app.modules.math.figure.projection import ELLIPSE, TEXTBOOK, box_drawing, draw_polyhedron
from app.modules.math.figure.request import FigureRequest
from app.modules.math.figure.triangles import determined
from app.modules.math.schemas.figure import FigureSpec

# Sizes for what a question leaves open.
_EDGE, _LENGTH, _WIDTH, _HEIGHT, _RADIUS = 4.0, 6.0, 3.0, 4.0, 2.0


def box_sizes(request: FigureRequest) -> tuple[float | None, ...] | None:
    """A box's stated length, width and height: a cube's one edge for all three; a cuboid's
    by name, or three sizes given in a row ("8 cm by 3 cm by 7 cm"). Sizes some named and
    some not ("length 8 and a side 3") leave which is which open, and give None."""
    if request.shape == "cube":
        edge = request.first("edge", "side", "length")
        return (edge, edge, edge)
    unnamed = [m.value for m in request.measures if m.what in {"side", "edge"}]
    named = [request.first("length", "base"), request.first("width"), request.first("height")]
    if unnamed:
        return tuple(unnamed) if len(unnamed) == 3 and named == [None, None, None] else None
    return tuple(named)


def _box(request: FigureRequest) -> FigureSpec | None:
    cube = request.shape == "cube"
    sizes = box_sizes(request)
    if sizes is None:
        return None
    length, width, height = sizes
    edge = length or _EDGE
    long, w, h = (
        (edge, edge, edge) if cube else (length or _LENGTH, width or _WIDTH, height or _HEIGHT)
    )
    unit = request.unit
    # Its width going back (x), its length across (y), its height up (z).
    labels: dict[int, str] = {}
    if length is not None:
        labels[1] = length_label(length, unit)
    if height is not None and not cube:
        labels[2] = length_label(height, unit)
    if width is not None and not cube:
        labels[0] = length_label(width, unit)
    return box_drawing("cube" if cube else "cuboid", (w, long, h), labels).spec()


_END_ROLES = frozenset({"side", "leg", "hypotenuse", "base", "equal_side", "angle"})
# A prism's end edges by the end triangle's side: side i is opposite corner i.
_END_EDGES = {2: (0, 1), 1: (0, 2), 0: (1, 2)}


def prism_end(
    request: FigureRequest,
) -> tuple[list[float], list[tuple[float, float]], dict[int, str], float | None] | None:
    """A prism's end triangle as the question states it: its sides, corners, the labels of
    the sides it states (by the side), and the prism's own length. The end is drawn only
    when its stated values decide it ("sides 5 and 6" of an isosceles end leave it open);
    "height" is the end's when the prism's length is given too, else the prism's."""
    length = request.first("length")
    height_is_end = length is not None
    if length is None:
        length = request.first("height")
    measures = [
        m
        for m in request.measures
        if m.what in _END_ROLES or (m.what == "height" and height_is_end)
    ]
    if not measures:
        a, b, c = 3.0, 4.0, 5.0
        x = (c * c + a * a - b * b) / (2 * c)
        return [b, a, c], [(0.0, 0.0), (c, 0.0), (x, math.sqrt(a * a - x * x))], {}, length
    whats = {m.what for m in measures}
    shape = (
        "right_triangle"
        if whats & {"leg", "hypotenuse"}
        else "isosceles_triangle"
        if "equal_side" in whats
        else "triangle"
    )
    end = request.model_copy(update={"kind": "polygon", "shape": shape, "measures": measures})
    found = determined(end)
    if found is None:
        return None
    placed, sides = found
    t = placed.triangle
    x = (sides[2] ** 2 + sides[1] ** 2 - sides[0] ** 2) / (2 * sides[2])
    corners = [(0.0, 0.0), (sides[2], 0.0), (x, math.sqrt(max(0.0, sides[1] ** 2 - x * x)))]
    labels = {i: length_label(t.stated_sides[i], request.unit) for i in t.side_labels}
    return sides, corners, labels, length


def _prism(request: FigureRequest) -> FigureSpec | None:
    end = prism_end(request)
    if end is None:
        return None
    _, corners, end_labels, length = end
    depth = length or _LENGTH
    # Its front end upright toward the reader, its length going back along x.
    vertices = [(depth, x, y) for x, y in corners] + [(0.0, x, y) for x, y in corners]
    faces = [[0, 1, 2], [3, 4, 5], [0, 1, 4, 3], [1, 2, 5, 4], [2, 0, 3, 5]]
    labels = {_END_EDGES[i]: label for i, label in end_labels.items()}
    if length is not None:
        labels[(1, 4)] = length_label(length, request.unit)
    return draw_polyhedron("triangular_prism", vertices, faces, labels).spec()


def pyramid_height(request: FigureRequest) -> tuple[float | None, float] | None:
    """A square pyramid's stated base edge and its height, from a height, a slant height or
    a lateral edge ("edge" beside a base); any two of those must agree."""
    base = request.first("base", "side")
    edge = request.first("edge")
    if base is None:
        base, edge = edge, None
    a = base or _EDGE
    heights: list[float] = []
    if (height := request.first("height")) is not None:
        heights.append(height)
    if (slant := request.first("slant_height")) is not None:
        if slant <= a / 2:
            return None
        heights.append(math.sqrt(slant * slant - a * a / 4))
    if edge is not None:
        if edge <= a / math.sqrt(2):
            return None
        heights.append(math.sqrt(edge * edge - a * a / 2))
    if any(abs(h - heights[0]) > 1e-4 * heights[0] for h in heights):
        return None
    return base, heights[0] if heights else _HEIGHT


def _pyramid(request: FigureRequest) -> FigureSpec | None:
    found = pyramid_height(request)
    if found is None:
        return None
    base, h = found
    a = base or _EDGE
    vertices = [(0.0, 0.0, 0.0), (a, 0.0, 0.0), (a, a, 0.0), (0.0, a, 0.0), (a / 2, a / 2, h)]
    faces = [[0, 1, 2, 3], [0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]]
    unit = request.unit
    labels = {(0, 1): length_label(base, unit)} if base is not None else {}
    lateral = request.first("edge") if request.first("base", "side") is not None else None
    if lateral is not None:
        labels[(1, 4)] = length_label(lateral, unit)
    drawing = draw_polyhedron("square_pyramid", vertices, faces, labels)
    if (height := request.first("height")) is not None:
        centre = drawing.point(TEXTBOOK((a / 2, a / 2, 0.0)), dot=True)
        drawing.line(drawing.points[4].name, centre, length_label(height, unit), dashed=True)
    if (slant := request.first("slant_height")) is not None:
        # Down the face in sight, to its base edge's middle.
        middle = drawing.point(TEXTBOOK((a, a / 2, 0.0)))
        drawing.line(drawing.points[4].name, middle, length_label(slant, unit))
    return drawing.spec()


def round_base(drawing: Drawing, centre: str, r: float) -> None:
    """A circle lying flat: its front half drawn, its back half dashed."""
    drawing.arc(centre, r, r * ELLIPSE, start=180, end=360)
    drawing.arc(centre, r, r * ELLIPSE, start=0, end=180, dashed=True)


def round_size(request: FigureRequest) -> tuple[float | None, str | None, bool]:
    """A round solid's radius, the label its stated size is drawn with, and whether that
    size is a diameter (drawn across the circle, never on a radius)."""
    radius = request.first("radius")
    diameter = request.first("diameter")
    if radius is not None:
        return radius, length_label(radius, request.unit), False
    if diameter is not None:
        return diameter / 2, length_label(diameter, request.unit), True
    return None, None, False


def cylinder_drawing(
    r: float,
    h: float,
    *,
    height: str | None = None,
    radius: str | None = None,
    diameter: str | None = None,
    shape: str = "cylinder",
) -> Drawing:
    """An upright cylinder: its height labelled up its right side, its radius from the top's
    centre (or its diameter across the top)."""
    drawing = Drawing(shape)
    bottom = drawing.point((0.0, 0.0))
    top = drawing.point((0.0, h), dot=radius is not None or diameter is not None)
    round_base(drawing, bottom, r)
    drawing.arc(top, r, r * ELLIPSE)
    left_low, left_high = drawing.point((-r, 0.0)), drawing.point((-r, h))
    right_low, right_high = drawing.point((r, 0.0)), drawing.point((r, h))
    drawing.line(left_low, left_high)
    drawing.line(right_low, right_high, height)
    if diameter is not None:
        drawing.line(left_high, right_high, diameter)
    elif radius is not None:
        drawing.line(top, right_high, radius)
    return drawing


def _cylinder(request: FigureRequest) -> FigureSpec | None:
    radius, label, diameter_shown = round_size(request)
    height = request.first("height", "length")
    r, h = radius or _RADIUS, height or _HEIGHT * 1.2
    unit = request.unit
    return cylinder_drawing(
        r,
        h,
        height=length_label(height, unit) if height is not None else None,
        radius=label if not diameter_shown else None,
        diameter=label if diameter_shown else None,
    ).spec()


def cone_drawing(
    r: float,
    h: float,
    *,
    height: str | None = None,
    radius: str | None = None,
    diameter: str | None = None,
    slant: str | None = None,
) -> Drawing:
    """A cone on its base: its slant labelled on the right, its height dashed down the middle
    to the base's centre, its radius (or diameter) dashed across the base."""
    drawing = Drawing("cone")
    centre = drawing.point((0.0, 0.0), dot=True)
    apex = drawing.point((0.0, h))
    left, right = drawing.point((-r, 0.0)), drawing.point((r, 0.0))
    round_base(drawing, centre, r)
    drawing.line(left, apex)
    drawing.line(right, apex, slant)
    drawing.line(apex, centre, height, dashed=True)
    if diameter is not None:
        drawing.line(left, right, diameter, dashed=True, label_at=0.75)
    else:
        drawing.line(centre, right, radius, dashed=True)
    drawing.angle(centre, right, apex, right=True)
    return drawing


def _cone(request: FigureRequest) -> FigureSpec | None:
    radius, label, across = round_size(request)
    height = request.first("height")
    slant = request.first("slant_height")
    r = radius or _RADIUS
    if height is None and slant is not None:
        if slant <= r:
            return None
        h = math.sqrt(slant * slant - r * r)
    else:
        h = height or _HEIGHT
    if height is not None and slant is not None and abs(math.hypot(r, h) - slant) > 1e-4 * slant:
        return None
    unit = request.unit
    return cone_drawing(
        r,
        h,
        height=length_label(height, unit) if height is not None else None,
        radius=label if not across else None,
        diameter=label if across else None,
        slant=length_label(slant, unit) if slant is not None else None,
    ).spec()


def sphere_drawing(
    r: float, *, radius: str | None = None, diameter: str | None = None, half: bool = False
) -> Drawing:
    """A sphere (or a hemisphere on its flat face) with its equator, its radius labelled from
    the centre (or its diameter across)."""
    drawing = Drawing("hemisphere" if half else "sphere")
    centre = drawing.point((0.0, 0.0), dot=True)
    if half:
        drawing.arc(centre, r, start=180, end=360)
        drawing.arc(centre, r, r * ELLIPSE)
    else:
        drawing.arc(centre, r)
        round_base(drawing, centre, r)
    edge = drawing.point((r, 0.0))
    if diameter is not None:
        drawing.line(drawing.point((-r, 0.0)), edge, diameter, dashed=True, label_at=0.75)
    else:
        drawing.line(centre, edge, radius)
    return drawing


def _sphere(request: FigureRequest, *, half: bool = False) -> FigureSpec | None:
    radius, label, across = round_size(request)
    return sphere_drawing(
        radius or _RADIUS,
        radius=label if not across else None,
        diameter=label if across else None,
        half=half,
    ).spec()


_BOXES = frozenset({"cube", "cuboid", "box", "rectangular_prism", "rectangular_box"})
_PRISMS = frozenset({"triangular_prism", "prism", "right_triangular_prism"})
_PYRAMIDS = frozenset({"square_pyramid", "pyramid", "square_based_pyramid"})


def build_solid(request: FigureRequest) -> FigureSpec | None:
    shape = request.shape
    if shape in _BOXES:
        return _box(request)
    if shape in _PRISMS:
        return _prism(request)
    if shape in _PYRAMIDS:
        return _pyramid(request)
    if shape == "cylinder":
        return _cylinder(request)
    if shape == "cone":
        return _cone(request)
    if shape in {"sphere", "hemisphere"}:
        return _sphere(request, half=shape == "hemisphere")
    return None
