"""Symbolic math via SymPy — server-side only."""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Literal

import numpy as np
from sympy import (
    Eq,
    Integral,
    Sum,
    Symbol,
    diff,
    integrate,
    latex,
    limit,
    oo,
    parse_expr,
    simplify,
    solve,
)
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    standard_transformations,
)

from app.models.math_schemas import (
    CircleGeometryInput,
    CircleGeometryResult,
    EquationInput,
    GraphSampleInput,
    GraphSampleResult,
    MathExprResult,
    MathLimitResult,
    MathSeriesResult,
    MathSolveResult,
    MathSystemSolveResult,
    NewtonIterationStep,
    NewtonMethodInput,
    NewtonMethodResult,
    RectangleGeometryInput,
    RectangleGeometryResult,
    RightTriangleGeometryInput,
    RightTriangleGeometryResult,
    SquareGeometryInput,
    SquareGeometryResult,
    SystemOfEquationsInput,
    TriangleGeometryInput,
    TriangleGeometryResult,
)

logger = logging.getLogger(__name__)

_TRANSFORMATIONS = (
    *standard_transformations,
    implicit_multiplication_application,
    convert_xor,
)
_LOCALS: dict[str, Any] = {
    "pi": math.pi,
    "e": math.e,
}


class MathServiceError(ValueError):
    """Invalid or unsupported math input."""


def _normalize_expr(text: str) -> str:
    s = text.strip()
    s = s.replace("^", "**")
    s = re.sub(r"\s+", " ", s)
    return s


# Only characters a real math expression ever needs. Rejects backslashes,
# quotes, braces, semicolons, and every other punctuation a Python-eval
# gadget would need to reach beyond a plain arithmetic/algebraic expression.
_SAFE_EXPR_CHARS = re.compile(r"^[\w\s+\-*/().,=<>!]*$")
_DECIMAL_NUMBER = re.compile(r"\d+\.\d+|\.\d+|\d+\.")


def _reject_unsafe_expr(normalized: str) -> None:
    """BUG FIX (was a live RCE): parse_expr/sympify evaluate the input via
    Python's eval() internally. Restricting local_dict to declared variable
    names (as this module already did) only stops BARE names from resolving
    to something dangerous via auto_symbol — it does nothing to stop
    ATTRIBUTE ACCESS on an already-resolved object. A Symbol instance is a
    real Python object, so "x.__class__.__mro__[1].__subclasses__()[N](...)"
    is valid Python syntax that walks the class hierarchy to reach e.g.
    subprocess.Popen and executes arbitrary shell commands — entirely inside
    SymPy's parse-time eval(), no further .doit()/evaluation needed. This is
    reachable from a plain chat message (math_tools.py's keyword-triggered
    intent extraction has no sanitization) and from the sympy MCP tool the
    model can call directly. SymPy's own docs are explicit that
    sympify/parse_expr must never see untrusted input un-validated.

    Reject anything that isn't plainly arithmetic/algebraic before it ever
    reaches parse_expr: no "__" (blocks every dunder-attribute gadget chain),
    no "." outside a decimal number (blocks attribute access while still
    allowing "3.14"), no "[" or "]" (blocks subscripting), and a strict
    character allowlist as a second, independent layer against whatever this
    doesn't anticipate. Do not loosen this without a real threat-model
    review — this is the only thing standing between a chat message and
    eval() in the API process.
    """
    if "__" in normalized:
        raise MathServiceError("Invalid expression")
    if "[" in normalized or "]" in normalized:
        raise MathServiceError("Invalid expression")
    if "." in _DECIMAL_NUMBER.sub("", normalized):
        raise MathServiceError("Invalid expression")
    if not _SAFE_EXPR_CHARS.match(normalized):
        raise MathServiceError("Invalid expression")


def _parse_expression(expr: str, variable_names: list[str] | None = None):
    normalized = _normalize_expr(expr)
    if len(normalized) > 512:
        raise MathServiceError("Expression too long")
    _reject_unsafe_expr(normalized)
    local_dict = dict(_LOCALS)
    if variable_names:
        for name in variable_names:
            local_dict[name] = Symbol(name)
    try:
        return parse_expr(
            normalized,
            local_dict=local_dict,
            transformations=_TRANSFORMATIONS,
            evaluate=True,
        )
    except Exception as exc:
        raise MathServiceError(f"Could not parse expression: {expr}") from exc


