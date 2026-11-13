"""The net of a solid: its faces unfolded flat, each true to the sizes the question states.

A box unfolds into a cross, a triangular prism into three rectangles with its two
triangles, a cylinder into a rectangle and two circles, a square pyramid into a square with
four triangles, a cone into a sector and a circle.
"""

from __future__ import annotations

import math

from app.modules.math.figure.drawing import Drawing, Point, length_label, polar
from app.modules.math.figure.request import FigureRequest
from app.modules.math.figure.solids import prism_triangle
from app.modules.math.schemas.figure import FigureSpec

_EDGE, _LENGTH, _WIDTH, _HEIGHT, _RADIUS = 4.0, 6.0, 3.0, 4.0, 2.0


def _rect(drawing: Drawing, x: float, y: float, w: float, h: float) -> None:
    corners: list[Point] = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    for i, corner in enumerate(corners):
        drawing.edge(corner, corners[(i + 1) % 4])
    drawing.faces.append([drawing.corner(corner) for corner in corners])


def _label(drawing: Drawing, a: Point, b: Point, value: float | None, unit: str) -> None:
    if value is not None:
        drawing.edge(a, b, length_label(value, unit))


def _radius(request: FigureRequest) -> float | None:
    diameter = request.first("diameter")
    return request.first("radius") or (diameter / 2 if diameter is not None else None)


def _box_net(request: FigureRequest) -> FigureSpec | None:
    cube = request.shape == "cube"
    edge = request.first("edge", "side", "length") if cube else None
    length = edge if cube else request.first("length", "base")
    width = edge if cube else request.first("width")
    height = edge if cube else request.first("height")
    long, w, h = length or _LENGTH, width or _WIDTH, height or _HEIGHT
    if cube:
        long = w = h = edge or _EDGE
    drawing = Drawing("cube_net" if cube else "cuboid_net")
    # The middle row: left side, front, right side, back; the top and bottom on the front.
    x = 0.0
    for size in (w, long, w, long):
        _rect(drawing, x, 0.0, size, h)
        x += size
    _rect(drawing, w, h, long, w)
    _rect(drawing, w, -w, long, w)
    unit = request.unit
    _label(drawing, (w, -w), (w + long, -w), length, unit)
    if not cube:
        _label(drawing, (0.0, 0.0), (0.0, h), height, unit)
        _label(drawing, (w + long, h), (w + long, h + w), width, unit)
    return drawing.spec()


def _prism_net(request: FigureRequest) -> FigureSpec | None:
    end = prism_triangle(request)
    if end is None:
        return None
    (a, b, c), _, stated = end
    length = request.first("length") or (request.first("height") if stated else None)
    depth = length or _LENGTH
    drawing = Drawing("triangular_prism_net")
    x = 0.0
    for size in (a, c, b):
        _rect(drawing, x, 0.0, size, depth)
        x += size
    # The two end triangles on the middle rectangle's long sides.
    apex_x = (c * c + a * a - b * b) / (2 * c)
    rise = math.sqrt(max(0.0, a * a - apex_x * apex_x))
    for y, sign in ((depth, 1.0), (0.0, -1.0)):
        apex = (a + apex_x, y + sign * rise)
        drawing.edge((a, y), apex)
        drawing.edge((a + c, y), apex)
    unit = request.unit
    if stated:
        _label(drawing, (a, depth), (a + c, depth), c, unit)
        _label(drawing, (0.0, 0.0), (a, 0.0), a, unit)
        _label(drawing, (a + c, 0.0), (a + c + b, 0.0), b, unit)
    _label(drawing, (0.0, 0.0), (0.0, depth), length, unit)
    return drawing.spec()


def _cylinder_net(request: FigureRequest) -> FigureSpec | None:
    radius = _radius(request)
    height = request.first("height", "length")
    r, h = radius or _RADIUS, height or _HEIGHT
    around = 2 * math.pi * r
    drawing = Drawing("cylinder_net")
    _rect(drawing, 0.0, 0.0, around, h)
    for y in (h + r, -r):
        centre = drawing.point((around / 2, y), dot=True)
        drawing.arc(centre, r)
        if radius is not None and y > 0:
            edge = drawing.point((around / 2 + r, y))
            drawing.line(centre, edge, length_label(radius, request.unit))
    _label(drawing, (around, 0.0), (around, h), height, request.unit)
    return drawing.spec()


def _pyramid_net(request: FigureRequest) -> FigureSpec | None:
    base = request.first("base", "side", "edge", "length")
    height = request.first("height")
    slant = request.first("slant_height")
    a = base or _EDGE
    if slant is None:
        slant_size = math.hypot(height or _HEIGHT, a / 2)
    else:
        slant_size = slant
    if slant_size <= a / 2:
        return None
    drawing = Drawing("square_pyramid_net")
    _rect(drawing, 0.0, 0.0, a, a)
    tips = [
        (a / 2, -slant_size),
        (a + slant_size, a / 2),
        (a / 2, a + slant_size),
        (-slant_size, a / 2),
    ]
    sides = [((0.0, 0.0), (a, 0.0)), ((a, 0.0), (a, a)), ((a, a), (0.0, a)), ((0.0, a), (0.0, 0.0))]
    for tip, (p, q) in zip(tips, sides, strict=True):
        drawing.edge(p, tip)
        drawing.edge(q, tip)
    _label(drawing, (0.0, 0.0), (a, 0.0), base, request.unit)
    if slant is not None:
        middle = drawing.corner((a / 2, a))
        drawing.line(
            middle, drawing.corner(tips[2]), length_label(slant, request.unit), dashed=True
        )
    return drawing.spec()


def _cone_net(request: FigureRequest) -> FigureSpec | None:
    radius = _radius(request)
    height = request.first("height")
    slant = request.first("slant_height")
    r = radius or _RADIUS
    slant_size = slant or math.hypot(height or _HEIGHT, r)
    if slant_size <= r:
        return None
    sweep = 360.0 * r / slant_size
    start = 270.0 - sweep / 2
    drawing = Drawing("cone_net")
    apex = drawing.point((0.0, 0.0))
    drawing.arc(apex, slant_size, start=start, end=start + sweep)
    first = drawing.point(polar(slant_size, start))
    last = drawing.point(polar(slant_size, start + sweep))
    drawing.line(apex, first, length_label(slant, request.unit) if slant is not None else None)
    drawing.line(apex, last)
    centre = drawing.point((0.0, -slant_size - r), dot=True)
    drawing.arc(centre, r)
    if radius is not None:
        edge = drawing.point((r, -slant_size - r))
        drawing.line(centre, edge, length_label(radius, request.unit))
    return drawing.spec()


def build_net(request: FigureRequest) -> FigureSpec | None:
    shape = request.shape
    if shape in {"cube", "cuboid", "box", "rectangular_prism", "rectangular_box"}:
        return _box_net(request)
    if shape in {"triangular_prism", "prism", "right_triangular_prism"}:
        return _prism_net(request)
    if shape == "cylinder":
        return _cylinder_net(request)
    if shape in {"square_pyramid", "pyramid", "square_based_pyramid"}:
        return _pyramid_net(request)
    if shape == "cone":
        return _cone_net(request)
    return None
