"""Derivatives, integrals, limits and series — SymPy, with verified worked lines."""

from __future__ import annotations

from typing import Any

from sympy import (
    Integral,
    Mul,
    Sum,
    Symbol,
    diff,
    integrate,
    latex,
    limit,
    oo,
    simplify,
    zoo,
)

from app.modules.math.schemas import (
    MathExprResult,
    MathLimitResult,
    MathSeriesResult,
)
from app.modules.math.solve.algebra import _expr_equal
from app.modules.math.solve.parse import (
    MathServiceError,
    _parse_expression,
    format_verified_latex,
)


def _term_derivative_step(term: Any, sym: Any) -> str:
    """One verified worked line for the derivative of a single term, naming
    the rule by structure. The derivative itself is always SymPy-computed so
    the shown value is verified; the rule label is a best-effort classification
    (power/constant-multiple/product/quotient/chain) so the model can copy a
    real derivation instead of inventing one."""
    deriv = diff(term, sym)
    lhs = f"\\frac{{d}}{{d{latex(sym)}}}\\left[{latex(term)}\\right]"
    # Constant: no occurrence of the differentiation variable.
    if not term.free_symbols & {sym}:
        return f"Constant rule: ${lhs} = 0$"
    # Power rule: x or x^n with base == sym.
    if term == sym:
        return f"Power rule: ${lhs} = {latex(deriv)}$"
    if getattr(term, "is_Pow", False) and term.base == sym:
        return (
            f"Power rule: ${lhs} = {latex(term.exp)} \\cdot "
            f"{latex(sym)}^{{{latex(term.exp - 1)}}} = {latex(deriv)}$"
        )
    # Product / quotient / constant-multiple.
    if getattr(term, "is_Mul", False):
        dep = [f for f in term.args if f.free_symbols & {sym}]
        if len(dep) == 1:
            const = [f for f in term.args if not (f.free_symbols & {sym})]
            return (
                f"Constant multiple: ${lhs} = {latex(Mul(*const) if const else 1)} \\cdot "
                f"\\frac{{d}}{{d{latex(sym)}}}\\left[{latex(dep[0])}\\right] = {latex(deriv)}$"
            )
        return f"Product rule: ${lhs} = {latex(deriv)}$"
    if getattr(term, "is_Pow", False) and term.base != sym:
        # e.g. e^x, 2^x, sin(x)^2 — chain rule territory.
        return f"Chain rule: ${lhs} = {latex(deriv)}$"
    # Anything else with a function of sym (sin, cos, exp, log, …) → chain rule.
    return f"Chain rule: ${lhs} = {latex(deriv)}$"


def _differentiation_steps(parsed: Any, sym: Any, result_latex: str) -> list[str]:
    """Verified step-by-step derivation for a single-variable derivative.

    Sums are split by the sum rule (linearity); each term gets a rule-named
    line with its SymPy-computed derivative; the final result line closes.
    """
    steps: list[str] = []
    if getattr(parsed, "is_Add", False):
        steps.append(
            f"Sum rule (linearity): $\\frac{{d}}{{d{latex(sym)}}}\\left[{latex(parsed)}\\right] "
            f"= \\sum \\frac{{d}}{{d{latex(sym)}}}\\left[\\text{{each term}}\\right]$"
        )
        for term in parsed.args:
            steps.append(_term_derivative_step(term, sym))
    else:
        steps.append(_term_derivative_step(parsed, sym))
    steps.append(
        f"Result: $\\frac{{d}}{{d{latex(sym)}}}\\left[{latex(parsed)}\\right] = {result_latex}$"
    )
    return steps


def differentiate_expression(expr: str, variable: str = "x", order: int = 1) -> MathExprResult:
    if order < 1 or order > 4:
        raise MathServiceError("unsupported derivative order")
    sym = Symbol(variable)
    parsed = _parse_expression(expr, [variable])
    result = diff(parsed, sym, order)
    result_latex = format_verified_latex(result)
    if order == 1:
        steps = _differentiation_steps(parsed, sym, result_latex)
    else:
        ordinals = {1: "First", 2: "Second", 3: "Third", 4: "Fourth"}
        current = parsed
        steps = []
        for index in range(1, order + 1):
            current = diff(current, sym)
            derivative_tex = (
                rf"\frac{{d}}{{d{latex(sym)}}}"
                if index == 1
                else rf"\frac{{d^{{{index}}}}}{{d{latex(sym)}^{{{index}}}}}"
            )
            steps.append(f"**{ordinals[index]} derivative**\n${derivative_tex} = {latex(current)}$")
    return MathExprResult(
        result=str(result),
        latex=result_latex,
        steps=steps,
    )