def parse_equation(data: EquationInput) -> tuple[Any, Any, list[Any]]:
    lhs = _parse_expression(data.lhs, data.variables)
    rhs = _parse_expression(data.rhs, data.variables)
    return Eq(lhs, rhs), lhs, rhs


def _worked_isolation_steps(lhs: Any, rhs: Any, variable: str) -> list[str]:
    """Derive verified intermediate isolation steps for common single-variable
    polynomial equations (degree 1, or degree 2 with no linear term) so the
    model can copy them verbatim instead of re-deriving (and corrupting) the
    algebra. Returns [] for forms it doesn't recognize — the caller still has
    the equation + solutions."""
    from sympy import Poly, sqrt

    try:
        var = Symbol(variable)
        expr = simplify(lhs - rhs)
        poly = Poly(expr, var)
    except Exception:
        return []

    degree = poly.degree()
    if degree not in (1, 2):
        return []

    # Coefficients of the polynomial in `var` (expr = 0 form).
    c1 = poly.coeff_monomial(var) if degree >= 1 else 0
    c2 = poly.coeff_monomial(var**2) if degree == 2 else 0
    c0 = poly.coeff_monomial(1)  # constant term

    steps: list[str] = []
    if degree == 1 and c1 != 0:
        # a*x + c0 = 0  →  a*x = -c0  →  x = -c0/a
        isolated = simplify(-c0 / c1)
        steps.append(f"Isolate: {latex(c1)} \\cdot {variable} = {latex(-c0)}")
        steps.append(f"Solve: {variable} = {latex(isolated)}")
        return steps

    if degree == 2 and c2 != 0 and c1 == 0:
        # a*x^2 + c0 = 0  →  x^2 = -c0/a  →  x = ±sqrt(-c0/a)
        ratio = simplify(-c0 / c2)
        steps.append(f"Isolate: {variable}^{{2}} = {latex(ratio)}")
        radicand = simplify(ratio)
        # Only emit the square-root step when the radicand is non-negative
        # (so we don't claim a real root for a negative radicand).
        if radicand.is_number and radicand >= 0:
            root = simplify(sqrt(radicand))
            steps.append(f"Take square root: {variable} = \\pm {latex(root)}")
        else:
            steps.append(f"Take square root: {variable} = \\pm \\sqrt{{{latex(radicand)}}}")
        return steps

    return steps


def _classify_no_solution(lhs: Any, rhs: Any) -> Literal["none", "infinite"]:
    """solve() returning [] is ambiguous: it means either a genuine
    contradiction (e.g. "0 = 1") or a tautology true for every value (e.g.
    "x = x", "2x + 4 = 2(x + 2)") — infinitely many solutions. Distinguish
    by checking whether lhs - rhs simplifies to the identically-zero
    expression. Anything not provably zero (including indeterminate cases
    with free symbols outside the solved-for variables) defaults to "none",
    matching the historical (ambiguous) behavior rather than over-claiming
    infinite solutions."""
    diff_expr = simplify(lhs - rhs)
    return "infinite" if diff_expr.is_zero else "none"


def solve_equation(data: EquationInput) -> MathSolveResult:
    equation, lhs, rhs = parse_equation(data)
    syms = [Symbol(v) for v in data.variables]
    try:
        raw_solutions = solve(equation, syms, dict=True)
    except Exception as exc:
        raise MathServiceError("Could not solve equation") from exc

    solutions_latex: list[str] = []
    for sol in raw_solutions:
        parts = [f"{latex(sym)} = {latex(val)}" for sym, val in sol.items()]
        solutions_latex.extend(parts)

    if not solutions_latex and raw_solutions:
        solutions_latex = [latex(s) for s in raw_solutions]

    steps = [
        f"Equation: {latex(lhs)} = {latex(rhs)}",
    ]
    # Include verified intermediate isolation steps for the common single-
    # variable forms so the model copies them instead of inventing wrong ones.
    if len(data.variables) == 1:
        steps.extend(_worked_isolation_steps(lhs, rhs, data.variables[0]))

    solution_kind: Literal["finite", "none", "infinite"] = "finite"
    if solutions_latex:
        steps.append(f"Solutions: {', '.join(solutions_latex)}")
    else:
        solution_kind = _classify_no_solution(lhs, rhs)
        if solution_kind == "infinite":
            steps.append(
                "Infinitely many solutions (equation is an identity, true for all values)."
            )
        else:
            steps.append("No solutions found (equation is a contradiction).")

    return MathSolveResult(
        solutions_latex=solutions_latex,
        steps=steps,
        lhs_latex=latex(lhs),
        rhs_latex=latex(rhs),
        solution_kind=solution_kind,
    )


