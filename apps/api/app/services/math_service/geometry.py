"""2D/3D geometry measurements — no SymPy parse."""

from __future__ import annotations

import math

from app.models.math_schemas import (
    CircleGeometryInput,
    CircleGeometryResult,
    ParallelogramInput,
    ParallelogramResult,
    RectangleGeometryInput,
    RectangleGeometryResult,
    RightTriangleGeometryInput,
    RightTriangleGeometryResult,
    SectorInput,
    SectorResult,
    SolidGeometryInput,
    SolidGeometryResult,
    SquareGeometryInput,
    SquareGeometryResult,
    TrapezoidInput,
    TrapezoidResult,
    TriangleGeometryInput,
    TriangleGeometryResult,
    TriangleSidesInput,
    TriangleSidesResult,
)
from app.services.math_service.parse import MathServiceError


def rectangle_geometry(data: RectangleGeometryInput) -> RectangleGeometryResult:
    w, h = data.width, data.height
    diagonal = math.sqrt(w * w + h * h)
    angle_deg = math.degrees(math.atan2(h, w))
    area = w * h
    perimeter = 2 * (w + h)
    unit = data.unit
    labels = {
        "width": f"{w:g} {unit}",
        "height": f"{h:g} {unit}",
        "diagonal": f"{diagonal:.2f} {unit}",
        "angle": f"{angle_deg:.1f}°",
        "area": f"{area:g} {unit}²",
        "perimeter": f"{perimeter:g} {unit}",
    }
    return RectangleGeometryResult(
        width=w,
        height=h,
        unit=unit,
        diagonal=round(diagonal, 4),
        angle_deg=round(angle_deg, 2),
        area=round(area, 4),
        perimeter=round(perimeter, 4),
        labels=labels,
    )


def square_geometry(data: SquareGeometryInput) -> SquareGeometryResult:
    s = data.side
    diagonal = math.sqrt(2 * s * s)
    area = s * s
    perimeter = 4 * s
    unit = data.unit
    labels = {
        "side": f"{s:g} {unit}",
        "diagonal": f"{diagonal:.2f} {unit}",
        "area": f"{area:g} {unit}²",
        "perimeter": f"{perimeter:g} {unit}",
    }
    return SquareGeometryResult(
        side=s,
        unit=unit,
        diagonal=round(diagonal, 4),
        area=round(area, 4),
        perimeter=round(perimeter, 4),
        labels=labels,
    )


