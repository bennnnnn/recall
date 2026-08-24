"""Graph / point / vertical verified blocks."""

from __future__ import annotations

from app.core.config import Settings
from app.models.math_schemas import GraphBlockSpec, GraphSampleInput, MathIntent
from app.services import math_service
from app.services.math_tools.block.common import (
    VerifiedMathBlock,
    _diagram_block,
)


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
        "Do NOT invent a function or extra points through this marker — "
        "Recall attaches the verified plot."
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
        return _diagram_block(lines, ellipse_spec)

    line_spec = math_service.number_line_spec_from_expr(
        intent.expr[: settings.math_max_expr_length], intent.variable
    )
    if line_spec is not None:
        lines.append(
            f"Shaded region for {line_spec.expr} on the number line: "
            "open circle = endpoint not included, filled circle = included. "
            "This is a one-variable inequality rendered as a number line "
            '(type "number_line") — shade the solution '
            "interval, do not plot a y=f(x) curve."
        )
        return _diagram_block(lines, line_spec)

    # Use the user-named domain ("from 0 to 100") when present, else the
    # [-10, 10] default. Without this the verified block always sampled the
    # default window even when the user asked for a specific range, so the
    # model emitted its own (often wrong) spec.
    x_min = intent.graph_x_min if intent.graph_x_min is not None else -10
    x_max = intent.graph_x_max if intent.graph_x_max is not None else 10
    sample = math_service.sample_function(
        GraphSampleInput(
            expr=intent.expr[: settings.math_max_expr_length],
            variable=intent.variable,
            x_min=x_min,
            x_max=x_max,
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
    return _diagram_block(lines, graph_spec)


def _verified_block_graph_pair(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.expr2):
        return None
    x_min = intent.graph_x_min if intent.graph_x_min is not None else -10
    x_max = intent.graph_x_max if intent.graph_x_max is not None else 10
    sample1 = math_service.sample_function(
        GraphSampleInput(
            expr=intent.expr[: settings.math_max_expr_length],
            variable=intent.variable,
            x_min=x_min,
            x_max=x_max,
            n=settings.math_graph_max_points,
        )
    )
    sample2 = math_service.sample_function(
        GraphSampleInput(
            expr=intent.expr2[: settings.math_max_expr_length],
            variable=intent.variable,
            x_min=x_min,
            x_max=x_max,
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
    return _diagram_block(lines, graph_spec)
