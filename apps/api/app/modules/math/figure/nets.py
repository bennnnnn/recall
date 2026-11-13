"""The net of a solid: its faces unfolded flat, each true to the sizes the question states.

A box unfolds into a cross, a triangular prism into three rectangles with its two
triangles, a cylinder into a rectangle and two circles, a square pyramid into a square with
four triangles, a cone into a sector and a circle.
"""

from __future__ import annotations

import math

from app.modules.math.figure.drawing import Drawing, Point, length_label, polar
from app.modules.math.figure.request import FigureRequest
from app.modules.math.figure.solids import box_sizes, prism_end, pyramid_height, round_size
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


def _box_net(request: FigureRequest) -> FigureSpec | None:
    cube = request.shape == "cube"
    sizes = box_sizes(request)
    if sizes is None:
        return None
    length, width, height = sizes
    edge = length or _EDGE
    long, w, h = (
        (edge, edge, edge) if cube else (length or _LENGTH, width or _WIDTH, height or _HEIGHT)
    )
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
    end = prism_end(request)
    if end is None:
        return None
    (s0, s1, s2), corners, labels, length = end
    depth = length or _LENGTH
    drawing = Drawing("triangular_prism_net")
    # The three side faces in a row, each as wide as the end's side it joins: side 1 (from
    # the first corner to the apex), the base (side 2), then side 0.
    x = 0.0
    for size in (s1, s2, s0):
        _rect(drawing, x, 0.0, size, depth)
        x += size
    # The two end triangles on the middle rectangle's long sides.
    apex_x, rise = corners[2]
    for y, sign in ((depth, 1.0), (0.0, -1.0)):
        apex = (s1 + apex_x, y + sign * rise)
        drawing.edge((s1, y), apex)
        drawing.edge((s1 + s2, y), apex)
    unit = request.unit
    for index, (a, b) in {
        1: ((0.0, 0.0), (s1, 0.0)),
        2: ((s1, depth), (s1 + s2, depth)),
        0: ((s1 + s2, 0.0), (s1 + s2 + s0, 0.0)),
    }.items():
        if index in labels:
            drawing.edge(a, b, labels[index])
    _label(drawing, (0.0, 0.0), (0.0, depth), length, unit)
    return drawing.spec()


def _across(drawing: Drawing, centre: tuple[float, float], r: float, label: str) -> None:
    """A circle's stated size: a diameter drawn across it, or a radius to its edge."""
    drawing.line(
        drawing.point((centre[0] - r, centre[1])), drawing.point((centre[0] + r, centre[1])), label
    )


def _cylinder_net(request: FigureRequest) -> FigureSpec | None:
    radius, label, across = round_size(request)
    height = request.first("height", "length")
    r, h = radius or _RADIUS, height or _HEIGHT
    around = 2 * math.pi * r
    drawing = Drawing("cylinder_net")
    _rect(drawing, 0.0, 0.0, around, h)
    for y in (h + r, -r):
        centre = drawing.point((around / 2, y), dot=True)
        drawing.arc(centre, r)
        if label is not None and y > 0:
            if across:
                _across(drawing, (around / 2, y), r, label)
            else:
                drawing.line(centre, drawing.point((around / 2 + r, y)), label)
    _label(drawing, (around, 0.0), (around, h), height, request.unit)
    return drawing.spec()


def _pyramid_net(request: FigureRequest) -> FigureSpec | None:
    found = pyramid_height(request)
    if found is None:
        return None
    base, height = found
    slant = request.first("slant_height")
    a = base or _EDGE
    slant_size = math.hypot(height, a / 2)
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
    lateral = request.first("edge") if request.first("base", "side") is not None else None
    if lateral is not None:
        drawing.edge((a, 0.0), tips[1], length_label(lateral, request.unit))
    if slant is not None:
        middle = drawing.corner((a / 2, a))
        drawing.line(
            middle, drawing.corner(tips[2]), length_label(slant, request.unit), dashed=True
        )
    return drawing.spec()


def _cone_net(request: FigureRequest) -> FigureSpec | None:
    radius, label, across = round_size(request)
    height = request.first("height")
    slant = request.first("slant_height")
    r = radius or _RADIUS
    if (
        height is not None
        and slant is not None
        and abs(math.hypot(r, height) - slant) > 1e-4 * slant
    ):
        return None  # radius 3, height 4 and slant 6 are no one cone
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
    if label is not None:
        if across:
            _across(drawing, (0.0, -slant_size - r), r, label)
        else:
            drawing.line(centre, drawing.point((r, -slant_size - r)), label)
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