def solid_geometry(data: SolidGeometryInput) -> SolidGeometryResult:
    """School volume and total surface area. Uses the same π as circle_geometry."""
    unit = data.unit
    shape = data.shape
    volume: float
    surface: float
    extra: dict[str, str] = {}

    if shape == "cube":
        if data.side is None:
            raise MathServiceError("cube requires side")
        s = data.side
        volume = s * s * s
        surface = 6 * s * s
        extra["side"] = f"{s:g} {unit}"
    elif shape == "rectangular_prism":
        if data.width is None or data.height is None or data.depth is None:
            raise MathServiceError("rectangular prism requires three edges")
        length, w, h = data.width, data.depth, data.height
        volume = length * w * h
        surface = 2 * (length * w + length * h + w * h)
        extra["length"] = f"{length:g} {unit}"
        extra["width"] = f"{w:g} {unit}"
        extra["height"] = f"{h:g} {unit}"
    elif shape == "cylinder":
        if data.radius is None or data.height is None:
            raise MathServiceError("cylinder requires radius and height")
        r, h = data.radius, data.height
        volume = math.pi * r * r * h
        surface = 2 * math.pi * r * (r + h)
        extra["radius"] = f"{r:g} {unit}"
        extra["height"] = f"{h:g} {unit}"
    elif shape == "cone":
        if data.radius is None or data.height is None:
            raise MathServiceError("cone requires radius and height")
        r, h = data.radius, data.height
        slant = math.sqrt(r * r + h * h)
        volume = (1.0 / 3.0) * math.pi * r * r * h
        surface = math.pi * r * (r + slant)
        extra["radius"] = f"{r:g} {unit}"
        extra["height"] = f"{h:g} {unit}"
        extra["slant"] = f"{slant:.2f} {unit}"
    elif shape == "sphere":
        if data.radius is None:
            raise MathServiceError("sphere requires radius")
        r = data.radius
        volume = (4.0 / 3.0) * math.pi * r * r * r
        surface = 4 * math.pi * r * r
        extra["radius"] = f"{r:g} {unit}"
    elif shape == "pyramid":
        pyr_h = data.height
        if pyr_h is None:
            raise MathServiceError("pyramid requires height")
        if data.side is not None:
            s = data.side
            volume = (1.0 / 3.0) * s * s * pyr_h
            slant = math.sqrt(pyr_h * pyr_h + (s / 2.0) * (s / 2.0))
            surface = s * s + 2 * s * slant
            extra["base"] = f"{s:g} {unit}"
        elif data.width is not None and data.depth is not None:
            length, w = data.width, data.depth
            volume = (1.0 / 3.0) * length * w * pyr_h
            face_l = math.sqrt(pyr_h * pyr_h + (w / 2.0) * (w / 2.0))
            face_w = math.sqrt(pyr_h * pyr_h + (length / 2.0) * (length / 2.0))
            surface = length * w + length * face_l + w * face_w
            extra["length"] = f"{length:g} {unit}"
            extra["width"] = f"{w:g} {unit}"
        else:
            raise MathServiceError("pyramid requires base side or length and width")
        extra["height"] = f"{pyr_h:g} {unit}"
    else:
        raise MathServiceError(f"unsupported solid {shape}")

    uses_pi = shape in {"cylinder", "cone", "sphere"}
    vol_label = f"{volume:.2f} {unit}³" if uses_pi else f"{volume:g} {unit}³"
    sa_label = f"{surface:.2f} {unit}²" if uses_pi else f"{surface:g} {unit}²"
    labels = {**extra, "volume": vol_label, "surface_area": sa_label}
    return SolidGeometryResult(
        shape=shape,
        volume=round(volume, 4),
        surface_area=round(surface, 4),
        unit=unit,
        labels=labels,
    )


def triangle_geometry(data: TriangleGeometryInput) -> TriangleGeometryResult:
    b, h = data.base, data.height
    area = 0.5 * b * h
    unit = data.unit
    labels = {
        "base": f"{b:g} {unit}",
        "height": f"{h:g} {unit}",
        "area": f"{area:g} {unit}²",
    }
    return TriangleGeometryResult(
        base=b,
        height=h,
        unit=unit,
        area=round(area, 4),
        labels=labels,
    )


def right_triangle_geometry(data: RightTriangleGeometryInput) -> RightTriangleGeometryResult:
    b, h = data.base, data.height
    hypotenuse = math.sqrt(b * b + h * h)
    area = 0.5 * b * h
    unit = data.unit
    angle_at_base = math.degrees(math.atan2(h, b))
    angle_at_height = math.degrees(math.atan2(b, h))
    labels = {
        "base": f"{b:g} {unit}",
        "height": f"{h:g} {unit}",
        "hypotenuse": f"{hypotenuse:.2f} {unit}",
        "area": f"{area:g} {unit}²",
        "angle": "90°",
        "angle_at_base": f"{angle_at_base:.1f}°",
        "angle_at_height": f"{angle_at_height:.1f}°",
    }
    return RightTriangleGeometryResult(
        base=b,
        height=h,
        unit=unit,
        hypotenuse=round(hypotenuse, 4),
        area=round(area, 4),
        labels=labels,
    )


