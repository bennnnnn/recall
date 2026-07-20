"""Pre-stream symbolic math augmentation for chat prompts."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import Settings
from app.models.math_schemas import (
    CircleGeometryBlockSpec,
    CircleGeometryInput,
    CombinatoricsInput,
    EquationInput,
    GeometryBlockSpec,
    GraphBlockSpec,
    GraphSampleInput,
    MathImageExtract,
    MathIntent,
    MatrixInput,
    NewtonMethodInput,
    NumberTheoryInput,
    ParallelogramGeometryBlockSpec,
    ParallelogramInput,
    RectangleGeometryInput,
    RightTriangleGeometryBlockSpec,
    RightTriangleGeometryInput,
    SectorGeometryBlockSpec,
    SectorInput,
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
from app.services.prompt_inject import inject_before_last_user
from app.services.text_normalize import collapse_ws

logger = logging.getLogger(__name__)


# Cap before any poly-time regex. CodeQL only treats a const length compare as a
# ReDoS sanitizer — collapsing whitespace alone is not enough.
_MAX_MATH_INPUT = 1000


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
    s = collapse_ws(expr)
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
    s = collapse_ws(expr)
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


def _parse_newton_guess(cleaned: str) -> tuple[float, str]:
    """Return ``(guess, text_for_eq)`` after stripping a trailing guess clause."""
    guess = _DEFAULT_NEWTON_GUESS
    text_for_eq = cleaned
    lower = cleaned.lower()
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
    return guess, text_for_eq


def _strip_newton_leadin(text_for_eq: str) -> str:
    """Strip newton lead-in without poly regex — phrase prefixes only."""
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
            return text_for_eq[len(prefix) :].strip()
    return text_for_eq


def _extract_rectangle_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

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
    return None


def _extract_square_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    lower = cleaned.lower()
    if "square" not in lower:
        return None
    dims = mtm.first_dim_pair(cleaned)
    side = mtm.number_after(cleaned, "side") or mtm.number_after(cleaned, "edge")
    if side is None and dims is not None and dims[0] == dims[1]:
        side = dims[0]
    if side is not None:
        return MathIntent(
            kind="square", side=side, width=side, height=side, unit="cm", operation="solve"
        )
    return MathIntent(kind="square", side=5, width=5, height=5, unit="cm", operation="solve")


def _extract_circle_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    lower = cleaned.lower()
    if "circle" not in lower:
        return None
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


def _extract_right_triangle_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    lower = cleaned.lower()
    if "right triangle" not in lower:
        return None
    dims = mtm.first_dim_pair(cleaned)
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


def _extract_triangle_sides_intent(cleaned: str) -> MathIntent | None:
    """Checked BEFORE the generic base+height triangle extractor below — a
    "triangle with sides 3, 4, 5" mention must not fall into that extractor's
    broad "triangle" + "area"/"draw"/... fallback and get the wrong (default
    base=8, height=5) shape instead of the SSS one actually named."""
    from app.services import math_text_match as mtm

    sides = mtm.triangle_sides_signal(cleaned)
    if sides is None:
        return None
    a, b, c = sides
    return MathIntent(
        kind="triangle_sides", tri_a=a, tri_b=b, tri_c=c, unit="cm", operation="solve"
    )


def _extract_trapezoid_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    lower = cleaned.lower()
    if "trapezoid" not in lower and "trapezium" not in lower:
        return None
    top = mtm.number_after(cleaned, "top")
    bottom = mtm.number_after(cleaned, "bottom")
    height = mtm.number_after(cleaned, "height")
    return MathIntent(
        kind="trapezoid",
        trapezoid_top=top if top is not None else 4,
        trapezoid_bottom=bottom if bottom is not None else 8,
        height=height if height is not None else 5,
        unit="cm",
        operation="solve",
    )


def _extract_parallelogram_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    if "parallelogram" not in cleaned.lower():
        return None
    base = mtm.number_after(cleaned, "base")
    height = mtm.number_after(cleaned, "height")
    side = mtm.number_after(cleaned, "side")
    return MathIntent(
        kind="parallelogram",
        base=base if base is not None else 8,
        height=height if height is not None else 4,
        side=side if side is not None else 5,
        unit="cm",
        operation="solve",
    )


def _extract_sector_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    lower = cleaned.lower()
    if "sector" not in lower and "pie slice" not in lower:
        return None
    if "sector" in lower and not any(k in lower for k in ("circle", "radius", "pie", "arc")):
        return None
    radius = mtm.number_after(cleaned, "radius")
    angle = mtm.number_after(cleaned, "angle")
    return MathIntent(
        kind="sector",
        radius=radius if radius is not None else 5,
        sector_angle_deg=angle if angle is not None else 90,
        unit="cm",
        operation="solve",
    )


def _extract_triangle_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    lower = cleaned.lower()
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
    return None


def _extract_point_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    point = mtm.bare_coord(cleaned) or mtm.plot_point(cleaned)
    if point is None:
        return None
    return MathIntent(
        kind="point",
        point_x=point[0],
        point_y=point[1],
        operation="graph",
    )


def _extract_vertical_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    vert_x = mtm.vertical_line_x(cleaned)
    if vert_x is None:
        return None
    return MathIntent(kind="vertical", point_x=vert_x, operation="graph")


def _extract_graph_pair_intent(cleaned: str) -> MathIntent | None:
    """Checked BEFORE the single-expression graph extractor below — "graph
    y=x^2 and y=2x" must not fall into graph_expr's single-capture, which
    would grab "x^2 and y=2x" as one unparseable expr and silently produce
    no augmentation for a very ordinary "compare these two functions" ask."""
    from app.services import math_text_match as mtm

    pair = mtm.graph_expr_pair(cleaned)
    if pair is None:
        return None
    first, second = pair
    expr1 = _strip_trailing_filler(first).replace("^", "**")
    expr2 = _strip_trailing_filler(second).replace("^", "**")
    if not expr1 or not expr2:
        return None
    return MathIntent(kind="graph_pair", expr=expr1, expr2=expr2, operation="graph")


def _extract_graph_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    g_expr = mtm.graph_expr(cleaned)
    if g_expr is None:
        return None
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


def _extract_calculus_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    op_word = mtm.calc_op(cleaned)
    if op_word is None:
        return None
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


def _extract_limit_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    limit_hit = mtm.parse_limit(cleaned)
    if limit_hit is None:
        return None
    expr = _normalize_latex_expr(_strip_trailing_filler(limit_hit.expr)).replace("^", "**")
    limit_point = limit_hit.point.lstrip("\\")
    if not expr:
        return None
    return MathIntent(
        kind="limit",
        expr=expr,
        variable=limit_hit.var,
        limit_point=limit_point,
        operation="limit",
    )


def _extract_series_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    series_hit = mtm.parse_series(cleaned)
    if series_hit is None:
        return None
    expr = _normalize_latex_expr(
        _strip_series_prefix(_strip_trailing_filler(series_hit.expr))
    ).replace("^", "**")
    end = series_hit.end.lstrip("\\")
    if not expr:
        return None
    return MathIntent(
        kind="series",
        expr=expr,
        variable=series_hit.var,
        series_start=series_hit.start,
        series_end=end,
        operation="series",
    )


def _extract_numerical_method_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not ("newton" in lower or "numerically" in lower or "root of" in lower):
        return None
    guess, text_for_eq = _parse_newton_guess(cleaned)
    text_for_eq = _strip_newton_leadin(text_for_eq)
    newton_pairs = math_service.try_extract_equations_from_text(text_for_eq)
    if not newton_pairs:
        return None
    lhs, rhs = newton_pairs[0]
    rhs_is_zero = rhs.strip() in ("0", "0.0")
    expr = lhs if rhs_is_zero else f"({lhs})-({rhs})"
    variables = math_service.guess_variables(f"{lhs} {rhs}")
    var = variables[0] if variables else "x"
    return MathIntent(
        kind="numerical_method",
        expr=expr,
        variable=var,
        newton_guess=float(guess),
        operation="newton",
    )


def _extract_statistics_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    signal = mtm.stats_signal(cleaned)
    if signal is None:
        return None
    op, numbers = signal
    return MathIntent(kind="statistics", stats_op=op, stats_numbers=numbers, operation="solve")


def _extract_combinatorics_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    signal = mtm.combinatorics_signal(cleaned)
    if signal is None:
        return None
    op, n, k = signal
    return MathIntent(kind="combinatorics", combo_op=op, combo_n=n, combo_k=k, operation="solve")


def _extract_number_theory_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    signal = mtm.number_theory_signal(cleaned)
    if signal is None:
        return None
    op, a, b = signal
    return MathIntent(
        kind="number_theory", numtheory_op=op, numtheory_a=a, numtheory_b=b, operation="solve"
    )


def _extract_matrix_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    signal = mtm.matrix_signal(cleaned)
    if signal is None:
        return None
    op, rows = signal
    return MathIntent(kind="matrix", matrix_op=op, matrix_rows=rows, operation="solve")


def _extract_system_intent(cleaned: str) -> MathIntent | None:
    eq_pairs = math_service.try_extract_equations_from_text(cleaned)
    if len(eq_pairs) < 2:
        return None
    # BUG FIX (most severe correctness bug found in the audit): this
    # used to fall through to the single-equation branch below, which
    # only ever looked at the FIRST clause and answered with the same
    # "verified, do NOT recompute" confidence as a fully correct
    # response — silently discarding every other equation in the system.
    all_text = " ".join(f"{lhs} {rhs}" for lhs, rhs in eq_pairs)
    variables = math_service.guess_variables(all_text)
    return MathIntent(
        kind="system",
        system_equations=eq_pairs[:4],
        system_variables=variables,
        operation="solve",
    )


def _extract_equation_intent(cleaned: str) -> MathIntent | None:
    eq_pairs = math_service.try_extract_equations_from_text(cleaned)
    if len(eq_pairs) != 1:
        return None
    lhs, rhs = eq_pairs[0]
    variables = math_service.guess_variables(lhs + rhs)
    return MathIntent(
        kind="equation",
        lhs=lhs,
        rhs=rhs,
        operation="solve",
        variable=variables[0] if variables else "x",
    )


def _extract_inequality_intent(cleaned: str) -> MathIntent | None:
    # Inequality — only reached when a math keyword already matched (this
    # function is called solely from needs_symbolic_math-gated paths), so bare
    # < / > here is safe from prose false-positives like "less than 5 minutes".
    ineq = math_service.try_extract_inequality_from_text(cleaned)
    if not ineq:
        return None
    lhs, rhs, comparator = ineq
    variables = math_service.guess_variables(lhs + rhs)
    return MathIntent(
        kind="inequality",
        lhs=lhs,
        rhs=rhs,
        comparator=comparator,
        operation="solve",
        variable=variables[0] if variables else "x",
    )


_INTENT_EXTRACTORS: Sequence[Callable[[str], MathIntent | None]] = (
    _extract_rectangle_intent,
    _extract_square_intent,
    # Sector before the generic circle extractor: a sector mention almost
    # always also says "circle" ("sector of a circle with radius 5"), which
    # would otherwise satisfy the plain circle extractor first and steal it.
    _extract_sector_intent,
    _extract_circle_intent,
    _extract_trapezoid_intent,
    _extract_parallelogram_intent,
    _extract_right_triangle_intent,
    _extract_triangle_sides_intent,
    _extract_triangle_intent,
    _extract_point_intent,
    _extract_vertical_intent,
    _extract_graph_pair_intent,
    _extract_graph_intent,
    _extract_calculus_intent,
    _extract_limit_intent,
    _extract_series_intent,
    _extract_numerical_method_intent,
    _extract_statistics_intent,
    _extract_combinatorics_intent,
    _extract_number_theory_intent,
    _extract_matrix_intent,
    _extract_system_intent,
    _extract_equation_intent,
    _extract_inequality_intent,
)


def extract_math_intent(text: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    cleaned = mtm.prepare(text)
    if not cleaned:
        return None

    for extractor in _INTENT_EXTRACTORS:
        intent = extractor(cleaned)
        if intent is not None:
            return intent
    return None


@dataclass(frozen=True)
class VerifiedMathBlock:
    """The system-prompt hint text plus the exact fence (if any) it asked
    the model to reuse verbatim — canonical_fence lets a post-stream check
    correct the model's actual output rather than only trusting compliance."""

    text: str
    canonical_fence: dict[str, Any] | None = None


