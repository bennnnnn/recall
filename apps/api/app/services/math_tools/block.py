"""kind → verified system block. Registry: _BLOCK_BUILDERS."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.models.math_schemas import (
    CircleGeometryBlockSpec,
    CircleGeometryInput,
    CombinatoricsInput,
    EquationInput,
    GeometryBlockSpec,
    GraphBlockSpec,
    GraphSampleInput,
    MathIntent,
    MatrixInput,
    NewtonMethodInput,
    NumberTheoryInput,
    NumberTheoryResult,
    ParallelogramGeometryBlockSpec,
    ParallelogramInput,
    RectangleGeometryInput,
    RightTriangleGeometryBlockSpec,
    RightTriangleGeometryInput,
    SectorGeometryBlockSpec,
    SectorInput,
    SolidGeometryInput,
    SquareGeometryInput,
    StatisticsInput,
    SystemOfEquationsInput,
    TrapezoidGeometryBlockSpec,
    TrapezoidInput,
    TriangleGeometryBlockSpec,
    TriangleGeometryInput,
    TriangleSidesGeometryBlockSpec,
    TriangleSidesInput,
)
from app.services import math_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VerifiedMathBlock:
    """The system-prompt hint text plus the exact fence (if any) it asked
    the model to reuse verbatim — canonical_fence lets a post-stream check
    correct the model's actual output rather than only trusting compliance.
    Geometry/graph turns keep the diagram JSON on canonical_fence and the
    numeric final on canonical_answer so ```answer can be rewritten too."""

    text: str
    canonical_fence: dict[str, Any] | None = None
    canonical_answer: str | None = None


def _fence(kind: str, spec: Any) -> str:
    return f"```{kind}\n{json.dumps(spec.model_dump(), separators=(',', ':'))}\n```"


def _answer_canonical(content: str) -> dict[str, str]:
    return {"type": "answer", "content": content}


def _finish_with_answer(
    lines: list[str],
    answer: str,
    *,
    preface: str = (
        "Do NOT recompute. Explain in plain language with $...$ for formulas. "
        "End with this final-answer fence (copy verbatim):"
    ),
) -> VerifiedMathBlock:
    """Attach a canonical ```answer fence the post-stream rewriter can enforce."""
    lines.append(f"{preface}\n```answer\n{answer}\n```")
    return VerifiedMathBlock(
        text="\n".join(lines),
        canonical_fence=_answer_canonical(answer),
        canonical_answer=answer,
    )


def _diagram_block(
    lines: list[str],
    spec: Any,
    answer: str | None = None,
) -> VerifiedMathBlock:
    """Diagram JSON on canonical_fence; optional numeric ```answer rewrite."""
    if answer:
        lines.append(f"End with this final-answer fence (copy verbatim):\n```answer\n{answer}\n```")
    dump = spec.model_dump() if hasattr(spec, "model_dump") else spec
    return VerifiedMathBlock(
        text="\n".join(lines),
        canonical_fence=dump,
        canonical_answer=answer,
    )


def _format_equation_answer(
    solutions_latex: list[str],
    solution_kind: str,
) -> str:
    if solutions_latex:
        return ", ".join(solutions_latex)
    if solution_kind == "infinite":
        return r"\text{all real numbers}"
    return r"\text{no solution}"


def _format_system_answer(
    solutions: list[dict[str, str]],
    solution_kind: str,
) -> str:
    if solutions:
        sets = [", ".join(f"{k} = {v}" for k, v in sol.items()) for sol in solutions]
        return "; ".join(sets)
    if solution_kind == "infinite":
        return r"\text{infinitely many solutions}"
    return r"\text{no solution}"


def _verified_block_equation(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.lhs and intent.rhs):
        return None
    eq = EquationInput(
        lhs=intent.lhs[: settings.math_max_expr_length],
        rhs=intent.rhs[: settings.math_max_expr_length],
        variables=[intent.variable],
    )
    result = math_service.solve_equation(eq)
    lines.extend(result.steps)
    answer = _format_equation_answer(result.solutions_latex, result.solution_kind)
    lines.append(
        "Formula shape: INLINE $...$ for every step (never backticks around "
        "`$...$`; never ```math for step equations — those stream blank). "
        "A ```math fence is OK only for a standalone final display equation. "
        "Do NOT recompute the solutions. Show worked steps by COPYING the "
        "verified steps above verbatim — do NOT derive intermediate algebra "
        "yourself. Keep any spacing (e.g. \\quad) INSIDE the $...$ delimiters. "
        "End with this final-answer fence (copy verbatim):\n"
        f"```answer\n{answer}\n```"
    )
    return VerifiedMathBlock(
        text="\n".join(lines),
        canonical_fence=_answer_canonical(answer),
    )


