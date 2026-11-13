"""A polygon by its name: the builder for its shape, its letters placed where the
question's named values put them. A circle drawn around or inside one asks for it here."""

from __future__ import annotations

from collections.abc import Callable

from app.modules.math.figure import quads, triangles
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


def build_polygon(request: FigureRequest) -> FigureSpec | None:
    shape = request.shape
    if shape in triangles.TRIANGLES:
        spec = triangles.build_triangle(request)
    elif shape in _POLYGONS:
        spec = _POLYGONS[shape](request)
    elif shape.startswith("regular") or shape in quads.POLYGON_SIDES:
        spec = quads.build_regular_polygon(request)
    else:
        return None
    return None if spec is None else lettered(spec, request)
