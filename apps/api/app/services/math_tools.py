"""Pre-stream symbolic math augmentation for chat prompts."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import Settings
from app.models.math_schemas import (
    CircleGeometryBlockSpec,
    CircleGeometryInput,
    EquationInput,
    GeometryBlockSpec,
    GraphBlockSpec,
    GraphSampleInput,
    MathImageExtract,
    MathIntent,
    NewtonMethodInput,
    RectangleGeometryInput,
    RightTriangleGeometryBlockSpec,
    RightTriangleGeometryInput,
    SquareGeometryInput,
    SystemOfEquationsInput,
    TriangleGeometryBlockSpec,
    TriangleGeometryInput,
)
from app.services import math_service

logger = logging.getLogger(__name__)


# Cap before any poly-time regex. CodeQL only treats a const length compare as a
# ReDoS sanitizer — collapsing whitespace alone is not enough.
_MAX_MATH_INPUT = 1000


def _collapse_ws(text: str) -> str:
    """Collapse runs of whitespace so matchers need no ``\\s+`` (avoids ReDoS)."""
    return " ".join(text.split())


# Common LaTeX commands/symbols that appear in a pasted or OCR'd limit/series
# expression — _parse_expression's safe-character allowlist rejects any
# backslash outright, so these must be normalized to plain SymPy-parseable
# syntax first. Not exhaustive: an unrecognized command left behind simply
# fails to parse and the caller gracefully falls back to no verified block,
# same as any other unparseable expression.
_LATEX_SYMBOL_SUBS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\\infty"), "oo"),
    (re.compile(r"\\pi\b"), "pi"),
    (re.compile(r"\\cdot"), "*"),
    (re.compile(r"\\times"), "*"),
    (re.compile(r"\\div"), "/"),
    (re.compile(r"\\left"), ""),
    (re.compile(r"\\right"), ""),
]
_LATEX_FUNCTION_RE = re.compile(
    r"\\(sin|cos|tan|sec|csc|cot|arcsin|arccos|arctan|sinh|cosh|tanh|log|ln|sqrt|exp|min|max)\b",
    re.IGNORECASE,
)


def _normalize_latex_expr(expr: str) -> str:
    s = expr
    for pattern, replacement in _LATEX_SYMBOL_SUBS:
        s = pattern.sub(replacement, s)
    s = _LATEX_FUNCTION_RE.sub(lambda m: m.group(1), s)
    return s


def _strip_series_prefix(expr: str) -> str:
    s = _collapse_ws(expr)
    if len(s) > _MAX_MATH_INPUT:
        return s[:_MAX_MATH_INPUT]
    prev = None
    while prev != s:
        prev = s
        lower = s.lower()
        for prefix in (
            "does the series ",
            "does the sum ",
            "the series ",
            "the sum ",
            "series ",
            "sum ",
            "of ",
        ):
            if lower.startswith(prefix):
                s = s[len(prefix) :].strip()
                break
        else:
            break
    return s


_DEFAULT_NEWTON_GUESS = 1.0
_NEWTON_NUM = re.compile(r"-?\d+(?:\.\d+)?")

_TRAILING_FILLER_SUFFIXES = (
    " please",
    " please.",
    " now",
    " now.",
    " thank",
    " thanks",
    " thanks.",
    " thank you",
    " thank you.",
    " for me",
    " for me.",
    " to me",
    " to me.",
    " real quick",
    " real quick.",
    " quickly",
    " quickly.",
    " briefly",
    " briefly.",
)

_CALC_VERBS = (
    "simplify",
    "differentiate",
    "derivative",
    "integrate",
    "integral",
    "factor",
    "expand",
)


def _split_and_then(s: str) -> str:
    """Keep text before the first `` and `` / `` then `` clause (no regex)."""
    lower = s.lower()
    cut: int | None = None
    for token in (" and ", " then "):
        idx = lower.find(token)
        if idx != -1 and (cut is None or idx < cut):
            cut = idx
    return s[:cut] if cut is not None else s


def _strip_trailing_filler(expr: str) -> str:
    """`_GRAPH_EXPR`/the calculus expr-match are greedy captures of everything
    after the trigger word, so natural phrasing like "graph x^2 please" or
    "differentiate x^2 for me" sweeps the trailing words into the
    "expression" — which then fails to parse and silently disables the
    verified-math augmentation for phrasing a real user would actually type."""
    s = _collapse_ws(expr)
    # Const length compare must sit in this function for CodeQL's ReDoS barrier.
    if len(s) > _MAX_MATH_INPUT:
        return s[:_MAX_MATH_INPUT]
    # A conjunction essentially never appears inside a math expression
    # itself — anything from " and "/" then " onward is a new clause of
    # natural language (e.g. "sin(x) and explain it"), not part of the expr.
    s = _split_and_then(s)
    prev = None
    while prev != s:
        prev = s
        lower = s.lower()
        for suffix in _TRAILING_FILLER_SUFFIXES:
            if lower.endswith(suffix):
                s = s[: -len(suffix)].rstrip()
                break
    return s


def _calc_expr_tail(cleaned: str) -> str | None:
    """Text after the first calculus verb (index scan — avoids poly regex)."""
    lower = cleaned.lower()
    best_at: int | None = None
    best_end = 0
    for verb in _CALC_VERBS:
        needle = f"{verb} "
        idx = lower.find(needle)
        if idx != -1 and (best_at is None or idx < best_at):
            best_at = idx
            best_end = idx + len(needle)
    if best_at is None:
        return None
    return cleaned[best_end:]


def needs_symbolic_math(text: str, *, has_image_attachment: bool = False) -> bool:
    from app.services import math_text_match

    return math_text_match.needs_symbolic(text, has_image_attachment=has_image_attachment)


def extract_math_intent(text: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    cleaned = mtm.prepare(text)
    if not cleaned:
        return None
    lower = cleaned.lower()

    dims = mtm.first_dim_pair(cleaned)
    padded = f" {lower} "
    if dims is not None and ("rectangle" in lower or " rect " in padded or "diagonal" in lower):
        width, height, unit = dims
        return MathIntent(
            kind="rectangle",
            width=width,
            height=height,
            unit=unit,
            operation="solve",
            wants_diagonal=" diagonal" in padded or padded.startswith("diagonal "),
            wants_angle=" angle" in padded or "angles" in lower,
            wants_area=" area" in padded or padded.startswith("area "),
            wants_perimeter=" perimeter" in padded or padded.startswith("perimeter "),
        )

    if mtm.has_draw_shape(lower, "rectangle"):
        return MathIntent(kind="rectangle", width=6, height=4, unit="cm", operation="solve")

    if "square" in lower:
        side = mtm.number_after(cleaned, "side") or mtm.number_after(cleaned, "edge")
        if side is None and dims is not None and dims[0] == dims[1]:
            side = dims[0]
        if side is not None:
            return MathIntent(
                kind="square", side=side, width=side, height=side, unit="cm", operation="solve"
            )
        return MathIntent(kind="square", side=5, width=5, height=5, unit="cm", operation="solve")

    if "circle" in lower:
        wants_area = "area" in lower
        wants_circumference = "circumference" in lower
        radius = mtm.number_after(cleaned, "radius")
        if radius is not None:
            return MathIntent(
                kind="circle",
                radius=radius,
                unit="cm",
                operation="solve",
                wants_area=wants_area,
                wants_circumference=wants_circumference,
            )
        diameter = mtm.number_after(cleaned, "diameter")
        if diameter is not None:
            return MathIntent(
                kind="circle",
                radius=diameter / 2,
                unit="cm",
                operation="solve",
                wants_diameter=True,
                wants_area=wants_area,
                wants_circumference=wants_circumference,
            )
        return MathIntent(kind="circle", radius=5, unit="cm", operation="solve")

    if "right triangle" in lower:
        if dims is not None:
            base, height, unit = dims
            return MathIntent(
                kind="right_triangle",
                base=base,
                height=height,
                unit=unit,
                operation="solve",
            )
        return MathIntent(kind="right_triangle", base=6, height=4, unit="cm", operation="solve")

    base_n = mtm.number_after(cleaned, "base")
    height_n = mtm.number_after(cleaned, "height")
    if base_n is not None and height_n is not None and "triangle" in lower:
        return MathIntent(
            kind="triangle",
            base=base_n,
            height=height_n,
            unit="cm",
            operation="solve",
        )

    if "triangle" in lower and any(k in lower for k in ("area", "draw", "visuali", "sketch")):
        return MathIntent(kind="triangle", base=8, height=5, unit="cm", operation="solve")

    point = mtm.bare_coord(cleaned) or mtm.plot_point(cleaned)
    if point is not None:
        return MathIntent(
            kind="point",
            point_x=point[0],
            point_y=point[1],
            operation="graph",
        )

    vert_x = mtm.vertical_line_x(cleaned)
    if vert_x is not None:
        return MathIntent(kind="vertical", point_x=vert_x, operation="graph")

    g_expr = mtm.graph_expr(cleaned)
    if g_expr is not None:
        expr = _strip_trailing_filler(g_expr).replace("^", "**").replace(" ", "")
        # Prefer vertical for "graph x=4"
        if expr.lower().startswith("x="):
            num = mtm.number_after(expr, "x=")
            if num is None:
                compact = expr.lower().replace(" ", "")
                if compact.startswith("x="):
                    try:
                        num = float(compact[2:])
                    except ValueError:
                        num = None
            if num is not None:
                return MathIntent(kind="vertical", point_x=num, operation="graph")
        expr = _strip_trailing_filler(g_expr).replace("^", "**")
        return MathIntent(kind="graph", expr=expr, operation="graph")

    op_word = mtm.calc_op(cleaned)
    if op_word is not None:
        calc_op: Literal["simplify", "differentiate", "integrate", "factor", "expand"] = (
            "differentiate" if op_word in {"differentiate", "derivative"} else "integrate"
        )
        if op_word == "simplify":
            calc_op = "simplify"
        elif op_word == "factor":
            calc_op = "factor"
        elif op_word == "expand":
            calc_op = "expand"
        tail = _calc_expr_tail(cleaned)
        expr = _strip_trailing_filler(tail) if tail is not None else cleaned
        integral_lower: str | None = None
        integral_upper: str | None = None
        if calc_op == "integrate":
            bounds = mtm.integral_bounds(expr)
            if bounds is not None:
                expr, integral_lower, integral_upper = bounds
        return MathIntent(
            kind="calculus",
            expr=expr,
            operation=calc_op,
            integral_lower=integral_lower,
            integral_upper=integral_upper,
        )

    limit_hit = mtm.parse_limit(cleaned)
    if limit_hit is not None:
        expr = _normalize_latex_expr(_strip_trailing_filler(limit_hit.expr)).replace("^", "**")
        limit_point = limit_hit.point.lstrip("\\")
        if expr:
            return MathIntent(
                kind="limit",
                expr=expr,
                variable=limit_hit.var,
                limit_point=limit_point,
                operation="limit",
            )

    series_hit = mtm.parse_series(cleaned)
    if series_hit is not None:
        expr = _normalize_latex_expr(
            _strip_series_prefix(_strip_trailing_filler(series_hit.expr))
        ).replace("^", "**")
        end = series_hit.end.lstrip("\\")
        if expr:
            return MathIntent(
                kind="series",
                expr=expr,
                variable=series_hit.var,
                series_start=series_hit.start,
                series_end=end,
                operation="series",
            )

    if "newton" in lower or "numerically" in lower or "root of" in lower:
        guess = _DEFAULT_NEWTON_GUESS
        text_for_eq = cleaned
        for label in (
            "starting at x0 =",
            "starting at x=",
            "starting at",
            "starting near",
            "initial guess of",
            "initial guess",
            "near x=",
            "near",
            "guess",
            "x0 =",
        ):
            idx = lower.find(label)
            if idx == -1:
                continue
            m = _NEWTON_NUM.search(cleaned, idx + len(label))
            if m:
                guess = float(m.group(0))
                # Guess clauses are almost always trailing — drop from the cue onward.
                text_for_eq = cleaned[:idx].rstrip()
                if text_for_eq.lower().endswith(" with"):
                    text_for_eq = text_for_eq[: -len(" with")].rstrip()
                break
        # Strip newton lead-in without poly regex — phrase prefixes only.
        for prefix in (
            "please use newton's method to find the root of ",
            "please use newton's method for ",
            "please use newton's method on ",
            "use newton's method to find the root of ",
            "use newton's method for ",
            "use newton's method on ",
            "newton's method for ",
            "newton's method on ",
            "newton's method to find the root of ",
            "please numerically solve ",
            "please numerically approximate ",
            "numerically solve ",
            "numerically approximate ",
            "please find the root of ",
            "find the root of ",
        ):
            if text_for_eq.lower().startswith(prefix):
                text_for_eq = text_for_eq[len(prefix) :].strip()
                break
        newton_pairs = math_service.try_extract_equations_from_text(text_for_eq)
        if newton_pairs:
            lhs, rhs = newton_pairs[0]
            rhs_is_zero = rhs.strip() in ("0", "0.0")
            expr = lhs if rhs_is_zero else f"({lhs})-({rhs})"
            variables = math_service._guess_variables(f"{lhs} {rhs}")
            var = variables[0] if variables else "x"
            return MathIntent(
                kind="numerical_method",
                expr=expr,
                variable=var,
                newton_guess=float(guess),
                operation="newton",
            )

    eq_pairs = math_service.try_extract_equations_from_text(cleaned)
    if len(eq_pairs) >= 2:
        # BUG FIX (most severe correctness bug found in the audit): this
        # used to fall through to the single-equation branch below, which
        # only ever looked at the FIRST clause and answered with the same
        # "verified, do NOT recompute" confidence as a fully correct
        # response — silently discarding every other equation in the system.
        all_text = " ".join(f"{lhs} {rhs}" for lhs, rhs in eq_pairs)
        variables = math_service._guess_variables(all_text)
        return MathIntent(
            kind="system",
            system_equations=eq_pairs[:4],
            system_variables=variables,
            operation="solve",
        )
    if len(eq_pairs) == 1:
        lhs, rhs = eq_pairs[0]
        variables = math_service._guess_variables(lhs + rhs)
        return MathIntent(
            kind="equation",
            lhs=lhs,
            rhs=rhs,
            operation="solve",
            variable=variables[0] if variables else "x",
        )

    # Inequality — only reached when a math keyword already matched (this
    # function is called solely from needs_symbolic_math-gated paths), so bare
    # < / > here is safe from prose false-positives like "less than 5 minutes".
    ineq = math_service.try_extract_inequality_from_text(cleaned)
    if ineq:
        lhs, rhs, comparator = ineq
        variables = math_service._guess_variables(lhs + rhs)
        return MathIntent(
            kind="inequality",
            lhs=lhs,
            rhs=rhs,
            comparator=comparator,
            operation="solve",
            variable=variables[0] if variables else "x",
        )

    return None


@dataclass(frozen=True)
class VerifiedMathBlock:
    """The system-prompt hint text plus the exact fence (if any) it asked
    the model to reuse verbatim — canonical_fence lets a post-stream check
    correct the model's actual output rather than only trusting compliance."""

    text: str
    canonical_fence: dict[str, Any] | None = None


