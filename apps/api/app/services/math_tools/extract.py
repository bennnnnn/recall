"""Ordered MathIntent extractors. Registry: _INTENT_EXTRACTORS."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from typing import Literal

from app.models.math_schemas import (
    MathIntent,
)
from app.services import math_service
from app.services.math_tools.helpers import (
    _calc_expr_tail,
    _normalize_latex_expr,
    _parse_newton_guess,
    _strip_newton_leadin,
    _strip_series_prefix,
    _strip_trailing_filler,
)
from app.services.math_tools.school import SCHOOL_EXTRACTORS

logger = logging.getLogger(__name__)


# "solve for y", "find y", "find the value of y", "solve y in …" — the user
# names the variable to isolate. Without this, _extract_equation_intent
# fell back to guess_variables(...)[0] (alphabetical first), so "Solve for
# y: x+y=5" solved for x and returned the wrong answer in the verified card.
# The captured letter must not be part of a longer word (lookahead rejects
# "find the roots" → 't' of "the"), and we only honor it when the letter
# actually appears in the equation.
_SOLVE_FOR_VAR_RE = re.compile(
    r"(?:solve\s+for|find|solve)\s+(?:the\s+value\s+of\s+)?([a-zA-Z])(?![a-zA-Z])",
    re.IGNORECASE,
)

# English lead-in words the equation parser leaves in the LHS ("for y in
# x+y" stays as-is). Strip them before guessing variables so they don't
# crowd out the real single-letter variable. Only multi-letter words are
# stripped — single letters are never removed (they may be variables).
_LEADIN_WORDS = frozenset(
    {
        "solve",
        "for",
        "find",
        "the",
        "value",
        "of",
        "in",
        "when",
        "given",
        "if",
        "such",
        "that",
        "where",
        "with",
        "please",
        "let",
        "us",
        "determine",
        "calculate",
        "compute",
        "get",
        "isolate",
        "express",
        "what",
        "is",
        "are",
        "does",
        "can",
        "you",
        "show",
        "tell",
    }
)


def _requested_variable(cleaned: str, equation_text: str) -> str | None:
    """Return the variable the user explicitly asked to solve for, or None."""
    m = _SOLVE_FOR_VAR_RE.search(cleaned)
    if m is None:
        return None
    var = m.group(1)
    tokens = re.findall(r"[a-zA-Z]+", equation_text)
    kept = [t for t in tokens if t.lower() not in _LEADIN_WORDS]
    letters = {c for t in kept for c in t if c.isalpha()}
    letters.discard("e")
    letters.discard("E")
    return var if var in letters else None


def _wants_geometry_angles(lower: str) -> bool:
    return any(w in lower for w in ("angle", "angles", "degree", "degrees"))


def _extract_solid_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    parsed = mtm.parse_solid(cleaned)
    if parsed is None:
        return None
    return MathIntent(
        kind="solid",
        solid_shape=parsed.shape,
        width=parsed.width,
        height=parsed.height,
        depth=parsed.depth,
        side=parsed.side,
        radius=parsed.radius,
        unit=parsed.unit,
        operation="solve",
        wants_volume=parsed.wants_volume,
        wants_surface_area=parsed.wants_surface_area,
    )


def _extract_rectangle_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    lower = cleaned.lower()
    if mtm.classify_solid_shape(lower) is not None:
        return None
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
    if mtm.classify_solid_shape(lower) is not None:
        return None
    if "square" not in lower:
        return None
    # Algebraic uses of the word "square" must not become a geometry diagram.
    # BUG FIX: "solve square root of x = 4" / "graph the square root" used to
    # match here (substring "square") and inject a default 5 cm square.
    if any(
        phrase in lower
        for phrase in (
            "square root",
            "perfect square",
            "squared",
            "squares to",
            "square of",
        )
    ):
        return None
    dims = mtm.first_dim_pair(cleaned)
    side = mtm.number_after(cleaned, "side") or mtm.number_after(cleaned, "edge")
    if side is None and dims is not None and dims[0] == dims[1]:
        side = dims[0]
    if side is not None:
        return MathIntent(
            kind="square", side=side, width=side, height=side, unit="cm", operation="solve"
        )
    # Default dimensions only when the user asked to draw/show the shape —
    # never invent a square for bare prose that merely contains "square".
    if mtm.has_draw_shape(lower, "square"):
        return MathIntent(kind="square", side=5, width=5, height=5, unit="cm", operation="solve")
    return None


def _extract_circle_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    lower = cleaned.lower()
    if mtm.classify_solid_shape(lower) is not None:
        return None
    if "circle" not in lower:
        return None
    # Sector mentions almost always include "circle" + "radius" — leave those
    # to `_extract_sector_intent` (which runs first). Without this guard a
    # partial sector cue ("sector … radius 5") becomes a plain circle fence.
    if "sector" in lower or "pie slice" in lower:
        return None
    # Algebra / unit-circle asks still contain "circle" (and often "radius") —
    # do not steal them from equation/graph extractors that run later.
    if mtm.geometry_deferred_for_algebra(lower):
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
    # Default radius only on an explicit draw/show/sketch — never invent a
    # 5 cm circle for "what is a circle?" / "unit circle" / algebra that
    # merely mentions the word (those used to ship as SymPy-verified).
    if mtm.has_draw_shape(lower, "circle"):
        return MathIntent(
            kind="circle",
            radius=5,
            unit="cm",
            operation="solve",
            wants_area=wants_area,
            wants_circumference=wants_circumference,
        )
    return None


def _extract_right_triangle_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    lower = cleaned.lower()
    if "right triangle" not in lower:
        return None
    if mtm.geometry_deferred_for_algebra(lower):
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
            wants_angle=_wants_geometry_angles(lower),
        )
    if mtm.has_draw_shape(lower, "right triangle"):
        return MathIntent(
            kind="right_triangle",
            base=6,
            height=4,
            unit="cm",
            operation="solve",
            wants_angle=_wants_geometry_angles(lower),
        )
    return None


def _extract_triangle_sides_intent(cleaned: str) -> MathIntent | None:
    """Checked BEFORE the generic base+height triangle extractor below — a
    "triangle with sides 3, 4, 5" mention must not fall into that extractor's
    broad "triangle" + "area"/"draw"/... fallback and get the wrong (default
    base=8, height=5) shape instead of the SSS one actually named."""
    from app.services import math_text_match as mtm

    if mtm.geometry_deferred_for_algebra(cleaned.lower()):
        return None
    sides = mtm.triangle_sides_signal(cleaned)
    if sides is None:
        return None
    a, b, c = sides
    return MathIntent(
        kind="triangle_sides",
        tri_a=a,
        tri_b=b,
        tri_c=c,
        unit="cm",
        operation="solve",
        wants_angle=_wants_geometry_angles(cleaned.lower()),
    )


def _extract_trapezoid_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    lower = cleaned.lower()
    if "trapezoid" not in lower and "trapezium" not in lower:
        return None
    if mtm.geometry_deferred_for_algebra(lower):
        return None
    top = mtm.number_after(cleaned, "top")
    bottom = mtm.number_after(cleaned, "bottom")
    height = mtm.number_after(cleaned, "height")
    if top is not None and bottom is not None and height is not None:
        return MathIntent(
            kind="trapezoid",
            trapezoid_top=top,
            trapezoid_bottom=bottom,
            height=height,
            unit="cm",
            operation="solve",
            wants_angle=_wants_geometry_angles(lower),
        )
    shape = "trapezoid" if "trapezoid" in lower else "trapezium"
    if mtm.has_draw_shape(lower, shape):
        return MathIntent(
            kind="trapezoid",
            trapezoid_top=4,
            trapezoid_bottom=8,
            height=5,
            unit="cm",
            operation="solve",
            wants_angle=_wants_geometry_angles(lower),
        )
    return None


def _extract_parallelogram_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    lower = cleaned.lower()
    if "parallelogram" not in lower:
        return None
    if mtm.geometry_deferred_for_algebra(lower):
        return None
    base = mtm.number_after(cleaned, "base")
    height = mtm.number_after(cleaned, "height")
    side = mtm.number_after(cleaned, "side")
    if base is not None and height is not None:
        # Side is only needed for the slanted diagram. When the user gave
        # base+height (enough for area) but no side, use a right parallelogram
        # (side=height → zero shear) rather than inventing a fake slant length.
        return MathIntent(
            kind="parallelogram",
            base=base,
            height=height,
            side=side if side is not None else height,
            unit="cm",
            operation="solve",
            wants_angle=_wants_geometry_angles(lower),
        )
    if mtm.has_draw_shape(lower, "parallelogram"):
        return MathIntent(
            kind="parallelogram",
            base=8,
            height=4,
            side=5,
            unit="cm",
            operation="solve",
            wants_angle=_wants_geometry_angles(lower),
        )
    return None


def _extract_sector_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    lower = cleaned.lower()
    if "sector" not in lower and "pie slice" not in lower:
        return None
    if "sector" in lower and not any(k in lower for k in ("circle", "radius", "pie", "arc")):
        return None
    if mtm.geometry_deferred_for_algebra(lower):
        return None
    radius = mtm.number_after(cleaned, "radius")
    angle = mtm.number_after(cleaned, "angle")
    if radius is not None and angle is not None:
        return MathIntent(
            kind="sector",
            radius=radius,
            sector_angle_deg=angle,
            unit="cm",
            operation="solve",
        )
    # Defaults only when the user asked to draw the shape — never invent a
    # 90° / 5 cm sector for "sector of a circle with radius 5" alone.
    if mtm.has_draw_shape(lower, "sector") or mtm.has_draw_shape(lower, "pie slice"):
        return MathIntent(
            kind="sector",
            radius=radius if radius is not None else 5,
            sector_angle_deg=angle if angle is not None else 90,
            unit="cm",
            operation="solve",
        )
    return None


def _extract_triangle_angles_intent(cleaned: str) -> MathIntent | None:
    """AAA (and angle-sum) triangles — law of sines with relative side units.

    Must run before the generic draw-a-triangle default (base=8, height=5)
    so "triangle with 120, 40, 20" is not an invented isosceles.
    """
    from app.services import math_service
    from app.services import math_text_match as mtm

    if mtm.geometry_deferred_for_algebra(cleaned.lower()):
        return None
    angles = mtm.triangle_angles_signal(cleaned)
    if angles is None:
        return None
    try:
        side_a, side_b, side_c = math_service.sides_from_interior_angles(*angles)
    except math_service.MathServiceError:
        return None
    return MathIntent(
        kind="triangle_sides",
        tri_a=side_a,
        tri_b=side_b,
        tri_c=side_c,
        unit="units",
        operation="solve",
        wants_angle=True,
    )


def _extract_triangle_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    lower = cleaned.lower()
    if mtm.geometry_deferred_for_algebra(lower):
        return None
    base_n = mtm.number_after(cleaned, "base")
    height_n = mtm.number_after(cleaned, "height")
    if base_n is not None and height_n is not None and "triangle" in lower:
        return MathIntent(
            kind="triangle",
            base=base_n,
            height=height_n,
            unit="cm",
            operation="solve",
            wants_angle=_wants_geometry_angles(lower),
        )

    # "area of a triangle" is a definition question — do not invent base/height.
    # Defaults only for an explicit draw/show/sketch/visualize request.
    if mtm.has_draw_shape(lower, "triangle"):
        return MathIntent(
            kind="triangle",
            base=8,
            height=5,
            unit="cm",
            operation="solve",
            wants_angle=_wants_geometry_angles(lower),
        )
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


def _solve_for_y_as_function_of_x(expr: str) -> str | None:
    """Turn an equation like ``x=2y`` into the function ``x/2`` (y = f(x)).

    Returns the RHS as a SymPy-text string in terms of x, or None when the
    equation can't be isolated to a single y = f(x) (e.g. no y, multiple
    solutions, or y is not the dependent variable). ``y=x^2`` stays a plain
    expression already; this only rewires equations that contain ``=``.
    """
    if "=" not in expr:
        return None
    from sympy import Eq, Symbol, solve, sstr
    from sympy.core.relational import Relational

    from app.services.math_service.parse import _parse_expression

    lhs_str, _, rhs_str = expr.partition("=")
    lhs_str, rhs_str = lhs_str.strip(), rhs_str.strip()
    if not lhs_str or not rhs_str:
        return None
    # Only attempt when y is present (the dependent variable we solve for).
    if "y" not in lhs_str and "y" not in rhs_str:
        return None
    try:
        lhs = _parse_expression(lhs_str, ["x", "y"], real=True)
        rhs = _parse_expression(rhs_str, ["x", "y"], real=True)
    except Exception:
        return None
    if isinstance(lhs, Relational) or isinstance(rhs, Relational):
        return None
    y = Symbol("y", real=True)
    try:
        sols = solve(Eq(lhs, rhs), y, dict=True)
    except Exception:
        return None
    if not sols or len(sols) != 1:
        return None
    sol = sols[0]
    value = sol.get(y) if isinstance(sol, dict) else sol
    if value is None:
        return None
    # Must be a function of x only (no free y left).
    text = sstr(value).replace(" ", "")
    if "y" in text:
        return None
    return text or None


def _strip_math_delims_and_fix_superscripts(raw: str) -> str:
    """Normalize a graph expression the composer/math keyboard may wrap in
    inline-math delimiters or malformed superscripts.

    The math keyboard wraps the typed expression in ``$...$``; ``graph_expr``
    returns it verbatim, so without stripping, SymPy's safe-char gate rejects
    ``$``/``{``/``}`` and the turn ships without a verified fence. The
    keyboard also emits a base-less superscript chain for "x²" — ``^{x}^{2}``
    — which we fold into ``x^{2}`` (first superscript's content becomes the
    base of the second).

        "$x^2$"          → "x^2"
        "$^{x}^{2}$"      → "^{x}^{2}" → "x^{2}"
    """
    s = raw.strip()
    # Strip one pair of inline-math delimiters ($...$) wrapping the expr.
    if len(s) >= 2 and s.startswith("$") and s.endswith("$"):
        s = s[1:-1].strip()
    # Fold a base-less superscript chain: ^{a}^{b} → a^{b}.
    s = re.sub(r"\^{([^{}]+)}\^{([^{}]+)}", r"\1^{\2}", s)
    # Strip braces from any remaining single superscript: x^{2} → x^2.
    # (The graph path converts ^ to ** next; leaving {2} would make SymPy's
    # safe-char gate reject the expression.)
    s = re.sub(r"\^{([^{}]+)}", r"^\1", s)
    return s


def _extract_graph_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    g_expr = mtm.graph_expr(cleaned)
    if g_expr is None:
        return None
    g_expr = _strip_math_delims_and_fix_superscripts(g_expr)
    # _strip_trailing_filler(g_expr) used to run twice (once for the x= vertical
    # check, once for the returned graph expr). Compute it once and derive
    # both forms from it.
    stripped = _strip_trailing_filler(g_expr)
    expr_no_space = stripped.replace("^", "**").replace(" ", "")
    # Prefer vertical for "graph x=4": the ENTIRE RHS after "x=" must be a
    # pure number — "x=2y" / "x=2*y" are functions (y = x/2), not vertical
    # lines, so they must fall through to the solve-for-y path below.
    if expr_no_space.lower().startswith("x="):
        try:
            num = float(expr_no_space[2:])
        except ValueError:
            num = None
        if num is not None:
            return MathIntent(kind="vertical", point_x=num, operation="graph")
    expr = stripped.replace("^", "**")
    # An equation like "x=2y" is not a function expression — solve for y as
    # y = f(x) (e.g. "x/2") so sample_function can plot it. Without this,
    # sample_function gets an Equality and rejects it, so no verified graph
    # is emitted and the model emits its own (often wrong) spec.
    if "=" in expr:
        solved = _solve_for_y_as_function_of_x(expr)
        if solved is not None:
            expr = solved
    return MathIntent(kind="graph", expr=expr, operation="graph")


def _extract_calculus_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    op_word = mtm.calc_op(cleaned)
    if op_word is None or op_word in {"taylor", "partial", "dsolve"}:
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
    requested = _requested_variable(cleaned, lhs + rhs)
    variable = requested or (variables[0] if variables else "x")
    return MathIntent(
        kind="equation",
        lhs=lhs,
        rhs=rhs,
        operation="solve",
        variable=variable,
    )


def _extract_inequality_intent(cleaned: str) -> MathIntent | None:
    # Inequality — only reached when a math keyword already matched (this
    # function is called solely from needs_symbolic_math-gated paths), so bare
    # < / > here is safe from prose false-positives like "less than 5 minutes".
    compound = math_service.try_extract_compound_inequality_from_text(cleaned)
    if compound is not None:
        low, low_op, mid, high_op, high = compound
        variables = math_service.guess_variables(f"{low} {mid} {high}")
        requested = _requested_variable(cleaned, f"{low} {mid} {high}")
        variable = requested or (variables[0] if variables else "x")
        return MathIntent(
            kind="inequality",
            lower=low,
            lhs=mid,
            rhs=high,
            comparator=low_op,
            comparator_upper=high_op,
            operation="solve",
            variable=variable,
        )
    ineq = math_service.try_extract_inequality_from_text(cleaned)
    if not ineq:
        return None
    lhs, rhs, comparator = ineq
    variables = math_service.guess_variables(lhs + rhs)
    requested = _requested_variable(cleaned, lhs + rhs)
    variable = requested or (variables[0] if variables else "x")
    return MathIntent(
        kind="inequality",
        lhs=lhs,
        rhs=rhs,
        comparator=comparator,
        operation="solve",
        variable=variable,
    )


_INTENT_EXTRACTORS: Sequence[Callable[[str], MathIntent | None]] = (
    _extract_solid_intent,
    *SCHOOL_EXTRACTORS,
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
    _extract_triangle_angles_intent,
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


_ROOTS_RE = re.compile(r"\b(?:find(?:\s+the)?\s+)?(?:roots|zeros)\s+of\s+(.+)", re.IGNORECASE)


def extract_math_intent(text: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    cleaned = mtm.prepare(text)
    if not cleaned:
        return None

    # "roots of x^2 - 4" / "zeros of x^2 - 1" have no "=", so the equation
    # extractor below would skip them. Rewrite to "solve <expr> = 0" so the
    # existing equation path solves the polynomial. Only when the captured
    # tail has a digit (a real polynomial) and no "=" of its own (otherwise
    # the user already wrote "zeros of f(x) = x^2-4" and the equation
    # extractor handles it directly).
    roots_match = _ROOTS_RE.search(cleaned)
    if roots_match:
        tail = roots_match.group(1).strip()
        if "=" not in tail and any(c.isdigit() for c in tail):
            cleaned = f"solve {tail} = 0"

    for extractor in _INTENT_EXTRACTORS:
        intent = extractor(cleaned)
        if intent is not None:
            return intent
    return None
