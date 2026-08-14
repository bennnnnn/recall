"""Symbolic math via SymPy — server-side only."""

from __future__ import annotations

import logging
import math
import re
import statistics as _stats
from itertools import pairwise
from typing import Any, Literal

import numpy as np
from sympy import (
    Abs,
    Eq,
    Integral,
    Sum,
    Symbol,
    diff,
    expand,
    factor,
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
    CombinatoricsInput,
    CombinatoricsResult,
    EquationInput,
    GraphBlockSpec,
    GraphSampleInput,
    GraphSampleResult,
    MathExprResult,
    MathLimitResult,
    MathSeriesResult,
    MathSolveResult,
    MathSystemSolveResult,
    MatrixInput,
    MatrixResult,
    NewtonIterationStep,
    NewtonMethodInput,
    NewtonMethodResult,
    NumberLineInterval,
    NumberTheoryInput,
    NumberTheoryResult,
    ParallelogramInput,
    ParallelogramResult,
    RectangleGeometryInput,
    RectangleGeometryResult,
    RightTriangleGeometryInput,
    RightTriangleGeometryResult,
    SectorInput,
    SectorResult,
    SquareGeometryInput,
    SquareGeometryResult,
    StatisticsInput,
    StatisticsResult,
    SystemOfEquationsInput,
    TrapezoidInput,
    TrapezoidResult,
    TriangleGeometryInput,
    TriangleGeometryResult,
    TriangleSidesInput,
    TriangleSidesResult,
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
    "Abs": Abs,
}


class MathServiceError(ValueError):
    """Invalid or unsupported math input."""


# Shallow LaTeX → SymPy-ish text. Nested \frac needs repeated passes (capped).
_LATEX_FRAC_RE = re.compile(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_LATEX_ABS_LEFT_RIGHT_RE = re.compile(
    r"\\(?:left|lvert)\s*\|\s*(.*?)\s*\\(?:right|rvert)\s*\|",
    re.DOTALL,
)
_LATEX_ABS_VERT_RE = re.compile(r"\\(?:lvert|rvert)\b")
_LATEX_SYMBOL_SUBS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\\infty"), "oo"),
    (re.compile(r"\\pi\b"), "pi"),
    (re.compile(r"\\cdot"), "*"),
    (re.compile(r"\\times"), "*"),
    (re.compile(r"\\div"), "/"),
    # Before \\left/\\right: \\le must not steal the prefix of \\left.
    (re.compile(r"\\leq"), "<="),
    (re.compile(r"\\geq"), ">="),
    (re.compile(r"\\le(?![a-zA-Z])"), "<="),
    (re.compile(r"\\ge(?![a-zA-Z])"), ">="),
    (re.compile(r"\\left"), ""),
    (re.compile(r"\\right"), ""),
]
_LATEX_FUNCTION_RE = re.compile(
    r"\\(sin|cos|tan|sec|csc|cot|arcsin|arccos|arctan|sinh|cosh|tanh|log|ln|sqrt|exp|min|max|Abs|abs)\b",
    re.IGNORECASE,
)


def _rewrite_bare_abs_bars(expr: str) -> str:
    """Rewrite paired ``|inner|`` → ``Abs(inner)``.

    Bare pipes are rejected by the expression allowlist; converting first lets
    homework like ``|x-2|<5`` reach SymPy without loosening ``_SAFE_EXPR_CHARS``.
    Unbalanced ``|`` is left as-is (still rejected later).
    """
    out: list[str] = []
    i = 0
    n = len(expr)
    while i < n:
        if expr[i] != "|":
            out.append(expr[i])
            i += 1
            continue
        depth = 0
        j = i + 1
        found = -1
        while j < n:
            ch = expr[j]
            if ch == "|" and depth == 0:
                found = j
                break
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(0, depth - 1)
            j += 1
        if found == -1:
            out.append("|")
            i += 1
            continue
        inner = expr[i + 1 : found]
        if not inner.strip():
            out.append("|")
            i += 1
            continue
        out.append(f"Abs({inner})")
        i = found + 1
    return "".join(out)