def _build_verified_block(intent: MathIntent, settings: Settings) -> VerifiedMathBlock | None:
    lines: list[str] = [
        "Symbolic math results (verified by SymPy — use these exact values in your answer):"
    ]

    try:
        if intent.kind == "equation" and intent.lhs and intent.rhs:
            eq = EquationInput(
                lhs=intent.lhs[: settings.math_max_expr_length],
                rhs=intent.rhs[: settings.math_max_expr_length],
                variables=[intent.variable],
            )
            result = math_service.solve_equation(eq)
            lines.extend(result.steps)
            lines.append(
                "Formula shape: INLINE $...$ for every step (never backticks around "
                "`$...$`; never ```math for step equations — those stream blank). "
                "A ```math fence is OK only for a standalone final display equation. "
                "Do NOT recompute the solutions. Show worked steps by COPYING the "
                "verified steps above verbatim — do NOT derive intermediate algebra "
                "yourself. Keep any spacing (e.g. \\quad) INSIDE the $...$ delimiters."
            )
            return VerifiedMathBlock(text="\n".join(lines))

        if intent.kind == "inequality" and intent.lhs and intent.rhs and intent.comparator:
            result = math_service.solve_inequality(
                intent.lhs[: settings.math_max_expr_length],
                intent.rhs[: settings.math_max_expr_length],
                intent.variable,
                intent.comparator,
            )
            lines.extend(result.steps)
            lines.append(
                "Formula shape: INLINE $...$ for the inequality and its solution "
                "set (never backticks around `$...$`). Do NOT recompute — copy the "
                "verified solution above verbatim. Render unions with \\lor "
                "(e.g. $x < -1 \\lor x > 1$) exactly as given."
            )
            return VerifiedMathBlock(text="\n".join(lines))

        if intent.kind == "system" and intent.system_equations:
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
            lines.append(
                "Formula shape: INLINE $...$ for every step (never backticks around "
                "`$...$`; never ```math for step equations). Do NOT recompute the "
                "solutions. Show worked steps by COPYING the verified steps above "
                "verbatim — do NOT derive intermediate algebra yourself."
            )
            return VerifiedMathBlock(text="\n".join(lines))

        if intent.kind == "numerical_method" and intent.expr and intent.newton_guess is not None:
            newton_input = NewtonMethodInput(
                expr=intent.expr[: settings.math_max_expr_length],
                variable=intent.variable,
                initial_guess=intent.newton_guess,
            )
            newton_result = math_service.newton_method(newton_input)
            lines.append(
                f"Newton's method for {newton_input.expr} = 0, x0 = {newton_input.initial_guess}:"
            )
            for step in newton_result.iterations:
                lines.append(f"  n={step.n}: x_{step.n} = {step.x_n}, f(x_{step.n}) = {step.f_x_n}")
            if newton_result.converged:
                lines.append(
                    f"Converged after {newton_result.iterations_used} iterations: root ≈ {newton_result.root}"
                )
            else:
                lines.append(
                    f"Did not converge within {newton_result.iterations_used} iterations "
                    "(the derivative may have vanished, or more iterations are needed) — "
                    "do NOT present a root as found."
                )
            lines.append(
                "Do NOT recompute or invent different iteration values. Show the "
                "worked steps by COPYING the verified iteration table above verbatim."
            )
            return VerifiedMathBlock(text="\n".join(lines))

        if intent.kind == "rectangle" and intent.width and intent.height:
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
            show_diagonal = (
                intent.wants_diagonal or intent.wants_angle or not (show_area or show_perimeter)
            )
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
                diagonal=rect_geo.diagonal,
                angle_deg=rect_geo.angle_deg,
                area=rect_geo.area,
                perimeter=rect_geo.perimeter,
                labels=rect_geo.labels,
            )
            lines.append(
                "When a diagram helps, emit ONLY this fence (adjust labels if needed):\n"
                f"```geometry\n{json.dumps(spec.model_dump(), separators=(',', ':'))}\n```"
            )
            lines.append("Do NOT recompute diagonal, angle, area, or perimeter.")
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=spec.model_dump())

        if intent.kind == "square" and (intent.side or intent.width):
            side = intent.side or intent.width or 5
            square_geo = math_service.square_geometry(
                SquareGeometryInput(side=side, unit=intent.unit)
            )
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
                diagonal=square_geo.diagonal,
                area=square_geo.area,
                perimeter=square_geo.perimeter,
                labels=square_geo.labels,
            )
            lines.append(
                "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
                f"```geometry\n{json.dumps(spec.model_dump(), separators=(',', ':'))}\n```"
            )
            lines.append("Do NOT recompute diagonal, area, or perimeter.")
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=spec.model_dump())

        if intent.kind == "circle" and intent.radius:
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
                f"```geometry\n{json.dumps(circle_spec.model_dump(), separators=(',', ':'))}\n```"
            )
            lines.append("Do NOT recompute diameter, area, or circumference.")
            return VerifiedMathBlock(
                text="\n".join(lines), canonical_fence=circle_spec.model_dump()
            )

        if intent.kind == "triangle" and intent.base and intent.height:
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
                area=tri_geo.area,
                labels=tri_geo.labels,
            )
            lines.append(
                "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
                f"```geometry\n{json.dumps(tri_spec.model_dump(), separators=(',', ':'))}\n```"
            )
            lines.append("Do NOT recompute area.")
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=tri_spec.model_dump())

        if intent.kind == "right_triangle" and intent.base and intent.height:
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
                f"```geometry\n{json.dumps(rt_spec.model_dump(), separators=(',', ':'))}\n```"
            )
            lines.append("Do NOT recompute hypotenuse or area.")
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=rt_spec.model_dump())

        if intent.kind == "point" and intent.point_x is not None and intent.point_y is not None:
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
                f"```graph\n{json.dumps(point_spec.model_dump(), separators=(',', ':'))}\n```"
            )
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=point_spec.model_dump())

        if intent.kind == "vertical" and intent.point_x is not None:
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
                f"```graph\n{json.dumps(vert_spec.model_dump(), separators=(',', ':'))}\n```"
            )
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=vert_spec.model_dump())

        if intent.kind == "graph" and intent.expr:
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
                f"```graph\n{json.dumps(graph_spec.model_dump(), separators=(',', ':'))}\n```"
            )
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=graph_spec.model_dump())

        if intent.kind == "calculus" and intent.expr and intent.operation:
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
            lines.append("Do NOT recompute. Explain in plain language with $...$ for formulas.")
            return VerifiedMathBlock(text="\n".join(lines))

        if intent.kind == "limit" and intent.expr and intent.limit_point is not None:
            limit_out = math_service.compute_limit(intent.expr, intent.variable, intent.limit_point)
            lines.append(f"Result: {limit_out.latex}")
            if limit_out.is_infinite:
                lines.append(
                    "This limit is infinite (or does not exist as a finite two-sided "
                    "value) — render it as \\infty, do not treat it as an ordinary "
                    "finite number."
                )
            lines.append("Do NOT recompute. Explain in plain language with $...$ for formulas.")
            return VerifiedMathBlock(text="\n".join(lines))

        if (
            intent.kind == "series"
            and intent.expr
            and intent.series_start is not None
            and intent.series_end is not None
        ):
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
            lines.append("Do NOT recompute. Explain in plain language with $...$ for formulas.")
            return VerifiedMathBlock(text="\n".join(lines))
    except math_service.MathServiceError as exc:
        logger.info("math_tools skipped: %s", exc)
        return None
    except Exception:
        logger.exception("math_tools failed")
        return None

    return None


