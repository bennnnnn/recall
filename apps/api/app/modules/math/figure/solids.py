"""Solids drawn as a textbook draws them, from the sizes a question states.

A box, a prism or a pyramid is drawn in oblique projection: the front face true to size,
the depth going back up and to the right at half scale, and the edges hidden behind the
solid dashed (an edge is hidden when no face that meets it faces the reader). A cylinder,
a cone and a sphere are drawn with ellipses, their back halves dashed. Only stated sizes
are labelled; a size left open is drawn in proportion.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.modules.math.figure.drawing import Drawing, length_label
from app.modules.math.figure.request import FigureRequest
from app.modules.math.figure.triangles import determined
from app.modules.math.schemas.figure import FigureSpec

Point3 = tuple[float, float, float]
# The receding axis: half scale, 35° up from the horizontal.
_DEPTH_SCALE = 0.5
_DEPTH_TURN = math.radians(35)
# A circle seen from a little above: its ellipse's height against its width.
_ELLIPSE = 0.3
# Sizes for what a question leaves open.
_EDGE, _LENGTH, _WIDTH, _HEIGHT, _RADIUS = 4.0, 6.0, 3.0, 4.0, 2.0
_TOLERANCE = 1e-9
_DEPTH_X = _DEPTH_SCALE * math.cos(_DEPTH_TURN)
_DEPTH_Y = _DEPTH_SCALE * math.sin(_DEPTH_TURN)


def project(point: Point3) -> tuple[float, float]:
    x, y, z = point
    return (x + z * _DEPTH_X, y + z * _DEPTH_Y)


def _normal(points: Sequence[Point3]) -> Point3:
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = points[0], points[1], points[2]
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    return (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)


def _facing(vertices: list[Point3], face: list[int]) -> bool:
    """The face's outward side looks toward the reader (who looks along +z, receding)."""
    points = [vertices[i] for i in face]
    nx, ny, nz = _normal(points)
    middle = [sum(p[k] for p in vertices) / len(vertices) for k in range(3)]
    centre = [sum(p[k] for p in points) / len(points) for k in range(3)]
    if sum(n * (c - m) for n, c, m in zip((nx, ny, nz), centre, middle, strict=True)) < 0:
        nx, ny, nz = -nx, -ny, -nz
    # The view direction: the 3D direction the projection flattens to a point.
    return nx * -_DEPTH_X + ny * -_DEPTH_Y + nz * 1.0 < -_TOLERANCE


def draw_polyhedron(
    shape: str,
    vertices: list[Point3],
    faces: list[list[int]],
    labels: dict[tuple[int, int], str],
) -> Drawing:
    drawing = Drawing(shape)
    names = [drawing.point(project(vertex)) for vertex in vertices]
    shown = [_facing(vertices, face) for face in faces]
    edges: dict[tuple[int, int], bool] = {}
    for face, visible in zip(faces, shown, strict=True):
        for i, a in enumerate(face):
            b = face[(i + 1) % len(face)]
            key = (min(a, b), max(a, b))
            edges[key] = edges.get(key, False) or visible
    for (a, b), visible in edges.items():
        drawing.line(names[a], names[b], labels.get((a, b)), dashed=not visible)
    # The faces the reader sees, lightly filled; a side's label sits outside the first
    # of them that holds it.
    drawing.faces = [
        [names[i] for i in face] for face, visible in zip(faces, shown, strict=True) if visible
    ]
    return drawing


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
    vertices = [
        (0, 0, 0), (long, 0, 0), (long, h, 0), (0, h, 0),
        (0, 0, w), (long, 0, w), (long, h, w), (0, h, w),
    ]  # fmt: skip
    faces = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [3, 2, 6, 7], [0, 3, 7, 4], [1, 2, 6, 5]]
    unit = request.unit
    labels: dict[tuple[int, int], str] = {}
    if length is not None:
        labels[(0, 1)] = length_label(length, unit)
    if height is not None and not cube:
        labels[(1, 2)] = length_label(height, unit)
    if width is not None and not cube:
        labels[(1, 5)] = length_label(width, unit)
    return draw_polyhedron(
        "cube" if cube else "cuboid", [_f(v) for v in vertices], faces, labels
    ).spec()