# OCR / homework unicode operators → ASCII before the allowlist runs.
# Do NOT widen `_SAFE_EXPR_CHARS`; map glyphs here instead.
# Escapes (not literals) keep RUF001 from flagging lookalike punctuation.
_UNICODE_OP_SUBS: tuple[tuple[str, str], ...] = (
    ("\u00d7", "*"),  # U+00D7 multiplication sign
    ("\u22c5", "*"),  # U+22C5 dot operator
    ("\u00b7", "*"),  # U+00B7 middle dot
    ("\u2217", "*"),  # U+2217 asterisk operator
    ("\u00f7", "/"),  # U+00F7 division sign
    ("\u2215", "/"),  # U+2215 division slash
    ("\u2044", "/"),  # U+2044 fraction slash
    ("\u2212", "-"),  # U+2212 minus sign
    ("\u2013", "-"),  # U+2013 en dash
    ("\u2014", "-"),  # U+2014 em dash
)


def _normalize_latex_to_sympy(expr: str) -> str:
    """Expand common LaTeX so pasted/OCR homework can pass the safe-char gate."""
    s = expr
    for glyph, repl in _UNICODE_OP_SUBS:
        s = s.replace(glyph, repl)
    s = _LATEX_ABS_LEFT_RIGHT_RE.sub(r"Abs(\1)", s)
    s = _LATEX_ABS_VERT_RE.sub("", s)
    for pattern, replacement in _LATEX_SYMBOL_SUBS:
        s = pattern.sub(replacement, s)

    def _func_repl(match: re.Match[str]) -> str:
        name = match.group(1).lower()
        return "Abs" if name == "abs" else name

    s = _LATEX_FUNCTION_RE.sub(_func_repl, s)
    for _ in range(8):
        nxt = _LATEX_FRAC_RE.sub(r"(\1)/(\2)", s)
        if nxt == s:
            break
        s = nxt
    s = _rewrite_bare_abs_bars(s)
    return s


def _normalize_expr(text: str) -> str:
    s = text.strip()
    s = _normalize_latex_to_sympy(s)
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


def _parse_expression(
    expr: str,
    variable_names: list[str] | None = None,
    *,
    real: bool = False,
):
    normalized = _normalize_expr(expr)
    if len(normalized) > 512:
        raise MathServiceError("Expression too long")
    _reject_unsafe_expr(normalized)
    local_dict = dict(_LOCALS)
    if variable_names:
        for name in variable_names:
            local_dict[name] = Symbol(name, real=True) if real else Symbol(name)
    try:
        return parse_expr(
            normalized,
            local_dict=local_dict,
            transformations=_TRANSFORMATIONS,
            evaluate=True,
        )
    except Exception as exc:
        raise MathServiceError(f"Could not parse expression: {expr}") from exc


def _expr_needs_real_domain(*parts: str) -> bool:
    """Abs-value homework needs a real domain; SymPy rejects Abs(complex) solve."""
    return any("Abs(" in p or "abs(" in p for p in parts)


def parse_equation(data: EquationInput) -> tuple[Any, Any, list[Any]]:
    real = _expr_needs_real_domain(data.lhs, data.rhs)
    lhs = _parse_expression(data.lhs, data.variables, real=real)
    rhs = _parse_expression(data.rhs, data.variables, real=real)
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

    if degree == 2 and c2 != 0 and c1 != 0:
        # General quadratic a*x^2 + b*x + c = 0 — emit the discriminant and
        # the quadratic formula so the model can copy verified steps instead
        # of re-deriving (and corrupting) the algebra when b != 0.
        discriminant = simplify(c1**2 - 4 * c2 * c0)
        steps.append(
            f"Discriminant: \\Delta = {latex(c1)}^{{2}} - 4({latex(c2)})({latex(c0)}) "
            f"= {latex(discriminant)}"
        )
        steps.append(
            f"Quadratic formula: {variable} = \\frac{{-{latex(c1)} \\pm "
            f"\\sqrt{{{latex(discriminant)}}}}}{{2({latex(c2)})}}"
        )
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
    real = _expr_needs_real_domain(data.lhs, data.rhs)
    syms = [Symbol(v, real=True) if real else Symbol(v) for v in data.variables]
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


def factor_expression(expr: str, variable: str = "x") -> MathExprResult:
    """Factor a polynomial/expression into a product of irreducible factors."""
    parsed = _parse_expression(expr, [variable])
    result = factor(parsed)
    return MathExprResult(result=str(result), latex=latex(result))


def expand_expression(expr: str, variable: str = "x") -> MathExprResult:
    """Expand a factored expression into a sum of terms."""
    parsed = _parse_expression(expr, [variable])
    result = expand(parsed)
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


