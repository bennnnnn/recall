"""Geometry verified blocks."""

from __future__ import annotations

from app.core.config import Settings
from app.models.math_schemas import (
    CircleGeometryBlockSpec,
    CircleGeometryInput,
    GeometryBlockSpec,
    MathIntent,
    ParallelogramGeometryBlockSpec,
    ParallelogramInput,
    RectangleGeometryInput,
    RightTriangleGeometryBlockSpec,
    RightTriangleGeometryInput,
    SectorGeometryBlockSpec,
    SectorInput,
    SolidGeometryInput,
    SquareGeometryInput,
    TrapezoidGeometryBlockSpec,
    TrapezoidInput,
    TriangleGeometryBlockSpec,
    TriangleGeometryInput,
    TriangleSidesGeometryBlockSpec,
    TriangleSidesInput,
)
from app.services import math_service
from app.services.math_tools.block.common import (
    VerifiedMathBlock,
    _diagram_block,
    _fence,
    _finish_with_answer,
)


def _verified_block_rectangle(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.width and intent.height):
        return None
    rect_geo = math_service.rectangle_geometry(
        RectangleGeometryInput(width=intent.width, height=intent.height, unit=intent.unit)
    )
    lines.append(
        f"Rectangle: width={rect_geo.width:g} {rect_geo.unit} "
        f"height={rect_geo.height:g} {rect_geo.unit} "
        f"diagonal={rect_geo.diagonal:g} angle={rect_geo.angle_deg:g}°"
    )
    # Only annotate the diagram with what was actually asked for —
    # e.g. "rectangle area 4 by 5" should draw area, not an
    # unrequested diagonal + angle. If nothing specific was asked,
    # default to the diagonal (a reasonable generic illustration)
    # without the angle number, since a bare "draw a rectangle" isn't
    # asking about any particular angle.
    show_area = intent.wants_area
    show_perimeter = intent.wants_perimeter
    show_diagonal = intent.wants_diagonal or intent.wants_angle or not (show_area or show_perimeter)
    show_angle = intent.wants_angle
    spec = GeometryBlockSpec(
        type="rectangle",
        width=rect_geo.width,
        height=rect_geo.height,
        unit=rect_geo.unit,
        show_diagonal=show_diagonal,
        show_angle=show_angle,
        show_area=show_area,
        show_perimeter=show_perimeter,
        show_ticks=True,
        diagonal=rect_geo.diagonal,
        angle_deg=rect_geo.angle_deg,
        area=rect_geo.area,
        perimeter=rect_geo.perimeter,
        labels=rect_geo.labels,
    )
    lines.append(
        "When a diagram helps, emit ONLY this fence (adjust labels if needed):\n"
        f"{_fence('geometry', spec)}"
    )
    lines.append("Do NOT recompute diagonal, angle, area, or perimeter.")
    if intent.wants_perimeter:
        answer = f"{rect_geo.perimeter:g}"
    elif intent.wants_diagonal and not intent.wants_area:
        answer = f"{rect_geo.diagonal:g}"
    else:
        answer = f"{rect_geo.area:g}"
    return _diagram_block(lines, spec, answer)


def _verified_block_square(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.side or intent.width):
        return None
    side = intent.side or intent.width or 5
    square_geo = math_service.square_geometry(SquareGeometryInput(side=side, unit=intent.unit))
    lines.append(
        f"Square: side={square_geo.side:g} {square_geo.unit} "
        f"diagonal={square_geo.diagonal:g} {square_geo.unit} "
        f"area={square_geo.area:g} {square_geo.unit}² "
        f"perimeter={square_geo.perimeter:g} {square_geo.unit}"
    )
    spec = GeometryBlockSpec(
        type="square",
        side=square_geo.side,
        width=square_geo.side,
        height=square_geo.side,
        unit=square_geo.unit,
        show_diagonal=True,
        show_area=True,
        show_perimeter=True,
        show_ticks=True,
        diagonal=square_geo.diagonal,
        area=square_geo.area,
        perimeter=square_geo.perimeter,
        labels=square_geo.labels,
    )
    lines.append(
        f"When a diagram helps, emit ONLY this fence (NEVER ```json):\n{_fence('geometry', spec)}"
    )
    lines.append("Do NOT recompute diagonal, area, or perimeter.")
    return _diagram_block(lines, spec, f"{square_geo.area:g}")


