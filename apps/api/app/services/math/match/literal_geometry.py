"""Complete literal measurement grammar shared by extraction and direct replies."""

from __future__ import annotations

import math
import re

from app.services.math.match.units import solid_length_unit, strip_geometry_length_units

GEOMETRY_DECIMAL = r"(?:[0-9]{1,12}(?:\.[0-9]{1,12})?|\.[0-9]{1,12})"
RIGHT_TRIANGLE_LEGS = re.compile(rf"legs\s+({GEOMETRY_DECIMAL})\s+and\s+({GEOMETRY_DECIMAL})")
_ANGLE_DRAW = re.compile(
    rf"(?:please )?(?:draw|sketch) (?:a |the )?triangle with angles "
    rf"({GEOMETRY_DECIMAL})\s*,\s*({GEOMETRY_DECIMAL})\s*,\s*({GEOMETRY_DECIMAL})(?: degrees|°)?"
)


def literal_triangle_angles_draw(text: str) -> tuple[float, float, float] | None:
    """One complete, valid angle triple requested only as a drawing."""
    if len(text) > 1000:
        return None
    request = " ".join(text.lower().split()).rstrip(".?")
    match = _ANGLE_DRAW.fullmatch(request)
    if match is None:
        return None
    a, b, c = (float(value) for value in match.groups())
    if any(not 0 < angle < 180 for angle in (a, b, c)) or not math.isclose(a + b + c, 180):
        return None
    return a, b, c


def measurement_request(user_text: str) -> tuple[str, str] | None:
    """Keep all text after a short measurement lead-in for the shape matcher."""
    if len(user_text) > 1000:
        return None
    request = " ".join(user_text.lower().split()).rstrip(".?")
    if request.startswith("please "):
        request = request[7:]
    for prefix in ("find ", "calculate ", "compute ", "determine ", "what is ", "what's "):
        if request.startswith(prefix):
            request = request[len(prefix) :]
            break
    if request.startswith("the "):
        request = request[4:]
    quantity, separator, body = request.partition(" of ")
    if separator:
        for article in ("a ", "the "):
            if body.startswith(article):
                body = body[len(article) :]
                break
        return quantity, body

    # Natural school prompts also put the shape first: “a rectangle area
    # with sides 4, 5”.  Normalize that into the same shape body used by the
    # strict direct guards.  Longer names/quantities run first so “surface
    # area” and “right triangle” are never truncated to a shorter phrase.
    for article in ("a ", "the "):
        if request.startswith(article):
            request = request[len(article) :]
            break
    shapes = (
        "rectangular prism",
        "right triangle",
        "square pyramid",
        "circle sector",
        "parallelogram",
        "trapezoid",
        "trapezium",
        "rectangle",
        "triangle",
        "cylinder",
        "sphere",
        "sector",
        "square",
        "circle",
        "cuboid",
        "cube",
        "cone",
    )
    quantities = (
        "total surface area",
        "surface area",
        "circumference",
        "arc length",
        "hypotenuse",
        "perimeter",
        "diagonal",
        "diameter",
        "volume",
        "area",
    )
    for shape in shapes:
        prefix = shape + " "
        if not request.startswith(prefix):
            continue
        remainder = request[len(prefix) :]
        for candidate in quantities:
            quantity_prefix = candidate + " "
            if remainder.startswith(quantity_prefix):
                dimensions = remainder[len(quantity_prefix) :].lstrip()
                return candidate, f"{shape} {dimensions}"
    return None


def literal_hypotenuse_legs(text: str) -> tuple[float, float] | None:
    """A whole hypotenuse request, not a reference, multiple, or transformed value."""
    request = measurement_request(text)
    if request is None or request[0] != "hypotenuse":
        return None
    shape = "right triangle "
    if not request[1].startswith(shape):
        return None
    dimensions = request[1][len(shape) :]
    if dimensions.startswith("with "):
        dimensions = dimensions[5:]
    if solid_length_unit(dimensions) is None:
        return None
    match = RIGHT_TRIANGLE_LEGS.fullmatch(strip_geometry_length_units(dimensions).strip())
    if match is None:
        return None
    base, height = (float(value) for value in match.groups())
    if not (0 < base <= 1_000_000 and 0 < height <= 1_000_000):
        return None
    return base, height