def _fence(kind: str, spec: Any) -> str:
    return f"```{kind}\n{json.dumps(spec.model_dump(), separators=(',', ':'))}\n```"


def _answer_canonical(content: str) -> dict[str, str]:
    return {"type": "answer", "content": content}


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
    result = math_service.solve_inequality(
        intent.lhs[: settings.math_max_expr_length],
        intent.rhs[: settings.math_max_expr_length],
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
    return VerifiedMathBlock(text="\n".join(lines), canonical_fence=spec.model_dump())


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
        diagonal=square_geo.diagonal,
        area=square_geo.area,
        perimeter=square_geo.perimeter,
        labels=square_geo.labels,
    )
    lines.append(
        f"When a diagram helps, emit ONLY this fence (NEVER ```json):\n{_fence('geometry', spec)}"
    )
    lines.append("Do NOT recompute diagonal, area, or perimeter.")
    return VerifiedMathBlock(text="\n".join(lines), canonical_fence=spec.model_dump())


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
    return VerifiedMathBlock(text="\n".join(lines), canonical_fence=circle_spec.model_dump())


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
        area=tri_geo.area,
        labels=tri_geo.labels,
    )
    lines.append(
        "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
        f"{_fence('geometry', tri_spec)}"
    )
    lines.append("Do NOT recompute area.")
    return VerifiedMathBlock(text="\n".join(lines), canonical_fence=tri_spec.model_dump())


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
    return VerifiedMathBlock(text="\n".join(lines), canonical_fence=rt_spec.model_dump())


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
    tri_spec = TriangleSidesGeometryBlockSpec(
        type="triangle_sides",
        a=tri_geo.a,
        b=tri_geo.b,
        c=tri_geo.c,
        unit=tri_geo.unit,
        show_labels=True,
        area=tri_geo.area,
        labels=tri_geo.labels,
    )
    lines.append(
        "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
        f"{_fence('geometry', tri_spec)}"
    )
    lines.append(
        "Do NOT recompute area, perimeter, or angles — this is Heron's formula + the law of cosines."
    )
    return VerifiedMathBlock(text="\n".join(lines), canonical_fence=tri_spec.model_dump())


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
        f"Trapezoid: top={trap_geo.top:g} {trap_geo.unit} bottom={trap_geo.bottom:g} {trap_geo.unit} "
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
    return VerifiedMathBlock(text="\n".join(lines), canonical_fence=trap_spec.model_dump())


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
    return VerifiedMathBlock(text="\n".join(lines), canonical_fence=para_spec.model_dump())


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
    return VerifiedMathBlock(text="\n".join(lines), canonical_fence=sector_spec.model_dump())


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
    return VerifiedMathBlock(text="\n".join(lines), canonical_fence=point_spec.model_dump())


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
    return VerifiedMathBlock(text="\n".join(lines), canonical_fence=vert_spec.model_dump())


