"""Function sampling, ellipses, inequality number lines."""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
from sympy import Symbol

from app.models.math_schemas import (
    GraphBlockSpec,
    GraphSampleInput,
    GraphSampleResult,
    NumberLineInterval,
)
from app.services.math_service.discrete import guess_variables
from app.services.math_service.extract_eq import (
    try_extract_compound_inequality_from_text,
    try_extract_inequality_from_text,
)
from app.services.math_service.parse import MathServiceError, _parse_expression


def _split_into_segments(
    points: list[list[float]], percentile: float = 85.0
) -> list[list[list[float]]]:
    """Split a continuous point list wherever a vertical asymptote likely
    sits between two consecutive samples (e.g. tan(x) near pi/2) — without
    this, naively connecting every finite sample draws a near-vertical line
    straight across the discontinuity.

    Numeric heuristic, not full symbolic singularity detection: flag a gap
    only where consecutive y-values (a) flip sign AND (b) both sit above the
    given percentile of |y| across the whole sample. A pole is exactly this
    shape — y diverges to +inf on one side and -inf on the other, so the two
    samples straddling it are both large AND opposite in sign. An ordinary
    zero-crossing (e.g. sin(x)) also flips sign but both values are small
    there, so it's correctly left unsplit; matches empirical validation
    against tan(x) (isolates all 6 real asymptotes in [-10, 10] with no
    over-splitting) and sin(x)/x**2 (never splits).
    """
    if len(points) < 2:
        return [points] if points else []
    abs_ys = sorted(abs(p[1]) for p in points)
    idx = min(len(abs_ys) - 1, int(len(abs_ys) * percentile / 100))
    large_threshold = abs_ys[idx]
    if large_threshold <= 0:
        return [points]
    segments: list[list[list[float]]] = [[points[0]]]
    for i in range(1, len(points)):
        y0, y1 = points[i - 1][1], points[i][1]
        sign_flip = (y0 > 0) != (y1 > 0)
        both_large = abs(y0) > large_threshold and abs(y1) > large_threshold
        if sign_flip and both_large:
            segments.append([])
        segments[-1].append(points[i])
    return [seg for seg in segments if seg]


def sample_function(data: GraphSampleInput) -> GraphSampleResult:
    if data.x_max <= data.x_min:
        raise MathServiceError("x_max must be greater than x_min")
    sym = Symbol(data.variable)
    parsed = _parse_expression(data.expr, [data.variable])
    from sympy.core.relational import Relational

    if isinstance(parsed, Relational):
        raise MathServiceError("Inequality expressions are number lines, not y=f(x) plots")

    from sympy.utilities.lambdify import lambdify

    numpy_fn = lambdify(sym, parsed, modules=["numpy"])
    xs = np.linspace(data.x_min, data.x_max, data.n)
    try:
        ys = numpy_fn(xs)
    except Exception as exc:
        raise MathServiceError(f"Could not sample function: {data.expr}") from exc

    ys = np.asarray(ys, dtype=float)
    points: list[list[float]] = []
    for x_val, y_val in zip(xs, ys, strict=False):
        if not np.isfinite(y_val):
            continue
        points.append([round(float(x_val), 4), round(float(y_val), 4)])

    return GraphSampleResult(
        expr=data.expr,
        variable=data.variable,
        x_min=data.x_min,
        x_max=data.x_max,
        points=points,
        segments=_split_into_segments(points),
    )


# Axis-aligned ellipse / circle relations only (not general F(x,y)=0).
_CIRCLE_RELATION_RE = re.compile(r"^(?:x\*\*2\+y\*\*2|y\*\*2\+x\*\*2)=(\d+(?:\.\d+)?)$")
_ELLIPSE_DIV_RELATION_RE = re.compile(r"^x\*\*2/(\d+(?:\.\d+)?)\+y\*\*2/(\d+(?:\.\d+)?)=1$")
_ELLIPSE_DIV_RELATION_YX_RE = re.compile(r"^y\*\*2/(\d+(?:\.\d+)?)\+x\*\*2/(\d+(?:\.\d+)?)=1$")
_ELLIPSE_SCALE_RELATION_RE = re.compile(
    r"^\(x/(\d+(?:\.\d+)?)\)\*\*2\+\(y/(\d+(?:\.\d+)?)\)\*\*2=1$"
)