def _verified_block_solid(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.solid_shape is None:
        return None
    geo = math_service.solid_geometry(
        SolidGeometryInput(
            shape=intent.solid_shape,
            width=intent.width,
            height=intent.height,
            depth=intent.depth,
            side=intent.side,
            radius=intent.radius,
            unit=intent.unit,
        )
    )
    lines.append(
        f"Solid ({geo.shape}): volume={geo.labels['volume']} "
        f"surface_area={geo.labels['surface_area']}"
    )
    for key, value in geo.labels.items():
        if key in {"volume", "surface_area"}:
            continue
        lines.append(f"{key}={value}")
    lines.append("Do NOT recompute volume or surface area.")
    if intent.wants_surface_area and not intent.wants_volume:
        answer = geo.labels["surface_area"].rsplit(" ", 1)[0]
    else:
        answer = geo.labels["volume"].rsplit(" ", 1)[0]
    return _finish_with_answer(lines, answer)


def _verified_block_circle(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not intent.radius:
        return None
    circle_geo = math_service.circle_geometry(
        CircleGeometryInput(radius=intent.radius, unit=intent.unit)
    )
    lines.append(
        f"Circle: radius={circle_geo.radius:g} {circle_geo.unit} "
        f"diameter={circle_geo.diameter:g} {circle_geo.unit} "
        f"area={circle_geo.area:.2f} {circle_geo.unit}² "
        f"circumference={circle_geo.circumference:.2f} {circle_geo.unit}"
    )
    circle_spec = CircleGeometryBlockSpec(
        type="circle",
        radius=circle_geo.radius,
        unit=circle_geo.unit,
        show_diameter=intent.wants_diameter,
        show_area=intent.wants_area,
        show_circumference=intent.wants_circumference,
        diameter=circle_geo.diameter,
        area=circle_geo.area,
        circumference=circle_geo.circumference,
        labels=circle_geo.labels,
    )
    lines.append(
        "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
        f"{_fence('geometry', circle_spec)}"
    )
    lines.append("Do NOT recompute diameter, area, or circumference.")
    return _diagram_block(lines, circle_spec, f"{circle_geo.area:.2f}")


def _verified_block_triangle(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.base and intent.height):
        return None
    tri_geo = math_service.triangle_geometry(
        TriangleGeometryInput(base=intent.base, height=intent.height, unit=intent.unit)
    )
    lines.append(
        f"Triangle: base={tri_geo.base:g} {tri_geo.unit} "
        f"height={tri_geo.height:g} {tri_geo.unit} area={tri_geo.area:g} {tri_geo.unit}²"
    )
    tri_spec = TriangleGeometryBlockSpec(
        type="triangle",
        base=tri_geo.base,
        height=tri_geo.height,
        unit=tri_geo.unit,
        show_labels=True,
        show_ticks=True,
        show_altitude=True,
        show_angle=True,
        area=tri_geo.area,
        labels=tri_geo.labels,
    )
    lines.append(
        "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
        f"{_fence('geometry', tri_spec)}"
    )
    lines.append("Do NOT recompute area.")
    return _diagram_block(lines, tri_spec, f"{tri_geo.area:g}")


def _verified_block_right_triangle(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.base and intent.height):
        return None
    rt_geo = math_service.right_triangle_geometry(
        RightTriangleGeometryInput(base=intent.base, height=intent.height, unit=intent.unit)
    )
    lines.append(
        f"Right triangle: base={rt_geo.base:g} {rt_geo.unit} "
        f"height={rt_geo.height:g} {rt_geo.unit} "
        f"hypotenuse={rt_geo.hypotenuse:g} {rt_geo.unit} "
        f"area={rt_geo.area:g} {rt_geo.unit}² "
        f"angles=90° / {rt_geo.labels['angle_at_base']} at base / "
        f"{rt_geo.labels['angle_at_height']} at height"
    )
    rt_spec = RightTriangleGeometryBlockSpec(
        type="right_triangle",
        base=rt_geo.base,
        height=rt_geo.height,
        unit=rt_geo.unit,
        show_labels=True,
        show_hypotenuse=True,
        show_angle=True,
        hypotenuse=rt_geo.hypotenuse,
        area=rt_geo.area,
        labels=rt_geo.labels,
    )
    lines.append(
        "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
        f"{_fence('geometry', rt_spec)}"
    )
    lines.append("Do NOT recompute hypotenuse, area, or interior angles.")
    lines.append(
        "Put all three interior-angle degree labels on the vertices (not only the 90° square)."
    )
    return _diagram_block(lines, rt_spec, f"{rt_geo.area:g}")


def _verified_block_triangle_sides(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.tri_a and intent.tri_b and intent.tri_c):
        return None
    tri_geo = math_service.triangle_sides_geometry(
        TriangleSidesInput(a=intent.tri_a, b=intent.tri_b, c=intent.tri_c, unit=intent.unit)
    )
    lines.append(
        f"Triangle: a={tri_geo.a:g} {tri_geo.unit} b={tri_geo.b:g} {tri_geo.unit} "
        f"c={tri_geo.c:g} {tri_geo.unit} area={tri_geo.area:g} {tri_geo.unit}² "
        f"perimeter={tri_geo.perimeter:g} {tri_geo.unit} "
        f"angles={tri_geo.angle_a_deg:g}°/{tri_geo.angle_b_deg:g}°/{tri_geo.angle_c_deg:g}°"
    )
    isosceles = (
        abs(tri_geo.a - tri_geo.b) < 1e-9
        or abs(tri_geo.a - tri_geo.c) < 1e-9
        or abs(tri_geo.b - tri_geo.c) < 1e-9
    )
    tri_spec = TriangleSidesGeometryBlockSpec(
        type="triangle_sides",
        a=tri_geo.a,
        b=tri_geo.b,
        c=tri_geo.c,
        unit=tri_geo.unit,
        show_labels=True,
        show_ticks=True,
        show_altitude=True,
        show_median=isosceles,
        show_angle=True,
        area=tri_geo.area,
        labels=tri_geo.labels,
    )
    lines.append(
        "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
        f"{_fence('geometry', tri_spec)}"
    )
    lines.append(
        "Do NOT recompute area, perimeter, or angles — "
        "this is Heron's formula + the law of cosines."
    )
    return _diagram_block(lines, tri_spec, f"{tri_geo.area:g}")


def _verified_block_trapezoid(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.trapezoid_top and intent.trapezoid_bottom and intent.height):
        return None
    trap_geo = math_service.trapezoid_geometry(
        TrapezoidInput(
            top=intent.trapezoid_top,
            bottom=intent.trapezoid_bottom,
            height=intent.height,
            unit=intent.unit,
        )
    )
    lines.append(
        f"Trapezoid: top={trap_geo.top:g} {trap_geo.unit} "
        f"bottom={trap_geo.bottom:g} {trap_geo.unit} "
        f"height={trap_geo.height:g} {trap_geo.unit} area={trap_geo.area:g} {trap_geo.unit}²"
    )
    trap_spec = TrapezoidGeometryBlockSpec(
        type="trapezoid",
        top=trap_geo.top,
        bottom=trap_geo.bottom,
        height=trap_geo.height,
        unit=trap_geo.unit,
        show_labels=True,
        show_angle=bool(intent.wants_angle),
        area=trap_geo.area,
        labels=trap_geo.labels,
    )
    lines.append(
        "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
        f"{_fence('geometry', trap_spec)}"
    )
    lines.append("Do NOT recompute area — area = (top + bottom) / 2 \\times height.")
    return _diagram_block(lines, trap_spec, f"{trap_geo.area:g}")


def _verified_block_parallelogram(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.base and intent.height and intent.side):
        return None
    para_geo = math_service.parallelogram_geometry(
        ParallelogramInput(
            base=intent.base, height=intent.height, side=intent.side, unit=intent.unit
        )
    )
    lines.append(
        f"Parallelogram: base={para_geo.base:g} {para_geo.unit} height={para_geo.height:g} "
        f"{para_geo.unit} side={para_geo.side:g} {para_geo.unit} area={para_geo.area:g} "
        f"{para_geo.unit}² perimeter={para_geo.perimeter:g} {para_geo.unit}"
    )
    para_spec = ParallelogramGeometryBlockSpec(
        type="parallelogram",
        base=para_geo.base,
        height=para_geo.height,
        side=para_geo.side,
        unit=para_geo.unit,
        show_labels=True,
        show_angle=bool(intent.wants_angle),
        area=para_geo.area,
        perimeter=para_geo.perimeter,
        labels=para_geo.labels,
    )
    lines.append(
        "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
        f"{_fence('geometry', para_spec)}"
    )
    lines.append("Do NOT recompute area or perimeter.")
    return _diagram_block(lines, para_spec, f"{para_geo.area:g}")


def _verified_block_sector(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.radius and intent.sector_angle_deg):
        return None
    sector_geo = math_service.sector_geometry(
        SectorInput(radius=intent.radius, angle_deg=intent.sector_angle_deg, unit=intent.unit)
    )
    lines.append(
        f"Circle sector: radius={sector_geo.radius:g} {sector_geo.unit} "
        f"angle={sector_geo.angle_deg:g}° arc_length={sector_geo.arc_length:.2f} {sector_geo.unit} "
        f"area={sector_geo.area:.2f} {sector_geo.unit}²"
    )
    sector_spec = SectorGeometryBlockSpec(
        type="sector",
        radius=sector_geo.radius,
        angle_deg=sector_geo.angle_deg,
        unit=sector_geo.unit,
        show_labels=True,
        arc_length=sector_geo.arc_length,
        area=sector_geo.area,
        labels=sector_geo.labels,
    )
    lines.append(
        "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
        f"{_fence('geometry', sector_spec)}"
    )
    lines.append("Do NOT recompute arc length or area.")
    return _diagram_block(lines, sector_spec, f"{sector_geo.area:g}")