def _classify_system_no_solution(pairs: list[tuple[Any, Any]]) -> Literal["none", "infinite"]:
    """Mirrors _classify_no_solution for the system case: solve() returning
    [] for every equation independently being a tautology (e.g. "x = x" AND
    "y = y") means infinitely many solutions; anything else defaults to
    "none", the same conservative default solve_equation uses. A genuinely
    underdetermined-but-non-trivial system (e.g. "x + y = 5" and
    "2x + 2y = 10") is NOT handled here — solve() already returns a
    parametrized solution for that case instead of an empty list, so it's
    caught by the free-symbol check in solve_system instead."""
    if all(simplify(lhs - rhs).is_zero for lhs, rhs in pairs):
        return "infinite"
    return "none"


def solve_system(data: SystemOfEquationsInput) -> MathSystemSolveResult:
    syms = [Symbol(v) for v in data.variables]
    equations = []
    parsed_pairs: list[tuple[Any, Any]] = []
    step_lines: list[str] = []
    for i, (lhs_raw, rhs_raw) in enumerate(data.equations, start=1):
        lhs = _parse_expression(lhs_raw, data.variables)
        rhs = _parse_expression(rhs_raw, data.variables)
        equations.append(Eq(lhs, rhs))
        parsed_pairs.append((lhs, rhs))
        step_lines.append(f"Equation {i}: {latex(lhs)} = {latex(rhs)}")

    try:
        raw_solutions = solve(equations, syms, dict=True)
    except Exception as exc:
        raise MathServiceError("Could not solve system of equations") from exc

    solutions: list[dict[str, str]] = [
        {str(sym): latex(val) for sym, val in sol.items()} for sol in raw_solutions
    ]

    # solve() returns a non-empty (but parametrized) solution for a
    # dependent/underdetermined system rather than an empty list — a value
    # that still contains one of the OTHER declared unknowns as a free
    # symbol means the system has infinitely many solutions, not a single
    # finite one, even though `solutions` isn't empty.
    declared = set(syms)
    is_parametrized = any(
        any(sympy_val.free_symbols & declared for sympy_val in sol.values())
        for sol in raw_solutions
    )

    solution_kind: Literal["finite", "none", "infinite"] = "finite"
    if is_parametrized:
        solution_kind = "infinite"
        for sol in solutions:
            parts = ", ".join(f"{k} = {v}" for k, v in sol.items())
            step_lines.append(f"Infinitely many solutions (one free variable): {parts}")
    elif solutions:
        for sol in solutions:
            parts = ", ".join(f"{k} = {v}" for k, v in sol.items())
            step_lines.append(f"Solution: {parts}")
    else:
        solution_kind = _classify_system_no_solution(parsed_pairs)
        if solution_kind == "infinite":
            step_lines.append("Infinitely many solutions (every equation is an identity).")
        else:
            step_lines.append("No solution — the equations are inconsistent.")

    return MathSystemSolveResult(solutions=solutions, steps=step_lines, solution_kind=solution_kind)


def newton_method(data: NewtonMethodInput) -> NewtonMethodResult:
    """Manual Newton iteration (not mpmath.findroot) so every step is
    inspectable and can be shown as verified "worked steps," mirroring
    _worked_isolation_steps's role for algebraic solves — the model copies
    the iteration history verbatim instead of inventing its own numbers."""
    sym = Symbol(data.variable)
    parsed = _parse_expression(data.expr, [data.variable])
    derivative = diff(parsed, sym)

    from sympy.utilities.lambdify import lambdify

    f = lambdify(sym, parsed, modules=["math"])
    fprime = lambdify(sym, derivative, modules=["math"])

    x_n = float(data.initial_guess)
    iterations: list[NewtonIterationStep] = []
    converged = False
    for i in range(data.max_iterations):
        try:
            fx = float(f(x_n))
        except Exception as exc:
            raise MathServiceError(f"Could not evaluate function at x={x_n}") from exc
        iterations.append(NewtonIterationStep(n=i, x_n=round(x_n, 10), f_x_n=round(fx, 10)))
        if abs(fx) < data.tolerance:
            converged = True
            break
        try:
            fpx = float(fprime(x_n))
        except Exception as exc:
            raise MathServiceError(f"Could not evaluate derivative at x={x_n}") from exc
        if fpx == 0:
            # Derivative vanished — Newton's method can't continue from here.
            break
        x_n = x_n - fx / fpx

    return NewtonMethodResult(
        iterations=iterations,
        converged=converged,
        root=round(x_n, 10) if converged else None,
        iterations_used=len(iterations),
    )