def _inject_before_last_user(messages: list[dict[str, str]], block: str) -> list[dict[str, str]]:
    augmented = list(messages)
    insert_at = len(augmented)
    for index in range(len(augmented) - 1, -1, -1):
        if augmented[index].get("role") == "user":
            insert_at = index
            break
    augmented.insert(insert_at, {"role": "system", "content": block})
    return augmented


async def augment_prompt_messages(
    messages: list[dict[str, str]],
    user_content: str,
    settings: Settings,
    *,
    has_image_attachment: bool = False,
    image_math_extract: MathImageExtract | None = None,
) -> tuple[list[dict[str, str]], VerifiedMathBlock | None]:
    if not settings.math_tools_enabled:
        return messages, None
    if not needs_symbolic_math(user_content, has_image_attachment=has_image_attachment):
        return messages, None

    if image_math_extract is not None:
        # OCR already produced a Pydantic-validated equation — use it directly
        # instead of re-parsing the stringified "lhs = rhs" text back through
        # try_extract_equations_from_text's restricted character-class regex,
        # which mangles unicode symbols, commas, and abs-value bars a real
        # photographed equation can contain. variables always has >=1 entry
        # (schema default_factory=["x"]), so this is the model's best guess
        # even when the image genuinely used "x".
        intent: MathIntent | None = MathIntent(
            kind="equation",
            lhs=image_math_extract.lhs,
            rhs=image_math_extract.rhs,
            operation="solve",
            variable=image_math_extract.variables[0],
        )
    else:
        intent = extract_math_intent(user_content)
    if intent is None and has_image_attachment:
        lines = [
            "The user attached an image that may contain a math problem. "
            "Extract the equation as lhs/rhs if possible, then explain using verified reasoning. "
            "Use $...$ for formulas and ```geometry / ```graph JSON fences for diagrams."
        ]
        return _inject_before_last_user(messages, "\n".join(lines)), None

    if intent is None:
        return messages, None

    verified = await _build_verified_block_async(intent, settings)
    if not verified:
        return messages, None
    return _inject_before_last_user(messages, verified.text), verified


async def _build_verified_block_async(
    intent: MathIntent, settings: Settings
) -> VerifiedMathBlock | None:
    """Run the sync, CPU-bound SymPy work in a bounded subprocess with a
    hard timeout + SIGTERM on timeout.

    ``_build_verified_block`` calls into SymPy's ``solve``/``integrate``/etc.,
    which are synchronous and can take arbitrarily long on a pathological
    expression. Running them on the shared default ``asyncio.to_thread`` pool
    would (a) starve unrelated async work and (b) leak the thread on timeout
    (the await cancels but the thread keeps running). The bounded
    ``ProcessPoolExecutor`` isolates SymPy to a single subprocess that can be
    hard-killed on timeout.
    """
    from app.services.sympy_executor import run_sympy

    try:
        return await run_sympy(
            _build_verified_block,
            intent,
            settings,
            timeout=settings.math_solve_timeout_seconds,
        )
    except TimeoutError:
        logger.warning(
            "math_tools solve timed out after %ss for kind=%s",
            settings.math_solve_timeout_seconds,
            intent.kind,
        )
        return None