def integrate_definite(expr: str, variable: str, lower: str, upper: str) -> MathExprResult:
    """Definite integral of expr w.r.t. variable from `lower` to `upper`.

    Bounds are infinity-aware ("oo"/"inf"/"infty" → sympy.oo) via the same
    parser limits/series use. A divergent/improper integral may evaluate to
    oo/-oo/zoo; that is reported as the result rather than raising.
    """
    sym = Symbol(variable)
    parsed = _parse_expression(expr, [variable])
    a = _parse_infinity_aware_point(lower)
    b = _parse_infinity_aware_point(upper)
    try:
        result = integrate(parsed, (sym, a, b))
    except Exception as exc:
        raise MathServiceError(f"Could not compute definite integral of: {expr}") from exc
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


def _is_equation_side(s: str) -> bool:
    stripped = s.strip()
    if not stripped or len(stripped) > 120:
        return False
    return all(c in _EQUATION_SIDE_CHARS for c in stripped)


def _strip_leading_prefixes(text: str, *, strip_bare_x: bool) -> str:
    """Strip leading solve/find/... filler without ``\\s+`` regex pumps."""
    s = text.strip()
    while True:
        prev = s
        low = s.lower()
        if low.startswith("please "):
            s = s[7:].lstrip()
            low = s.lower()
        for polite in ("can you ", "could you "):
            if low.startswith(polite):
                s = s[len(polite) :].lstrip()
                low = s.lower()
                break
        stripped_verb = False
        for verb in _FILLER_VERBS:
            if low.startswith(verb + " "):
                s = s[len(verb) + 1 :].lstrip()
                low = s.lower()
                stripped_verb = True
                break
        if not stripped_verb:
            return s
        if strip_bare_x:
            for sys in _SYSTEM_PREFIXES:
                if low.startswith(sys):
                    s = s[len(sys) :].lstrip()
                    low = s.lower()
                    break
        if low.startswith("for me "):
            s = s[7:].lstrip()
            low = s.lower()
        if strip_bare_x and low.startswith("x "):
            s = s[2:].lstrip()
            low = s.lower()
        if low.startswith("if "):
            s = s[3:].lstrip()
        if s == prev:
            return s
    return s


def _strip_leading_filler(text: str) -> str:
    return _strip_leading_prefixes(text, strip_bare_x=True)


def _strip_leading_verb(text: str) -> str:
    """Verb-only filler — keep bare ``x`` as a possible inequality lhs."""
    return _strip_leading_prefixes(text, strip_bare_x=False)


def try_extract_equations_from_text(text: str) -> list[tuple[str, str]]:
    """Best-effort extraction of every `lhs=rhs` clause in the text.

    BUG FIX (was the most severe correctness bug found in the math system
    audit): this used to be a single re.search, so "solve x+y=5, x-y=1"
    silently extracted only the first clause and answered with the same
    "verified, do NOT recompute" confidence as a fully correct response.
    Walking every ``=`` here returns every clause; callers decide whether 1
    match means a single equation or 2+ means a system.
    """
    # Expand LaTeX first so ``\frac{1}{2}x = 3`` survives the ASCII-only
    # side walker (which rejects ``\`` / ``{}``).
    cleaned = _normalize_latex_to_sympy(_strip_leading_filler(text))
    pairs: list[tuple[str, str]] = []
    start = 0
    while start < len(cleaned):
        eq = cleaned.find("=", start)
        if eq == -1:
            break
        if eq + 1 < len(cleaned) and cleaned[eq + 1] == "=":
            start = eq + 2
            continue
        left = eq
        while left > 0 and cleaned[left - 1] in _EQUATION_SIDE_CHARS:
            left -= 1
        right = eq + 1
        while right < len(cleaned) and cleaned[right] in _EQUATION_SIDE_CHARS:
            right += 1
        lhs = cleaned[left:eq].strip()
        rhs = cleaned[eq + 1 : right].strip()
        if _is_equation_side(lhs) and _is_equation_side(rhs):
            pairs.append((lhs, rhs))
        start = right if right > eq + 1 else eq + 1
    return pairs


def try_extract_equation_from_text(text: str) -> EquationInput | None:
    """Best-effort SINGLE-equation extraction — kept for callers that only
    ever want one equation. See try_extract_equations_from_text for the
    multi-equation (system) case."""
    pairs = try_extract_equations_from_text(text)
    if not pairs:
        return None
    lhs, rhs = pairs[0]
    variables = guess_variables(f"{lhs} {rhs}")
    try:
        return EquationInput(lhs=lhs, rhs=rhs, variables=variables or ["x"])
    except Exception:
        return None