def _verified_block_inequality(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.lhs and intent.rhs and intent.comparator):
        return None
    max_len = settings.math_max_expr_length
    if intent.lower is not None and intent.comparator_upper is not None:
        result = math_service.solve_compound_inequality(
            intent.lower[:max_len],
            intent.comparator,
            intent.lhs[:max_len],
            intent.comparator_upper,
            intent.rhs[:max_len],
            intent.variable,
        )
    else:
        result = math_service.solve_inequality(
            intent.lhs[:max_len],
            intent.rhs[:max_len],
            intent.variable,
            intent.comparator,
        )
    lines.extend(result.steps)
    answer = _format_equation_answer(result.solutions_latex, result.solution_kind)
    lines.append(
        "Formula shape: INLINE $...$ for the inequality and its solution "
        "set (never backticks around `$...$`). Do NOT recompute — copy the "
        "verified solution above verbatim. Render unions with \\lor "
        "(e.g. $x < -1 \\lor x > 1$) exactly as given. "
        "End with this final-answer fence (copy verbatim):\n"
        f"```answer\n{answer}\n```"
    )
    return VerifiedMathBlock(
        text="\n".join(lines),
        canonical_fence=_answer_canonical(answer),
    )


def _verified_block_system(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not intent.system_equations:
        return None
    capped_equations = [
        (
            lhs[: settings.math_max_expr_length],
            rhs[: settings.math_max_expr_length],
        )
        for lhs, rhs in intent.system_equations
    ]
    sys_input = SystemOfEquationsInput(
        equations=capped_equations,
        variables=intent.system_variables or ["x", "y"],
    )
    sys_result = math_service.solve_system(sys_input)
    lines.extend(sys_result.steps)
    answer = _format_system_answer(sys_result.solutions, sys_result.solution_kind)
    lines.append(
        "Formula shape: INLINE $...$ for every step (never backticks around "
        "`$...$`; never ```math for step equations). Do NOT recompute the "
        "solutions. Show worked steps by COPYING the verified steps above "
        "verbatim — do NOT derive intermediate algebra yourself. "
        "End with this final-answer fence (copy verbatim):\n"
        f"```answer\n{answer}\n```"
    )
    return VerifiedMathBlock(
        text="\n".join(lines),
        canonical_fence=_answer_canonical(answer),
    )


def _verified_block_numerical_method(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.newton_guess is not None):
        return None
    newton_input = NewtonMethodInput(
        expr=intent.expr[: settings.math_max_expr_length],
        variable=intent.variable,
        initial_guess=intent.newton_guess,
    )
    newton_result = math_service.newton_method(newton_input)
    lines.append(f"Newton's method for {newton_input.expr} = 0, x0 = {newton_input.initial_guess}:")
    for step in newton_result.iterations:
        lines.append(f"  n={step.n}: x_{step.n} = {step.x_n}, f(x_{step.n}) = {step.f_x_n}")
    if not newton_result.converged or newton_result.root is None:
        lines.append(
            f"Did not converge within {newton_result.iterations_used} iterations "
            "(the derivative may have vanished, or more iterations are needed) — "
            "do NOT present a root as found."
        )
        lines.append(
            "Do NOT recompute or invent different iteration values. Show the "
            "worked steps by COPYING the verified iteration table above verbatim."
        )
        # No ```answer — post-stream must not force a root that was not found.
        return VerifiedMathBlock(text="\n".join(lines))

    lines.append(
        f"Converged after {newton_result.iterations_used} iterations: root ≈ {newton_result.root}"
    )
    answer = f"{newton_result.root:g}"
    return _finish_with_answer(
        lines,
        answer,
        preface=(
            "Do NOT recompute or invent different iteration values. Show the "
            "worked steps by COPYING the verified iteration table above verbatim. "
            "End with this final-answer fence (copy verbatim):"
        ),
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
        f"area={rt_geo.area:g} {rt_geo.unit}²"
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
    lines.append("Do NOT recompute hypotenuse or area.")
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


def _verified_block_point(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.point_x is None or intent.point_y is None:
        return None
    px, py = intent.point_x, intent.point_y
    point_spec = GraphBlockSpec(
        expr=f"({px:g}, {py:g})",
        title=f"Point ({px:g}, {py:g})",
        x_min=px - 5,
        x_max=px + 5,
        points=[[px, py]],
    )
    lines.append(f"Point: ({px:g}, {py:g})")
    lines.append(
        "When a diagram helps, emit ONLY this fence (NEVER ```json). Do NOT "
        "invent a line, function, or extra points through it — the user asked "
        "to mark this one coordinate, nothing else:\n"
        f"{_fence('graph', point_spec)}"
    )
    return _diagram_block(lines, point_spec, f"({px:g}, {py:g})")


def _verified_block_vertical(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.point_x is None:
        return None
    vx = float(intent.point_x)
    y_min, y_max = -10.0, 10.0
    vert_spec = GraphBlockSpec(
        type="vertical",
        x=vx,
        y_min=y_min,
        y_max=y_max,
        expr=f"x = {vx:g}",
        title=f"x = {vx:g}",
    )
    lines.append(f"Vertical line: x = {vx:g} (from y = {y_min:g} to y = {y_max:g})")
    lines.append(
        "When a plot helps, emit ONLY this fence ONCE — no 'corrected/final graph "
        "spec' heading, and do NOT paste points in prose "
        "(the app renders the fence as an SVG):\n"
        f"{_fence('graph', vert_spec)}"
    )
    return _diagram_block(lines, vert_spec, f"{vx:g}")


def _verified_block_graph(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not intent.expr:
        return None
    # Axis-aligned circle/ellipse relations (x^2+y^2=1, x^2/9+y^2/4=1) are
    # not y=f(x) — sample parametrically into the same ```graph fence.
    ellipse_spec = math_service.build_ellipse_graph_spec(
        intent.expr[: settings.math_max_expr_length], settings.math_graph_max_points
    )
    if ellipse_spec is not None:
        lines.append(
            f"Relation samples for {ellipse_spec.expr}: "
            f"{len(ellipse_spec.points)} parametric points "
            "(closed curve)."
        )
        lines.append(
            "When a plot helps, emit ONLY this fence ONCE — no 'corrected/final graph "
            "spec' heading, and do NOT paste or re-list the points array in prose "
            "(the app renders the fence as an SVG):\n"
            f"{_fence('graph', ellipse_spec)}"
        )
        return _diagram_block(lines, ellipse_spec)

    line_spec = math_service.number_line_spec_from_expr(
        intent.expr[: settings.math_max_expr_length], intent.variable
    )
    if line_spec is not None:
        lines.append(
            f"Shaded region for {line_spec.expr} on the coordinate plane: "
            "dashed vertical boundary = endpoint not included, solid = included. "
            "Shade the solution set. This is NOT y=f(x) — do not plot a 0/1 step "
            "or a 1D number line."
        )
        lines.append(
            "When a plot helps, emit ONLY this fence ONCE — no 'corrected/final graph "
            "spec' heading, and do NOT paste or re-list the JSON in prose "
            "(the app renders the fence as an SVG):\n"
            f"{_fence('graph', line_spec)}"
        )
        return _diagram_block(lines, line_spec)

    sample = math_service.sample_function(
        GraphSampleInput(
            expr=intent.expr[: settings.math_max_expr_length],
            variable=intent.variable,
            x_min=-10,
            x_max=10,
            n=settings.math_graph_max_points,
        )
    )
    # Only attach segments when a real gap was detected (>1 segment)
    # — the overwhelmingly common case has none, and duplicating
    # every point into a redundant single-segment list would bloat
    # every graph fence for no benefit.
    has_discontinuity = len(sample.segments) > 1
    graph_spec = GraphBlockSpec(
        expr=sample.expr,
        variable=sample.variable,
        x_min=sample.x_min,
        x_max=sample.x_max,
        points=sample.points,
        segments=sample.segments if has_discontinuity else [],
    )
    lines.append(f"Function samples for {sample.expr}: {len(sample.points)} points.")
    if has_discontinuity:
        lines.append(
            f"NOTE: {sample.expr} has a discontinuity in this range (e.g. a vertical "
            "asymptote) — the sampled points are split into "
            f"{len(sample.segments)} segments; do not describe it as a single "
            "continuous curve."
        )
    lines.append(
        "When a plot helps, emit ONLY this fence ONCE — no 'corrected/final graph "
        "spec' heading, and do NOT paste or re-list the points array in prose "
        "(the app renders the fence as an SVG):\n"
        f"{_fence('graph', graph_spec)}"
    )
    return _diagram_block(lines, graph_spec)


def _verified_block_graph_pair(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.expr2):
        return None
    sample1 = math_service.sample_function(
        GraphSampleInput(
            expr=intent.expr[: settings.math_max_expr_length],
            variable=intent.variable,
            x_min=-10,
            x_max=10,
            n=settings.math_graph_max_points,
        )
    )
    sample2 = math_service.sample_function(
        GraphSampleInput(
            expr=intent.expr2[: settings.math_max_expr_length],
            variable=intent.variable,
            x_min=-10,
            x_max=10,
            n=settings.math_graph_max_points,
        )
    )
    has_disc1 = len(sample1.segments) > 1
    has_disc2 = len(sample2.segments) > 1
    graph_spec = GraphBlockSpec(
        expr=sample1.expr,
        variable=sample1.variable,
        x_min=sample1.x_min,
        x_max=sample1.x_max,
        points=sample1.points,
        segments=sample1.segments if has_disc1 else [],
        expr2=sample2.expr,
        variable2=sample2.variable,
        points2=sample2.points,
        segments2=sample2.segments if has_disc2 else [],
        label=f"y = {sample1.expr}",
        label2=f"y = {sample2.expr}",
    )
    lines.append(
        f"Function samples for y={sample1.expr} ({len(sample1.points)} points) and "
        f"y={sample2.expr} ({len(sample2.points)} points), same x-range for direct comparison."
    )
    lines.append(
        "When a plot helps, emit ONLY this fence ONCE — no 'corrected/final graph "
        "spec' heading, and do NOT paste or re-list either points array in prose "
        "(the app renders both curves as one SVG, color-coded with a legend):\n"
        f"{_fence('graph', graph_spec)}"
    )
    return _diagram_block(lines, graph_spec)


def _verified_block_calculus(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.operation):
        return None
    from app.services.math_tools.school import apply_calculus_extension

    extended = apply_calculus_extension(intent, settings, lines)
    if extended is not None:
        return extended
    if intent.operation == "simplify":
        out = math_service.simplify_expression(intent.expr, intent.variable)
    elif intent.operation == "differentiate":
        out = math_service.differentiate_expression(intent.expr, intent.variable)
    elif intent.operation == "integrate":
        if intent.integral_lower is not None and intent.integral_upper is not None:
            out = math_service.integrate_definite(
                intent.expr,
                intent.variable,
                intent.integral_lower,
                intent.integral_upper,
            )
        else:
            out = math_service.integrate_expression(intent.expr, intent.variable)
    elif intent.operation == "factor":
        out = math_service.factor_expression(intent.expr, intent.variable)
    elif intent.operation == "expand":
        out = math_service.expand_expression(intent.expr, intent.variable)
    else:
        return None
    if not out.solved:
        lines.append(
            f"SymPy could not find a closed-form result (got: {out.latex}). "
            "Do NOT claim this as a verified answer — tell the user no closed "
            "form was found, or explain why the integral is hard, instead of "
            "asserting a solution."
        )
        return VerifiedMathBlock(text="\n".join(lines))
    lines.append(f"Result: {out.latex}")
    return _finish_with_answer(lines, out.latex)


def _verified_block_limit(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.limit_point is not None):
        return None
    limit_out = math_service.compute_limit(intent.expr, intent.variable, intent.limit_point)
    lines.append(f"Result: {limit_out.latex}")
    if limit_out.is_infinite:
        lines.append(
            "This limit is infinite (or does not exist as a finite two-sided "
            "value) — render it as \\infty, do not treat it as an ordinary "
            "finite number."
        )
    return _finish_with_answer(lines, limit_out.latex)


def _verified_block_series(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.series_start is not None and intent.series_end is not None):
        return None
    series_out = math_service.evaluate_series_sum(
        intent.expr, intent.variable, intent.series_start, intent.series_end
    )
    lines.append(f"Result: {series_out.latex}")
    if series_out.is_convergent is not None:
        lines.append(
            f"Convergent: {series_out.is_convergent}"
            + (
                f" (absolutely convergent: {series_out.is_absolutely_convergent})"
                if series_out.is_absolutely_convergent is not None
                else ""
            )
            + "."
        )
    if series_out.is_infinite:
        lines.append(
            "This series diverges to infinity — render it as \\infty, do not "
            "treat it as an ordinary finite number."
        )
    return _finish_with_answer(lines, series_out.latex)


def _verified_block_statistics(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not intent.stats_numbers or len(intent.stats_numbers) < 2:
        return None
    result = math_service.compute_statistics(StatisticsInput(numbers=intent.stats_numbers))
    lines.append(f"Data ({result.count} values): {', '.join(f'{v:g}' for v in result.numbers)}")
    sample_stdev = (
        f"{result.stdev_sample:g}" if result.stdev_sample is not None else "n/a (needs 2+ values)"
    )
    lines.append(
        f"mean={result.mean:g} median={result.median:g} mode={result.labels.get('mode', 'none')} "
        f"range={result.range:g} population variance={result.variance_population:g} "
        f"population stdev={result.stdev_population:g} sample stdev={sample_stdev}"
    )
    if intent.stats_op == "median":
        answer = result.labels["median"]
    elif intent.stats_op == "mode":
        answer = result.labels["mode"]
    elif intent.stats_op == "stdev":
        answer = result.labels["population_stdev"]
    elif intent.stats_op == "variance":
        answer = f"{result.variance_population:g}"
    else:
        answer = result.labels["mean"]
    return _finish_with_answer(
        lines,
        answer,
        preface=(
            "Do NOT recompute any of these values — use the verified numbers above. "
            "Show the relevant formula with these exact numbers substituted in. "
            "End with this final-answer fence (copy verbatim):"
        ),
    )


def _format_number_theory_answer(result: NumberTheoryResult) -> str:
    """Short final for ```answer — matches the verified step language."""
    if result.operation == "factorize" and result.factors is not None:
        parts = [f"{p}^{{{e}}}" if e > 1 else f"{p}" for p, e in sorted(result.factors.items())]
        return " \\times ".join(parts)
    if result.operation == "is_prime" and result.result_bool is not None:
        return "prime" if result.result_bool else "not prime"
    if result.result_int is not None:
        return str(result.result_int)
    return result.steps[-1] if result.steps else ""


def _verified_block_combinatorics(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.combo_op is None or intent.combo_n is None:
        return None
    if intent.combo_op != "factorial" and intent.combo_k is None:
        return None
    result = math_service.compute_combinatorics(
        CombinatoricsInput(operation=intent.combo_op, n=intent.combo_n, k=intent.combo_k)
    )
    lines.extend(result.steps)
    lines.append(f"Result: {result.result}")
    return _finish_with_answer(
        lines,
        str(result.result),
        preface="Do NOT recompute — use this exact verified result. "
        "End with this final-answer fence (copy verbatim):",
    )


def _verified_block_number_theory(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.numtheory_op is None or intent.numtheory_a is None:
        return None
    result = math_service.compute_number_theory(
        NumberTheoryInput(operation=intent.numtheory_op, a=intent.numtheory_a, b=intent.numtheory_b)
    )
    lines.extend(result.steps)
    answer = _format_number_theory_answer(result)
    if not answer:
        return VerifiedMathBlock(text="\n".join(lines))
    return _finish_with_answer(
        lines,
        answer,
        preface="Do NOT recompute — use this exact verified result. "
        "End with this final-answer fence (copy verbatim):",
    )


def _verified_block_matrix(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.matrix_op is None or not intent.matrix_rows:
        return None
    result = math_service.compute_matrix(
        MatrixInput(operation=intent.matrix_op, rows=intent.matrix_rows)
    )
    lines.extend(result.steps)
    if result.operation == "inverse" and result.inverse_latex:
        answer = result.inverse_latex
    elif result.result_latex:
        answer = result.result_latex
    elif result.determinant is not None:
        answer = f"{result.determinant:g}"
    else:
        return VerifiedMathBlock(text="\n".join(lines))
    return _finish_with_answer(
        lines,
        answer,
        preface="Do NOT recompute — use this exact verified result. "
        "End with this final-answer fence (copy verbatim):",
    )


_BlockBuilder = Callable[[MathIntent, Settings, list[str]], VerifiedMathBlock | None]

_BLOCK_BUILDERS: dict[str, _BlockBuilder] = {
    "equation": _verified_block_equation,
    "inequality": _verified_block_inequality,
    "system": _verified_block_system,
    "numerical_method": _verified_block_numerical_method,
    "rectangle": _verified_block_rectangle,
    "square": _verified_block_square,
    "solid": _verified_block_solid,
    "circle": _verified_block_circle,
    "triangle": _verified_block_triangle,
    "right_triangle": _verified_block_right_triangle,
    "triangle_sides": _verified_block_triangle_sides,
    "trapezoid": _verified_block_trapezoid,
    "parallelogram": _verified_block_parallelogram,
    "sector": _verified_block_sector,
    "point": _verified_block_point,
    "vertical": _verified_block_vertical,
    "graph": _verified_block_graph,
    "graph_pair": _verified_block_graph_pair,
    "calculus": _verified_block_calculus,
    "limit": _verified_block_limit,
    "series": _verified_block_series,
    "statistics": _verified_block_statistics,
    "combinatorics": _verified_block_combinatorics,
    "number_theory": _verified_block_number_theory,
    "matrix": _verified_block_matrix,
}


def _build_verified_block(intent: MathIntent, settings: Settings) -> VerifiedMathBlock | None:
    lines: list[str] = [
        "Symbolic math results (verified by SymPy — use these exact values in your answer):"
    ]

    try:
        builder = _BLOCK_BUILDERS.get(intent.kind)
        if builder is None:
            from app.services.math_tools.school import SCHOOL_BLOCK_BUILDERS

            builder = SCHOOL_BLOCK_BUILDERS.get(intent.kind)
        if builder is None:
            return None
        return builder(intent, settings, lines)
    except math_service.MathServiceError as exc:
        logger.info("math_tools skipped: %s", exc)
        return None
    except Exception:
        logger.exception("math_tools failed")
        return None