def simplify_expression(expr: str, variable: str = "x") -> MathExprResult:
    parsed = _parse_expression(expr, [variable])
    result = simplify(parsed)
    return MathExprResult(result=str(result), latex=latex(result))


def differentiate_expression(expr: str, variable: str = "x") -> MathExprResult:
    sym = Symbol(variable)
    parsed = _parse_expression(expr, [variable])
    result = diff(parsed, sym)
    return MathExprResult(result=str(result), latex=latex(result))


def integrate_expression(expr: str, variable: str = "x") -> MathExprResult:
    sym = Symbol(variable)
    parsed = _parse_expression(expr, [variable])
    result = integrate(parsed, sym)
    # integrate() can fail to find a closed form and hand back a result that
    # still contains an unevaluated Integral(...) rather than raising —
    # callers must not treat that as a verified, fully-solved answer.
    solved = not result.has(Integral)
    return MathExprResult(result=str(result), latex=latex(result), solved=solved)


_INFINITY_WORDS = {"infinity", "inf", "oo", "infty"}


def _parse_infinity_aware_point(raw: str) -> Any:
    """Limit/series bounds routinely use "infinity"/"inf"/"oo" (with an
    optional leading "-") instead of a plain number — map those directly to
    sympy's oo/-oo rather than routing the bare word through
    _parse_expression, which would reject it as an unrecognized symbol name.
    Anything else still goes through the same safety-checked expression
    parser as every other numeric input in this module."""
    s = raw.strip().lower()
    negative = s.startswith("-")
    core = s[1:].strip() if negative else s
    if core in _INFINITY_WORDS:
        return -oo if negative else oo
    return _parse_expression(raw)


def compute_limit(expr: str, variable: str, point: str, direction: str = "+-") -> MathLimitResult:
    sym = Symbol(variable)
    parsed = _parse_expression(expr, [variable])
    point_val = _parse_infinity_aware_point(point)
    try:
        result = limit(parsed, sym, point_val, dir=direction)
    except Exception as exc:
        raise MathServiceError(f"Could not compute limit of: {expr}") from exc
    # A limit can legitimately evaluate to oo/-oo (diverges) or zoo (the
    # two-sided limit doesn't exist because the two sides disagree) — render
    # these explicitly via latex() ("\infty" etc.) rather than leaving an
    # opaque symbol name for the model to describe incorrectly.
    return MathLimitResult(
        result=str(result), latex=latex(result), is_infinite=bool(result.is_infinite)
    )