# Inequality operators → canonical form. Longer forms first so ``<=`` wins
# over ``<``, and ``\\leq`` wins over ``\\le``. ``\\le``/``\\ge`` must not
# match the prefix inside ``\\left`` / ``\\geq``. ASCII ``<=``/``>=`` are
# required after LaTeX normalize turns ``\\leq`` into ``<=``.
_INEQ_OPS: tuple[tuple[str, str], ...] = (
    ("\\leq", "<="),
    ("\\geq", ">="),
    ("\\le", "<="),
    ("\\ge", ">="),
    ("≤", "<="),
    ("≥", ">="),
    ("<=", "<="),
    (">=", ">="),
    ("<", "<"),
    (">", ">"),
)


def _find_inequality_ops(cleaned: str) -> list[tuple[int, int, str]]:
    """Non-overlapping ``(start, end, canon)`` hits, longest-op-first at each index."""
    hits: list[tuple[int, int, str]] = []
    i = 0
    n = len(cleaned)
    while i < n:
        matched: tuple[int, int, str] | None = None
        for op, canon in _INEQ_OPS:
            if cleaned.startswith(op, i):
                after = i + len(op)
                if op in ("\\le", "\\ge") and after < n and cleaned[after].isalpha():
                    continue
                matched = (i, after, canon)
                break
        if matched is not None:
            hits.append(matched)
            i = matched[1]
        else:
            i += 1
    return hits


def try_extract_compound_inequality_from_text(
    text: str,
) -> tuple[str, str, str, str, str] | None:
    """Extract ``low OP mid OP high`` (e.g. ``1 < x < 5``).

    Returns ``(low, low_op, mid, high_op, high)`` with canonical ops, or None.
    Must run before single-op extract so ``1 < x < 5`` is not eaten as ``1 < x``.
    """
    cleaned = _normalize_latex_to_sympy(_strip_leading_verb(text))
    hits = _find_inequality_ops(cleaned)
    if len(hits) < 2:
        return None
    for a, b in pairwise(hits):
        left = a[0]
        while left > 0 and cleaned[left - 1] in _EQUATION_SIDE_CHARS:
            left -= 1
        low = cleaned[left : a[0]].strip()
        mid = cleaned[a[1] : b[0]].strip()
        right = b[1]
        while right < len(cleaned) and cleaned[right] in _EQUATION_SIDE_CHARS:
            right += 1
        high = cleaned[b[1] : right].strip()
        if not (
            _is_equation_side(low)
            and _is_equation_side(mid)
            and _is_equation_side(high)
            and any(c.isalpha() for c in mid)
        ):
            continue
        return low, a[2], mid, b[2], high
    return None


def try_extract_inequality_from_text(text: str) -> tuple[str, str, str] | None:
    """Best-effort extraction of a single `lhs OP rhs` inequality (OP ∈
    <, >, ≤, ≥, \\leq, \\geq, \\le, \\ge). Returns (lhs, rhs, canonical_comparator)
    or None. NOTE: callers gate this on a math keyword (needs_symbolic_math)
    having already matched, so prose like "less than 5 minutes" (no keyword)
    never reaches here — bare < / > is safe in that context."""
    cleaned = _normalize_latex_to_sympy(_strip_leading_verb(text))
    best: tuple[int, str, str, str] | None = None  # (index, lhs, rhs, canon)
    for start, after, canon in _find_inequality_ops(cleaned):
        left = start
        while left > 0 and cleaned[left - 1] in _EQUATION_SIDE_CHARS:
            left -= 1
        right = after
        while right < len(cleaned) and cleaned[right] in _EQUATION_SIDE_CHARS:
            right += 1
        lhs = cleaned[left:start].strip()
        rhs = cleaned[after:right].strip()
        if _is_equation_side(lhs) and _is_equation_side(rhs):
            if best is None or start < best[0]:
                best = (start, lhs, rhs, canon)
    if best is None:
        return None
    return best[1], best[2], best[3]