def _verified_block_graph(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not intent.expr:
        return None
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
    return VerifiedMathBlock(text="\n".join(lines), canonical_fence=graph_spec.model_dump())


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
    return VerifiedMathBlock(text="\n".join(lines), canonical_fence=graph_spec.model_dump())


def _verified_block_calculus(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.operation):
        return None
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
    lines.append("Do NOT recompute. Explain in plain language with $...$ for formulas.")
    return VerifiedMathBlock(text="\n".join(lines))


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
    lines.append("Do NOT recompute. Explain in plain language with $...$ for formulas.")
    return VerifiedMathBlock(text="\n".join(lines))


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
    lines.append(
        "Do NOT recompute any of these values — use the verified numbers above. Show "
        "the relevant formula (e.g. mean = sum / count) with these exact numbers substituted in."
    )
    return VerifiedMathBlock(text="\n".join(lines))


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
    lines.append("Do NOT recompute — use this exact verified result.")
    return VerifiedMathBlock(text="\n".join(lines))


def _verified_block_number_theory(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.numtheory_op is None or intent.numtheory_a is None:
        return None
    result = math_service.compute_number_theory(
        NumberTheoryInput(operation=intent.numtheory_op, a=intent.numtheory_a, b=intent.numtheory_b)
    )
    lines.extend(result.steps)
    lines.append("Do NOT recompute — use this exact verified result.")
    return VerifiedMathBlock(text="\n".join(lines))


def _verified_block_matrix(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.matrix_op is None or not intent.matrix_rows:
        return None
    result = math_service.compute_matrix(
        MatrixInput(operation=intent.matrix_op, rows=intent.matrix_rows)
    )
    lines.extend(result.steps)
    lines.append("Do NOT recompute — use this exact verified result.")
    return VerifiedMathBlock(text="\n".join(lines))


_BlockBuilder = Callable[[MathIntent, Settings, list[str]], VerifiedMathBlock | None]

_BLOCK_BUILDERS: dict[str, _BlockBuilder] = {
    "equation": _verified_block_equation,
    "inequality": _verified_block_inequality,
    "system": _verified_block_system,
    "numerical_method": _verified_block_numerical_method,
    "rectangle": _verified_block_rectangle,
    "square": _verified_block_square,
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
            return None
        return builder(intent, settings, lines)
    except math_service.MathServiceError as exc:
        logger.info("math_tools skipped: %s", exc)
        return None
    except Exception:
        logger.exception("math_tools failed")
        return None


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
        #
        # kind branches beyond the single-equation case (system/inequality)
        # so a photographed system or inequality gets the same SymPy-verified
        # path a single equation already did — previously ANY photo with more
        # than one equation (or a bare inequality) silently fell back to
        # unverified free-text, regardless of how well the OCR itself worked.
        if image_math_extract.kind == "system" and image_math_extract.equations:
            intent: MathIntent | None = MathIntent(
                kind="system",
                system_equations=image_math_extract.equations[:4],
                system_variables=image_math_extract.variables,
                operation="solve",
            )
        elif image_math_extract.kind == "inequality" and image_math_extract.comparator:
            intent = MathIntent(
                kind="inequality",
                lhs=image_math_extract.lhs,
                rhs=image_math_extract.rhs,
                comparator=image_math_extract.comparator,
                operation="solve",
                variable=image_math_extract.variables[0],
            )
        else:
            intent = MathIntent(
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
        return inject_before_last_user(messages, "\n".join(lines)), None

    if intent is None:
        return messages, None

    verified = await _build_verified_block_async(intent, settings)
    if not verified:
        return messages, None
    return inject_before_last_user(messages, verified.text), verified


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