def circle_geometry(data: CircleGeometryInput) -> CircleGeometryResult:
    r = data.radius
    diameter = 2 * r
    area = math.pi * r * r
    circumference = 2 * math.pi * r
    unit = data.unit
    labels = {
        "radius": f"{r:g} {unit}",
        "diameter": f"{diameter:g} {unit}",
        "area": f"{area:.2f} {unit}²",
        "circumference": f"{circumference:.2f} {unit}",
    }
    return CircleGeometryResult(
        radius=r,
        unit=unit,
        diameter=round(diameter, 4),
        area=round(area, 4),
        circumference=round(circumference, 4),
        labels=labels,
    )


def triangle_sides_geometry(data: TriangleSidesInput) -> TriangleSidesResult:
    """Area via Heron's formula, angles via the law of cosines — for a
    triangle given as three side lengths rather than base+height."""
    a, b, c = data.a, data.b, data.c
    s = (a + b + c) / 2
    area = math.sqrt(s * (s - a) * (s - b) * (s - c))
    perimeter = a + b + c
    angle_a = math.degrees(math.acos((b * b + c * c - a * a) / (2 * b * c)))
    angle_b = math.degrees(math.acos((a * a + c * c - b * b) / (2 * a * c)))
    angle_c = 180.0 - angle_a - angle_b
    unit = data.unit
    labels = {
        "a": f"{a:g} {unit}",
        "b": f"{b:g} {unit}",
        "c": f"{c:g} {unit}",
        "area": f"{area:.2f} {unit}²",
        "perimeter": f"{perimeter:g} {unit}",
        "angle_a": f"{angle_a:.1f}°",
        "angle_b": f"{angle_b:.1f}°",
        "angle_c": f"{angle_c:.1f}°",
    }
    return TriangleSidesResult(
        a=a,
        b=b,
        c=c,
        unit=unit,
        area=round(area, 4),
        perimeter=round(perimeter, 4),
        angle_a_deg=round(angle_a, 2),
        angle_b_deg=round(angle_b, 2),
        angle_c_deg=round(angle_c, 2),
        labels=labels,
    )


def trapezoid_geometry(data: TrapezoidInput) -> TrapezoidResult:
    area = (data.top + data.bottom) / 2 * data.height
    unit = data.unit
    labels = {
        "top": f"{data.top:g} {unit}",
        "bottom": f"{data.bottom:g} {unit}",
        "height": f"{data.height:g} {unit}",
        "area": f"{area:g} {unit}²",
    }
    return TrapezoidResult(
        top=data.top,
        bottom=data.bottom,
        height=data.height,
        unit=unit,
        area=round(area, 4),
        labels=labels,
    )


def parallelogram_geometry(data: ParallelogramInput) -> ParallelogramResult:
    area = data.base * data.height
    perimeter = 2 * (data.base + data.side)
    unit = data.unit
    labels = {
        "base": f"{data.base:g} {unit}",
        "height": f"{data.height:g} {unit}",
        "side": f"{data.side:g} {unit}",
        "area": f"{area:g} {unit}²",
        "perimeter": f"{perimeter:g} {unit}",
    }
    return ParallelogramResult(
        base=data.base,
        height=data.height,
        side=data.side,
        unit=unit,
        area=round(area, 4),
        perimeter=round(perimeter, 4),
        labels=labels,
    )


def sector_geometry(data: SectorInput) -> SectorResult:
    r, theta_deg = data.radius, data.angle_deg
    theta_rad = math.radians(theta_deg)
    arc_length = r * theta_rad
    area = 0.5 * r * r * theta_rad
    unit = data.unit
    labels = {
        "radius": f"{r:g} {unit}",
        "angle": f"{theta_deg:g}°",
        "arc_length": f"{arc_length:.2f} {unit}",
        "area": f"{area:.2f} {unit}²",
    }
    return SectorResult(
        radius=r,
        angle_deg=theta_deg,
        unit=unit,
        arc_length=round(arc_length, 4),
        area=round(area, 4),
        labels=labels,
    )