def parse_ellipse_relation(expr: str) -> tuple[float, float] | None:
    """Parse ``x^2+y^2=r^2`` / ``x^2/a^2+y^2/b^2=1`` into semi-axes ``(a, b)``.

    Returns ``None`` for anything that is not this narrow homework shape —
    general implicit curves stay out of scope.
    """
    s = expr.strip().replace("^", "**")
    s = re.sub(r"\s+", "", s)
    if not s:
        return None
    m = _CIRCLE_RELATION_RE.fullmatch(s)
    if m:
        r2 = float(m.group(1))
        if r2 <= 0:
            return None
        r = math.sqrt(r2)
        return r, r
    m = _ELLIPSE_DIV_RELATION_RE.fullmatch(s)
    if m:
        a2, b2 = float(m.group(1)), float(m.group(2))
        if a2 <= 0 or b2 <= 0:
            return None
        return math.sqrt(a2), math.sqrt(b2)
    m = _ELLIPSE_DIV_RELATION_YX_RE.fullmatch(s)
    if m:
        b2, a2 = float(m.group(1)), float(m.group(2))
        if a2 <= 0 or b2 <= 0:
            return None
        return math.sqrt(a2), math.sqrt(b2)
    m = _ELLIPSE_SCALE_RELATION_RE.fullmatch(s)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        if a <= 0 or b <= 0:
            return None
        return a, b
    return None


def sample_ellipse(a: float, b: float, n: int = 96) -> GraphSampleResult:
    """Parametric samples for ``(x/a)^2 + (y/b)^2 = 1`` as a closed polyline."""
    if a <= 0 or b <= 0:
        raise MathServiceError("Ellipse semi-axes must be positive")
    count = max(16, min(int(n), 500))
    thetas = np.linspace(0.0, 2.0 * math.pi, count, endpoint=False)
    points: list[list[float]] = [
        [round(float(a * math.cos(t)), 4), round(float(b * math.sin(t)), 4)] for t in thetas
    ]
    # Close the loop so the SVG polyline does not leave a gap at θ=0.
    points.append(points[0])
    if abs(a - b) < 1e-12:
        label = f"x**2 + y**2 = {a * a:g}"
    else:
        label = f"x**2/{a * a:g} + y**2/{b * b:g} = 1"
    pad_x = max(1.0, a * 0.15)
    return GraphSampleResult(
        expr=label,
        variable="x",
        x_min=-(a + pad_x),
        x_max=a + pad_x,
        points=points,
        segments=[],
    )


def build_ellipse_graph_spec(expr: str, n: int) -> GraphBlockSpec | None:
    """If ``expr`` is an axis-aligned circle/ellipse relation, return the
    parametrically-sampled ``GraphBlockSpec`` (with a square-ish viewport
    around the curve); otherwise ``None``.

    Shared by the heuristic ``_verified_block_graph`` (math_tools.py) and the
    MCP ``sympy`` adapter so the sampling and y-range padding live in one
    place — previously both copied the same ``-(b + max(1.0, b * 0.15))`` /
    ``b + max(1.0, b * 0.15)`` viewport math, which could drift.
    """
    ellipse = parse_ellipse_relation(expr)
    if ellipse is None:
        return None
    a, b = ellipse
    sample = sample_ellipse(a, b, n)
    return GraphBlockSpec(
        expr=sample.expr,
        variable=sample.variable,
        x_min=sample.x_min,
        x_max=sample.x_max,
        y_min=-(b + max(1.0, b * 0.15)),
        y_max=b + max(1.0, b * 0.15),
        points=sample.points,
        segments=[],
        title=sample.expr,
    )


_EQUATION_SIDE_CHARS = frozenset(
    "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+-*/().^ "
)

_FILLER_VERBS = (
    "solve",
    "find",
    "calculate",
    "compute",
    "evaluate",
    "determine",
    "simplify",
    "what is",
    "what's",
)
_SYSTEM_PREFIXES = (
    "the system of equations ",
    "the system ",
    "the equations ",
)


_MAX_NUMBER_LINE_INTERVALS = 8


def expr_looks_like_inequality(expr: str) -> bool:
    """True when ``expr`` has a comparison op (not a plain y=f(x) or x=c)."""
    compact = expr.replace(" ", "")
    return any(op in compact for op in (">=", "<=", ">", "<", "≥", "≤"))