def _f(point: tuple[float, ...]) -> Point3:
    return (float(point[0]), float(point[1]), float(point[2]))


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
    vertices = [(x, y, 0.0) for x, y in corners] + [(x, y, depth) for x, y in corners]
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
    vertices = [(0.0, 0.0, 0.0), (a, 0.0, 0.0), (a, 0.0, a), (0.0, 0.0, a), (a / 2, h, a / 2)]
    faces = [[0, 1, 2, 3], [0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]]
    unit = request.unit
    labels = {(0, 1): length_label(base, unit)} if base is not None else {}
    lateral = request.first("edge") if request.first("base", "side") is not None else None
    if lateral is not None:
        labels[(1, 4)] = length_label(lateral, unit)
    drawing = draw_polyhedron("square_pyramid", vertices, faces, labels)
    if (height := request.first("height")) is not None:
        centre = drawing.point(project((a / 2, 0.0, a / 2)), dot=True)
        drawing.line(drawing.points[4].name, centre, length_label(height, unit), dashed=True)
    if (slant := request.first("slant_height")) is not None:
        middle = drawing.point(project((a / 2, 0.0, 0.0)))
        drawing.line(drawing.points[4].name, middle, length_label(slant, unit), dashed=True)
    return drawing.spec()


def _round_base(drawing: Drawing, centre: str, r: float) -> None:
    """A circle lying flat: its front half drawn, its back half dashed."""
    drawing.arc(centre, r, r * _ELLIPSE, start=180, end=360)
    drawing.arc(centre, r, r * _ELLIPSE, start=0, end=180, dashed=True)


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


def _cylinder(request: FigureRequest) -> FigureSpec | None:
    radius, label, diameter_shown = round_size(request)
    height = request.first("height", "length")
    r, h = radius or _RADIUS, height or _HEIGHT * 1.2
    drawing = Drawing("cylinder")
    bottom = drawing.point((0.0, 0.0))
    top = drawing.point((0.0, h), dot=radius is not None)
    _round_base(drawing, bottom, r)
    drawing.arc(top, r, r * _ELLIPSE)
    left_low, left_high = drawing.point((-r, 0.0)), drawing.point((-r, h))
    right_low, right_high = drawing.point((r, 0.0)), drawing.point((r, h))
    drawing.line(left_low, left_high)
    unit = request.unit
    drawing.line(right_low, right_high, length_label(height, unit) if height is not None else None)
    if radius is not None:
        start = left_high if diameter_shown else top
        drawing.line(start, right_high, label)
    return drawing.spec()


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
    drawing = Drawing("cone")
    centre = drawing.point((0.0, 0.0), dot=True)
    apex = drawing.point((0.0, h))
    left, right = drawing.point((-r, 0.0)), drawing.point((r, 0.0))
    _round_base(drawing, centre, r)
    unit = request.unit
    drawing.line(left, apex)
    drawing.line(right, apex, length_label(slant, unit) if slant is not None else None)
    drawing.line(
        apex, centre, length_label(height, unit) if height is not None else None, dashed=True
    )
    if across:
        drawing.line(left, right, label, dashed=True, label_at=0.75)
    else:
        drawing.line(centre, right, label, dashed=True)
    drawing.angle(centre, right, apex, right=True)
    return drawing.spec()


def _sphere(request: FigureRequest, *, half: bool = False) -> FigureSpec | None:
    radius, label, across = round_size(request)
    r = radius or _RADIUS
    drawing = Drawing("hemisphere" if half else "sphere")
    centre = drawing.point((0.0, 0.0), dot=True)
    if half:
        drawing.arc(centre, r, start=180, end=360)
        drawing.arc(centre, r, r * _ELLIPSE)
    else:
        drawing.arc(centre, r)
        _round_base(drawing, centre, r)
    edge = drawing.point((r, 0.0))
    if across:
        drawing.line(drawing.point((-r, 0.0)), edge, label, dashed=True, label_at=0.75)
    else:
        drawing.line(centre, edge, label)
    return drawing.spec()


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