def solve_compound_inequality(
    low: str,
    low_op: str,
    mid: str,
    high_op: str,
    high: str,
    variable: str,
) -> MathSolveResult:
    """Solve ``low OP mid OP high`` (e.g. ``1 < x <= 3``) as an And of relations."""
    from sympy import Ge, Gt, Le, Lt, S, solveset

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
        # ``5 > x > 1`` → x < 5 and x > 1
        lower_rel = Lt(mid_e, low_e) if low_op == ">" else Le(mid_e, low_e)
        upper_rel = Gt(mid_e, high_e) if high_op == ">" else Ge(mid_e, high_e)
    else:
        raise MathServiceError(
            f"Unsupported compound inequality direction: {low} {low_op} {mid} {high_op} {high}"
        )

    try:
        # solveset rejects And(...); solve each side and intersect on Reals.
        sol = solveset(lower_rel, sym, domain=S.Reals).intersect(
            solveset(upper_rel, sym, domain=S.Reals)
        )
    except Exception as exc:
        raise MathServiceError(
            f"Could not solve compound inequality: {low} {low_op} {mid} {high_op} {high}"
        ) from exc

    sol_latex = latex(sol)
    cmp_latex = {"<": "<", ">": ">", "<=": "\\leq", ">=": "\\geq"}
    return MathSolveResult(
        solutions_latex=[sol_latex],
        steps=[
            (
                f"Compound inequality: {latex(low_e)} {cmp_latex[low_op]} "
                f"{latex(mid_e)} {cmp_latex[high_op]} {latex(high_e)}"
            ),
            f"Solution: {sol_latex}",
        ],
        lhs_latex=latex(mid_e),
        rhs_latex=f"{latex(low_e)}, {latex(high_e)}",
    )


def solve_inequality(lhs: str, rhs: str, variable: str, comparator: str) -> MathSolveResult:
    """Solve a single-variable inequality, e.g. `x**2 - 1 > 0` → x < -1 or x > 1.

    `comparator` is the canonical form returned by try_extract_inequality_from_text
    ("<", ">", "<=", ">="). lhs/rhs go through the same allow-checked parser as
    every other expression; the relational is built from SymPy Lt/Gt/Le/Ge, so
    no user string is eval'd.
    """
    from sympy import Ge, Gt, Le, Lt, S, solve_univariate_inequality, solveset

    real = _expr_needs_real_domain(lhs, rhs)
    sym = Symbol(variable, real=True) if real else Symbol(variable)
    left = _parse_expression(lhs, [variable], real=real)
    right = _parse_expression(rhs, [variable], real=real)
    diff_expr = simplify(left - right)
    rel_cls = {"<": Lt, ">": Gt, "<=": Le, ">=": Ge}.get(comparator)
    if rel_cls is None:
        raise MathServiceError(f"Unknown inequality comparator: {comparator}")
    rel = rel_cls(diff_expr, 0)
    try:
        if real:
            sol = solveset(rel_cls(left, right), sym, domain=S.Reals)
        else:
            sol = solve_univariate_inequality(rel, sym)
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


def guess_variables(text: str) -> list[str]:
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


def compute_statistics(data: StatisticsInput) -> StatisticsResult:
    """Mean/median/mode/variance/stdev for a raw list of numbers — stdlib
    `statistics`, not SymPy (no expression parsing needed for plain floats)."""
    numbers = data.numbers
    n = len(numbers)
    total = math.fsum(numbers)
    mean_val = total / n
    median_val = _stats.median(numbers)
    # multimode() returns every value tied for most frequent — when every
    # value is unique that's the WHOLE list, which isn't a meaningful mode.
    modes = sorted(_stats.multimode(numbers))
    if len(modes) == n and n > 1:
        modes = []
    variance_population = _stats.pvariance(numbers)
    stdev_population = _stats.pstdev(numbers)
    variance_sample = _stats.variance(numbers) if n >= 2 else None
    stdev_sample = _stats.stdev(numbers) if n >= 2 else None
    range_val = max(numbers) - min(numbers)
    labels = {
        "count": str(n),
        "sum": f"{total:g}",
        "mean": f"{mean_val:g}",
        "median": f"{median_val:g}",
        "mode": ", ".join(f"{m:g}" for m in modes) if modes else "none",
        "range": f"{range_val:g}",
        "population_stdev": f"{stdev_population:.4f}",
        "sample_stdev": f"{stdev_sample:.4f}" if stdev_sample is not None else "n/a",
    }
    return StatisticsResult(
        count=n,
        numbers=numbers,
        sum=round(total, 6),
        mean=round(mean_val, 6),
        median=round(median_val, 6),
        modes=modes,
        range=round(range_val, 6),
        variance_population=round(variance_population, 6),
        stdev_population=round(stdev_population, 6),
        variance_sample=round(variance_sample, 6) if variance_sample is not None else None,
        stdev_sample=round(stdev_sample, 6) if stdev_sample is not None else None,
        labels=labels,
    )


