"""A polygon by its name: the builder for its shape, its letters placed where the
question's named values put them. A circle drawn around or inside one asks for it here, and
so do the figures built on a polygon: a right triangle in its scene, similar triangles,
shadows, a shape with a second one joined to it, an exterior angle."""

from __future__ import annotations

from collections.abc import Callable

from app.modules.math.figure import (
    angle_terms,
    composite,
    exterior,
    heights,
    quadrilateral,
    quads,
    similar,
    triangles,
)
from app.modules.math.figure.lettering import lettered
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec

_POLYGONS: dict[str, Callable[[FigureRequest], FigureSpec | None]] = {
    "square": quads.build_square,
    "rectangle": quads.build_rectangle,
    "parallelogram": quads.build_parallelogram,
    "rhombus": quads.build_rhombus,
    "trapezium": quads.build_trapezium,
    "trapezoid": quads.build_trapezium,
    "isosceles_trapezium": quads.build_trapezium,
    "isosceles_trapezoid": quads.build_trapezium,
    "kite": quads.build_kite,
}


# Figures that letter their own corners where the question's values put them: a scene of
# heights and distances, two similar triangles, shadows, a shape made of two, a triangle's
# exterior angle, a quadrilateral drawn by its angles.
_PLACED: dict[str, Callable[[FigureRequest], FigureSpec | None]] = {
    **dict.fromkeys(heights.SCENES, heights.build_scene),
    "similar_triangles": similar.build_similar,
    "shadows": similar.build_shadows,
    **dict.fromkeys(quadrilateral.SHAPES, quadrilateral.build_quadrilateral),
}


def build_polygon(request: FigureRequest) -> FigureSpec | None:
    shape = request.shape
    if request.given("shadow"):
        return similar.build_shadows(request)
    if request.attached:
        return composite.build_composite(request)
    if shape in _PLACED:
        return _PLACED[shape](request)
    if shape in triangles.TRIANGLES and any(m.what in heights.ROLES for m in request.measures):
        # A right triangle read by a scene's roles (a wire's length, a distance along the
        # ground): the scene's triangle, upright.
        return heights.build_scene(heights.as_scene(request))
    if request.given("exterior_angle") and shape in triangles.TRIANGLES:
        return exterior.build_exterior(request)
    if request.angle_terms and shape in triangles.TRIANGLES:
        return angle_terms.build_lettered_triangle(request)
    if request.angle_terms:
        return None
    if shape in triangles.TRIANGLES:
        spec = triangles.build_triangle(request)
    elif shape in _POLYGONS:
        spec = _POLYGONS[shape](request)
    elif shape.startswith("regular") or shape in quads.POLYGON_SIDES:
        spec = quads.build_regular_polygon(request)
    else:
        return None
    return None if spec is None else lettered(spec, request)