def _finite_or_none(bound: Any) -> float | None:
    if bound is None:
        return None
    if getattr(bound, "is_infinite", False):
        return None
    try:
        value = float(bound)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def _collect_number_line_intervals(sol: Any, out: list[NumberLineInterval]) -> bool:
    """Walk a SymPy set into number-line intervals. False = unsupported shape."""
    from sympy import EmptySet, FiniteSet, Interval, Union
    from sympy import S as sympy_S

    if sol is None or sol is EmptySet or sol == sympy_S.EmptySet:
        return True
    if sol == sympy_S.Reals:
        out.append(NumberLineInterval(start=None, end=None))
        return True
    if isinstance(sol, Interval):
        start = _finite_or_none(sol.start)
        end = _finite_or_none(sol.end)
        out.append(
            NumberLineInterval(
                start=start,
                end=end,
                start_inclusive=start is not None and not bool(sol.left_open),
                end_inclusive=end is not None and not bool(sol.right_open),
            )
        )
        return True
    if isinstance(sol, FiniteSet):
        for point in sol:
            value = _finite_or_none(point)
            if value is None:
                return False
            out.append(
                NumberLineInterval(
                    start=value,
                    end=value,
                    start_inclusive=True,
                    end_inclusive=True,
                )
            )
        return True
    if isinstance(sol, Union):
        return all(_collect_number_line_intervals(arg, out) for arg in sol.args)
    return False


def _inequality_solution_set(expr: str, variable: str) -> Any:
    """Solve a 1-variable inequality; returns a SymPy set (possibly empty)."""
    from sympy import Ge, Gt, Le, Lt, S, solveset

    compound = try_extract_compound_inequality_from_text(expr)
    if compound is not None:
        low, low_op, mid, high_op, high = compound
        sym = Symbol(variable, real=True)
        low_e = _parse_expression(low, [variable], real=True)
        mid_e = _parse_expression(mid, [variable], real=True)
        high_e = _parse_expression(high, [variable], real=True)
        ascending = low_op in ("<", "<=") and high_op in ("<", "<=")
        descending = low_op in (">", ">=") and high_op in (">", ">=")
        if ascending:
            lower_rel = Gt(mid_e, low_e) if low_op == "<" else Ge(mid_e, low_e)
            upper_rel = Lt(mid_e, high_e) if high_op == "<" else Le(mid_e, high_e)
        elif descending:
            lower_rel = Lt(mid_e, low_e) if low_op == ">" else Le(mid_e, low_e)
            upper_rel = Gt(mid_e, high_e) if high_op == ">" else Ge(mid_e, high_e)
        else:
            raise MathServiceError("Unsupported compound inequality direction")
        return solveset(lower_rel, sym, domain=S.Reals).intersect(
            solveset(upper_rel, sym, domain=S.Reals)
        )

    ineq = try_extract_inequality_from_text(expr)
    if ineq is None:
        raise MathServiceError("Not a 1-variable inequality")
    lhs, rhs, comparator = ineq
    # Number lines are real; solveset(..., Reals) returns Interval/Union,
    # unlike solve_univariate_inequality which can return a Relational.
    sym = Symbol(variable, real=True)
    left = _parse_expression(lhs, [variable], real=True)
    right = _parse_expression(rhs, [variable], real=True)
    rel_cls = {"<": Lt, ">": Gt, "<=": Le, ">=": Ge}.get(comparator)
    if rel_cls is None:
        raise MathServiceError(f"Unknown inequality comparator: {comparator}")
    return solveset(rel_cls(left, right), sym, domain=S.Reals)


def number_line_spec_from_expr(expr: str, variable: str = "x") -> GraphBlockSpec | None:
    """Turn ``x > 3`` / ``1 < x < 5`` into a number-line fence, or None.

    Two-variable relations (``y > 2x``) stay out — those are half-planes, not
    a 1D number line. Unsolvable / exotic sets also return None.
    """
    cleaned = expr.strip()
    if not cleaned or not expr_looks_like_inequality(cleaned):
        return None
    vars_found = guess_variables(cleaned)
    if len(vars_found) > 1:
        return None
    var = vars_found[0] if vars_found else variable
    try:
        sol = _inequality_solution_set(cleaned, var)
        intervals: list[NumberLineInterval] = []
        if not _collect_number_line_intervals(sol, intervals):
            return None
        if len(intervals) > _MAX_NUMBER_LINE_INTERVALS:
            return None
    except MathServiceError:
        return None
    return GraphBlockSpec(
        type="number_line",
        expr=cleaned[:256],
        variable=var,
        title=cleaned[:64],
        intervals=intervals,
    )


_FUNCTION_NAME_RE = re.compile(
    r"\b(?:sin|cos|tan|sec|csc|cot|arcsin|arccos|arctan|sinh|cosh|tanh|log|ln|sqrt|exp|min|max|abs)\b",
    re.IGNORECASE,
)

# Multi-letter mathematical constants that must NOT be split into per-letter
# variable candidates. Without this, "sin(pi*x) = 0" would guess 'i' and 'p'
# as variables (alphabetically before 'x'), silently solving for the wrong
# symbol. SymPy recognizes these as constants, so the guesser must too.
_CONSTANT_NAMES_RE = re.compile(
    r"\b(?:pi|oo|inf|infinity|nan)\b",
    re.IGNORECASE,
)