def compute_combinatorics(data: CombinatoricsInput) -> CombinatoricsResult:
    """Factorial / nCr / nPr — plain integer arithmetic (math.factorial/comb/
    perm), not SymPy: these never touch the untrusted-expression parser."""
    if data.operation == "factorial":
        if data.n > 170:
            raise MathServiceError("Factorial input is capped at 170")
        result = math.factorial(data.n)
        return CombinatoricsResult(
            operation="factorial",
            n=data.n,
            k=None,
            result=result,
            steps=[f"{data.n}! = {result}"],
        )
    if data.k is None or data.k < 0 or data.k > data.n:
        raise MathServiceError("k must satisfy 0 <= k <= n")
    if data.operation == "combinations":
        result = math.comb(data.n, data.k)
        steps = [
            f"C({data.n},{data.k}) = {data.n}! / ({data.k}! \\times "
            f"({data.n}-{data.k})!) = {result}"
        ]
    else:
        result = math.perm(data.n, data.k)
        steps = [f"P({data.n},{data.k}) = {data.n}! / ({data.n}-{data.k})! = {result}"]
    return CombinatoricsResult(
        operation=data.operation, n=data.n, k=data.k, result=result, steps=steps
    )


def compute_number_theory(data: NumberTheoryInput) -> NumberTheoryResult:
    """GCD / LCM / prime factorization / primality / modulo — integer-only,
    bypasses the expression parser entirely (see NumberTheoryInput's bounds
    for why factorize/is_prime stay fast even on an adversarial input)."""
    a = data.a
    if data.operation in ("gcd", "lcm", "mod"):
        if data.b is None:
            raise MathServiceError(f"{data.operation} requires two integers")
        b = data.b
        if data.operation == "gcd":
            result = math.gcd(a, b)
            steps = [f"gcd({a}, {b}) = {result}"]
        elif data.operation == "lcm":
            result = math.lcm(a, b)
            steps = [f"lcm({a}, {b}) = {result}"]
        else:
            if b == 0:
                raise MathServiceError("Modulo by zero is undefined")
            result = a % b
            steps = [f"{a} \\bmod {b} = {result}"]
        return NumberTheoryResult(
            operation=data.operation, a=a, b=b, result_int=result, steps=steps
        )

    if data.operation == "factorize":
        from sympy import factorint

        if a < 2:
            raise MathServiceError("Prime factorization needs an integer >= 2")
        raw_factors = factorint(a)
        factors = {int(p): int(e) for p, e in raw_factors.items()}
        parts = [(f"{p}^{{{e}}}" if e > 1 else f"{p}") for p, e in sorted(factors.items())]
        steps = [f"{a} = " + " \\times ".join(parts)]
        return NumberTheoryResult(operation="factorize", a=a, b=None, factors=factors, steps=steps)

    # is_prime
    from sympy import isprime

    result_bool = bool(isprime(a))
    steps = [f"{a} is {'prime' if result_bool else 'not prime'}"]
    return NumberTheoryResult(
        operation="is_prime", a=a, b=None, result_bool=result_bool, steps=steps
    )


def compute_matrix(data: MatrixInput) -> MatrixResult:
    """Determinant / inverse of a small square matrix via sympy.Matrix.
    Entries are plain floats from Pydantic (never sympified from raw text),
    so this never touches the untrusted-expression parser either. Converted
    via Rational(str(v)) rather than left as float — sympy.Matrix keeps
    float entries as floats, so e.g. an inverse's 1/6 entry would otherwise
    print as the illegible "0.166666666666667" instead of a clean fraction.
    """
    from sympy import Matrix, Rational

    mat = Matrix([[Rational(str(v)) for v in row] for row in data.rows])
    det = mat.det()
    if data.operation == "determinant":
        steps = [f"\\det = {latex(det)}"]
        return MatrixResult(operation="determinant", determinant=float(det), steps=steps)

    if det == 0:
        raise MathServiceError("Matrix is singular (determinant is 0) — no inverse exists")
    inv = mat.inv()
    steps = [f"\\det = {latex(det)}", f"\\text{{inverse}} = {latex(inv)}"]
    return MatrixResult(
        operation="inverse", determinant=float(det), inverse_latex=latex(inv), steps=steps
    )