def differentiate_at_point(expr: str, variable: str, point: str) -> MathExprResult:
    """Evaluate the two-sided derivative definition at a named real point."""
    sym = Symbol(variable, real=True)
    parsed = _parse_expression(expr, [variable], real=True)
    at = _parse_expression(point, [variable], real=True)
    quotient = simplify((parsed - parsed.subs(sym, at)) / (sym - at))
    try:
        left = limit(quotient, sym, at, dir="-")
        right = limit(quotient, sym, at, dir="+")
    except Exception as exc:
        raise MathServiceError("Could not evaluate derivative at the requested point") from exc
    finite = bool(left.is_finite is True and right.is_finite is True)
    if not finite or not _expr_equal(left, right):
        if finite:
            reason = (
                f"Left derivative: {latex(left)}; right derivative: {latex(right)}; "
                "they do not agree."
            )
        else:
            reason = "The difference quotient is not finite from both sides."
        return MathExprResult(
            result="undefined",
            latex=r"\text{undefined}",
            steps=[reason],
        )
    value = simplify(left)
    return MathExprResult(
        result=str(value),
        latex=format_verified_latex(value),
        steps=[f"The left- and right-hand difference quotients both equal {latex(value)}."],
    )


def integrate_expression(expr: str, variable: str = "x") -> MathExprResult:
    sym = Symbol(variable)
    parsed = _parse_expression(expr, [variable])
    result = integrate(parsed, sym)
    # integrate() can fail to find a closed form and hand back a result that
    # still contains an unevaluated Integral(...) rather than raising —
    # callers must not treat that as a verified, fully-solved answer.
    solved = not result.has(Integral)
    return MathExprResult(result=str(result), latex=format_verified_latex(result), solved=solved)


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
    return MathExprResult(result=str(result), latex=format_verified_latex(result), solved=solved)


def integrate_double(
    expr: str,
    variable: str,
    lower: str,
    upper: str,
    variable2: str,
    lower2: str,
    upper2: str,
) -> MathExprResult:
    """Definite double integral over a named axis-aligned rectangle."""
    parsed = _parse_expression(expr, [variable, variable2])
    a = _parse_infinity_aware_point(lower)
    b = _parse_infinity_aware_point(upper)
    c = _parse_infinity_aware_point(lower2)
    d = _parse_infinity_aware_point(upper2)
    try:
        result = integrate(
            parsed,
            (Symbol(variable), a, b),
            (Symbol(variable2), c, d),
        )
    except Exception as exc:
        raise MathServiceError(f"Could not compute double integral of: {expr}") from exc
    solved = not result.has(Integral)
    return MathExprResult(result=str(result), latex=format_verified_latex(result), solved=solved)


def integrate_triple(
    expr: str,
    variable: str,
    lower: str,
    upper: str,
    variable2: str,
    lower2: str,
    upper2: str,
    variable3: str,
    lower3: str,
    upper3: str,
) -> MathExprResult:
    """Definite triple integral over a named axis-aligned box."""
    parsed = _parse_expression(expr, [variable, variable2, variable3])
    a = _parse_infinity_aware_point(lower)
    b = _parse_infinity_aware_point(upper)
    c = _parse_infinity_aware_point(lower2)
    d = _parse_infinity_aware_point(upper2)
    e = _parse_infinity_aware_point(lower3)
    f = _parse_infinity_aware_point(upper3)
    try:
        result = integrate(
            parsed,
            (Symbol(variable), a, b),
            (Symbol(variable2), c, d),
            (Symbol(variable3), e, f),
        )
    except Exception as exc:
        raise MathServiceError(f"Could not compute triple integral of: {expr}") from exc
    solved = not result.has(Integral)
    return MathExprResult(result=str(result), latex=format_verified_latex(result), solved=solved)


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
    # School limits are over a real input unless another domain is stated.
    # Real assumptions are required for piecewise/absolute-value behavior:
    # without them SymPy cannot decide lim |x|/x at 0.
    sym = Symbol(variable, real=True)
    parsed = _parse_expression(expr, [variable], real=True)
    point_val = _parse_infinity_aware_point(point)
    try:
        result = limit(parsed, sym, point_val, dir=direction)
    except ValueError as exc:
        if direction != "+-":
            raise MathServiceError(f"Could not compute limit of: {expr}") from exc
        try:
            left = limit(parsed, sym, point_val, dir="-")
            right = limit(parsed, sym, point_val, dir="+")
            result = left if simplify(left - right) == 0 else zoo
        except Exception as side_exc:
            raise MathServiceError(f"Could not compute limit of: {expr}") from side_exc
    except Exception as exc:
        raise MathServiceError(f"Could not compute limit of: {expr}") from exc
    # A limit can legitimately evaluate to oo/-oo (diverges) or zoo (the
    # two-sided limit doesn't exist because the two sides disagree). Keep
    # the symbolic result so presentation can distinguish these statuses.
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
        solved=not result.has(Sum),
        is_convergent=None if is_convergent is None else bool(is_convergent),
        is_absolutely_convergent=(
            None if is_absolutely_convergent is None else bool(is_absolutely_convergent)
        ),
    )