def evaluate_series_sum(expr: str, variable: str, start: str, end: str) -> MathSeriesResult:
    sym = Symbol(variable)
    parsed = _parse_expression(expr, [variable])
    start_val = _parse_infinity_aware_point(start)
    end_val = _parse_infinity_aware_point(end)
    series = Sum(parsed, (sym, start_val, end_val))
    try:
        is_convergent = series.is_convergent()
    except NotImplementedError:
        is_convergent = None
    try:
        is_absolutely_convergent = series.is_absolutely_convergent()
    except NotImplementedError:
        is_absolutely_convergent = None
    try:
        result = series.doit()
    except Exception as exc:
        raise MathServiceError(f"Could not evaluate series: {expr}") from exc
    return MathSeriesResult(
        result=str(result),
        latex=latex(result),
        is_infinite=bool(result.is_infinite),
        is_convergent=None if is_convergent is None else bool(is_convergent),
        is_absolutely_convergent=(
            None if is_absolutely_convergent is None else bool(is_absolutely_convergent)
        ),
    )


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
    labels = {
        "base": f"{b:g} {unit}",
        "height": f"{h:g} {unit}",
        "hypotenuse": f"{hypotenuse:.2f} {unit}",
        "area": f"{area:g} {unit}²",
        "angle": "90°",
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


_EQUATION_PATTERN = re.compile(
    r"(?P<lhs>[0-9a-zA-Z+\-*/().\s^**]+?)\s*=\s*(?P<rhs>[0-9a-zA-Z+\-*/().\s^**]+)"
)

# BUG FIX: _EQUATION_PATTERN's lhs capture is non-greedy, but re.search still
# tries the EARLIEST possible match start — so natural phrasing like "Solve
# x^2 + 2 = 6" or "what is x^2 + 2 = 6" swept the trigger words into the
# extracted lhs. That corrupted BOTH the parsed expression (undeclared
# letters silently become new multiplied symbols via SymPy's auto_symbol,
# e.g. "Solve x^2" parses as S*o*l*v*e*x^2 with e resolving to Euler's
# number) and the guessed variable list — producing a confidently wrong
# answer presented as "verified, do NOT recompute." Strip common leading
# trigger phrases before the extraction regex ever runs.
_LEADING_FILLER_RE = re.compile(
    r"^\s*(?:please\s+)?(?:can\s+you\s+|could\s+you\s+)?"
    r"(?:solve|find|calculate|compute|evaluate|determine|simplify|what\s+is|what's)\s+"
    r"(?:the\s+system\s+of\s+equations\s+|the\s+system\s+|the\s+equations\s+)?"
    r"(?:for\s+me\s+)?(?:x\s+)?(?:if\s+)?",
    re.IGNORECASE,
)


def _strip_leading_filler(text: str) -> str:
    s = text.strip()
    prev = None
    while prev != s:
        prev = s
        s = _LEADING_FILLER_RE.sub("", s).strip()
    return s


# Verb-only leading filler — used by inequality extraction, where the bare
# variable IS the lhs and must NOT be stripped (unlike _LEADING_FILLER_RE's
# `(?:x\s+)?`, which would eat "x " in "solve x \leq 5").
_LEADING_VERB_RE = re.compile(
    r"^\s*(?:please\s+)?(?:can\s+you\s+|could\s+you\s+)?"
    r"(?:solve|find|calculate|compute|evaluate|determine|simplify|what\s+is|what's)\s+"
    r"(?:for\s+me\s+)?(?:if\s+)?",
    re.IGNORECASE,
)


def try_extract_equations_from_text(text: str) -> list[tuple[str, str]]:
    """Best-effort extraction of every `lhs=rhs` clause in the text.

    BUG FIX (was the most severe correctness bug found in the math system
    audit): this used to be a single re.search, so "solve x+y=5, x-y=1"
    silently extracted only the first clause and answered with the same
    "verified, do NOT recompute" confidence as a fully correct response.
    re.finditer here returns every clause; callers decide whether 1 match
    means a single equation or 2+ means a system.
    """
    cleaned = _strip_leading_filler(text)
    pairs: list[tuple[str, str]] = []
    for match in _EQUATION_PATTERN.finditer(cleaned):
        lhs = match.group("lhs").strip()
        rhs = match.group("rhs").strip()
        if not lhs or not rhs or len(lhs) > 120 or len(rhs) > 120:
            continue
        pairs.append((lhs, rhs))
    return pairs


def try_extract_equation_from_text(text: str) -> EquationInput | None:
    """Best-effort SINGLE-equation extraction — kept for callers that only
    ever want one equation. See try_extract_equations_from_text for the
    multi-equation (system) case."""
    pairs = try_extract_equations_from_text(text)
    if not pairs:
        return None
    lhs, rhs = pairs[0]
    variables = _guess_variables(f"{lhs} {rhs}")
    try:
        return EquationInput(lhs=lhs, rhs=rhs, variables=variables or ["x"])
    except Exception:
        return None


# Inequality operators → canonical form. \le/\leq/≤/<= all map to "<=" so the
# solver only has to handle four relations. The negative-lookahead on \le/\ge
# stops them from matching the \le inside \left (a very common LaTeX delimiter).
_INEQUALITY_PATTERN = re.compile(
    r"(?P<lhs>[0-9a-zA-Z+\-*/().\s^**]+?)\s*"
    r"(?P<op>\\leq(?![a-zA-Z])|\\geq(?![a-zA-Z])|\\le(?![a-zA-Z])|\\ge(?![a-zA-Z])|≤|≥|<|>)\s*"
    r"(?P<rhs>[0-9a-zA-Z+\-*/().\s^**]+)"
)
_INEQ_CANON = {
    "\\leq": "<=",
    "\\le": "<=",
    "≤": "<=",
    "\\geq": ">=",
    "\\ge": ">=",
    "≥": ">=",
    "<": "<",
    ">": ">",
}


def try_extract_inequality_from_text(text: str) -> tuple[str, str, str] | None:
    """Best-effort extraction of a single `lhs OP rhs` inequality (OP ∈
    <, >, ≤, ≥, \\leq, \\geq, \\le, \\ge). Returns (lhs, rhs, canonical_comparator)
    or None. NOTE: callers gate this on a math keyword (needs_symbolic_math)
    having already matched, so prose like "less than 5 minutes" (no keyword)
    never reaches here — bare < / > is safe in that context."""
    # Strip ONLY the leading verb, not the variable — _strip_leading_filler's
    # `(?:x\s+)?` would eat a bare "x " operand (e.g. "solve x \leq 5" → "\leq 5"),
    # leaving no lhs for the inequality pattern to match.
    cleaned = _LEADING_VERB_RE.sub("", text, count=1).strip()
    m = _INEQUALITY_PATTERN.search(cleaned)
    if not m:
        return None
    lhs = m.group("lhs").strip()
    rhs = m.group("rhs").strip()
    if not lhs or not rhs or len(lhs) > 120 or len(rhs) > 120:
        return None
    return lhs, rhs, _INEQ_CANON.get(m.group("op"), m.group("op"))


def solve_inequality(lhs: str, rhs: str, variable: str, comparator: str) -> MathSolveResult:
    """Solve a single-variable inequality, e.g. `x**2 - 1 > 0` → x < -1 or x > 1.

    `comparator` is the canonical form returned by try_extract_inequality_from_text
    ("<", ">", "<=", ">="). lhs/rhs go through the same allow-checked parser as
    every other expression; the relational is built from SymPy Lt/Gt/Le/Ge, so
    no user string is eval'd.
    """
    from sympy import Ge, Gt, Le, Lt, solve_univariate_inequality

    sym = Symbol(variable)
    left = _parse_expression(lhs, [variable])
    right = _parse_expression(rhs, [variable])
    diff_expr = simplify(left - right)
    rel_cls = {"<": Lt, ">": Gt, "<=": Le, ">=": Ge}.get(comparator)
    if rel_cls is None:
        raise MathServiceError(f"Unknown inequality comparator: {comparator}")
    try:
        sol = solve_univariate_inequality(rel_cls(diff_expr, 0), sym)
    except Exception as exc:  # NotImplementedError / non-univariate / etc.
        raise MathServiceError(f"Could not solve inequality: {lhs} {comparator} {rhs}") from exc
    sol_latex = latex(sol)
    cmp_latex = {"<": "<", ">": ">", "<=": "\\leq", ">=": "\\geq"}[comparator]
    return MathSolveResult(
        solutions_latex=[sol_latex],
        steps=[
            f"Inequality: {latex(left)} {cmp_latex} {latex(right)}",
            f"Solution: {sol_latex}",
        ],
        lhs_latex=latex(left),
        rhs_latex=latex(right),
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


def _guess_variables(text: str) -> list[str]:
    """BUG FIX: a bare per-letter scan treated function-name letters as
    candidate variables -- "cos(x) = 0" guessed 'c' (alphabetically first of
    c/o/s/x) instead of 'x', silently solving for the wrong symbol. Strip
    recognized function names AND multi-letter constants (pi, oo, ...) before
    extracting letters, so "sin(pi*x) = 0" guesses 'x' not 'i'/'p'."""
    stripped = _FUNCTION_NAME_RE.sub(" ", text)
    stripped = _CONSTANT_NAMES_RE.sub(" ", stripped)
    found = sorted(set(re.findall(r"[a-zA-Z]", stripped)))
    # Exclude single-letter constants: e (Euler's number), i (imaginary unit
    # in some contexts, though commonly a variable index -- keep it for now
    # since 'i' is far more often a loop variable than the imaginary unit in
    # user input). E (uppercase) is SymPy's Euler number.
    letters = [c for c in found if c not in {"e", "E"}]
    return letters[:4] if letters else ["x"]
