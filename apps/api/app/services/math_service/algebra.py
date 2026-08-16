"""Solve, calculus, Newton, inequalities — SymPy."""

from __future__ import annotations

from typing import Any, Literal

from sympy import (
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
    simplify,
    solve,
)

from app.models.math_schemas import (
    EquationInput,
    MathExprResult,
    MathLimitResult,
    MathSeriesResult,
    MathSolveResult,
    MathSystemSolveResult,
    NewtonIterationStep,
    NewtonMethodInput,
    NewtonMethodResult,
    SystemOfEquationsInput,
)
from app.services.math_service.parse import (
    MathServiceError,
    _expr_needs_real_domain,
    _parse_expression,
    parse_equation,
)


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
        # School-style: write the inverse on BOTH sides, then simplify.
        # Wrong: "Subtract 3" then jump to F = 3 - 3. Right: F + 3 - 3 = 3 - 3.
        both_sides = _linear_both_sides_steps(lhs, rhs, var, c1, c0)
        if both_sides:
            return both_sides
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


def _linear_both_sides_steps(lhs: Any, rhs: Any, var: Any, c1: Any, c0: Any) -> list[str]:
    """Verified linear steps that apply add/subtract/divide to both sides."""
    if not hasattr(lhs, "as_independent") or var not in getattr(lhs, "free_symbols", set()):
        return []

    steps: list[str] = []
    indep, _dep = lhs.as_independent(var, as_Add=True)
    cur_lhs, cur_rhs = lhs, rhs

    if indep != 0 and getattr(indep, "is_number", False):
        if indep > 0:
            steps.append(
                f"Subtract {latex(indep)} from both sides: "
                f"{latex(cur_lhs)} - {latex(indep)} = {latex(cur_rhs)} - {latex(indep)}"
            )
        else:
            addend = -indep
            steps.append(
                f"Add {latex(addend)} to both sides: "
                f"{latex(cur_lhs)} + {latex(addend)} = {latex(cur_rhs)} + {latex(addend)}"
            )
        cur_lhs = simplify(cur_lhs - indep)
        cur_rhs = simplify(cur_rhs - indep)
        steps.append(f"Simplify: {latex(cur_lhs)} = {latex(cur_rhs)}")

    coeff = cur_lhs.coeff(var) if hasattr(cur_lhs, "coeff") else c1
    isolated = simplify(-c0 / c1)
    final = f"{var} = {latex(isolated)}"
    if coeff != 0 and coeff != 1 and coeff != -1:
        steps.append(
            f"Divide both sides by {latex(coeff)}: "
            f"\\frac{{{latex(cur_lhs)}}}{{{latex(coeff)}}} = "
            f"\\frac{{{latex(cur_rhs)}}}{{{latex(coeff)}}}"
        )
        steps.append(f"Simplify: {final}")
    elif coeff == -1:
        steps.append(f"Multiply both sides by -1: {latex(-cur_lhs)} = {latex(-cur_rhs)}")
        if final not in (steps[-1] if steps else ""):
            steps.append(f"Simplify: {final}")
    elif not any(final in line for line in steps):
        steps.append(f"Solve: {final}")
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
