"""One equation solved by SymPy as school algebra reads it: refused without its unknown or
above the degree cap, an odd root of a negative kept real, non-real roots dropped when a real
one exists, and an identity told apart from a contradiction.

Systems are ``systems.py``, inequalities ``inequalities.py``, Newton's method ``numeric.py``,
simplify/factor/expand ``expressions.py`` and calculus ``calculus.py``.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from sympy import Symbol, latex, oo, simplify, solve

from app.core.config import get_settings
from app.modules.math.schemas import EquationInput, MathSolveResult, RejectedRootLatex
from app.modules.math.solve.declines import declines
from app.modules.math.solve.equation_conditions import (
    _parameter_solution_conditions,
    original_domain_conditions,
)
from app.modules.math.solve.odd_roots import real_odd_root_solutions
from app.modules.math.solve.parse import (
    SolveServiceError,
    _expr_needs_real_domain,
    parse_equation,
)
from app.modules.math.solve.real_domain import (
    RejectedRoot,
    not_real,
    rejection,
    written_domain_rules,
)
from app.modules.math.solve.root_latex import (
    _solution_value_latex,
    compact_root_answer_lines,
    expr_equal,
)


def _worked_isolation_steps(lhs: Any, rhs: Any, variable: str) -> list[str]:
    """String form of the structured equation trace for the verified-math hint."""
    from app.modules.math.solve.key_steps import equation_key_steps, stringify_key_steps

    return stringify_key_steps(equation_key_steps(lhs, rhs, variable))


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


def _reject_high_degree(lhs: Any, rhs: Any, variables: list[str]) -> None:
    """Refuse high-degree polynomials before ``solve()`` occupies the 5s pool."""
    max_degree = get_settings().math_max_poly_degree
    expr = lhs - rhs
    for name in variables:
        poly = expr.as_poly(Symbol(name))
        if poly is None:
            continue
        deg = poly.degree()
        # Identities like x = x have degree -oo.
        if deg == -oo:
            continue
        try:
            degree = int(deg)
        except TypeError:
            continue
        if degree > max_degree:
            raise SolveServiceError("Polynomial degree too high")


def _require_unknown(data: EquationInput, lhs: Any, rhs: Any) -> None:
    """Refuse an equation that does not contain the unknown it is solved for.

    ``F = ma`` solved for x has no x in it, and the empty solution set was
    certified as "no solution". A contradiction such as ``x - x = 5`` keeps
    its x in the written text after SymPy cancels it, so it still reads as
    one, and so does ``0 = 1``, which has no letter at all.
    """
    present = {str(symbol) for symbol in lhs.free_symbols | rhs.free_symbols}
    if not present or any(name in present for name in data.variables):
        return
    written = f"{data.lhs} {data.rhs}"
    if any(
        re.search(rf"(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])", written)
        for name in data.variables
    ):
        return
    raise SolveServiceError(f"{', '.join(data.variables)} does not appear in the equation")


def solve_equation(data: EquationInput) -> MathSolveResult:
    equation, lhs, rhs = parse_equation(data)
    _require_unknown(data, lhs, rhs)
    _reject_high_degree(lhs, rhs, data.variables)
    real = _expr_needs_real_domain(data.lhs, data.rhs)
    syms = [Symbol(v, real=True) if real else Symbol(v) for v in data.variables]
    original_excluded: list[Any] = []
    domain_conditions: list[str] = []
    if len(syms) == 1:
        original_excluded, domain_conditions = original_domain_conditions(data, syms[0])
    if len(syms) == 1:
        from app.modules.math.solve.trig_equations import solve_real_trig_equation

        trig_result = solve_real_trig_equation(lhs, rhs, syms[0])
        if trig_result is not None:
            return trig_result
    try:
        fractional = real_odd_root_solutions(lhs, rhs, syms[0]) if len(syms) == 1 else None
        raw_solutions = (
            [{syms[0]: value} for value in fractional]
            if fractional is not None
            else solve(equation, syms, dict=True)
        )
    except Exception as exc:
        raise SolveServiceError("Could not solve equation") from exc

    if original_excluded:
        raw_solutions = [
            solution
            for solution in raw_solutions
            if all(
                sym not in solution
                or all(not expr_equal(solution[sym], value) for value in original_excluded)
                for sym in syms
            )
        ]
    rejected: list[RejectedRoot] = []
    if len(syms) == 1 and not data.complex_roots:
        raw_solutions, rejected = _in_real_domain(data, syms[0], raw_solutions)
        raw_solutions = _real_roots_when_any(raw_solutions, syms[0])

    parameter_conditions: list[str] = []
    alternate_cases: list[str] = []
    if len(syms) == 1:
        parameter_conditions, alternate_cases = _parameter_solution_conditions(
            lhs, rhs, syms[0], raw_solutions
        )

    solutions_latex: list[str] = []
    values_by_var: dict[str, list[Any]] = {}
    for sol in raw_solutions:
        for sym, val in sol.items():
            solutions_latex.append(f"{latex(sym)} = {_solution_value_latex(val)}")
            values_by_var.setdefault(str(sym), []).append(val)

    if not solutions_latex and raw_solutions:
        solutions_latex = [latex(s) for s in raw_solutions]

    canonical_solutions_latex: list[str] = []
    if len(data.variables) == 1 and data.variables[0] in values_by_var:
        canonical_solutions_latex = compact_root_answer_lines(
            data.variables[0],
            values_by_var[data.variables[0]],
        )

    steps = [
        f"Equation: {latex(lhs)} = {latex(rhs)}",
    ]
    # Include verified intermediate isolation steps for the common single-
    # variable forms so the model copies them instead of inventing wrong ones.
    if len(data.variables) == 1:
        steps.extend(_worked_isolation_steps(lhs, rhs, data.variables[0]))

    solution_kind = _concluded(steps, solutions_latex, rejected, lhs, rhs)
    return MathSolveResult(
        solutions_latex=solutions_latex,
        canonical_solutions_latex=canonical_solutions_latex,
        steps=steps,
        lhs_latex=latex(lhs),
        rhs_latex=latex(rhs),
        solution_kind=solution_kind,
        domain_conditions_latex=[*domain_conditions, *parameter_conditions],
        alternate_cases_latex=alternate_cases,
        rejected_roots=[RejectedRootLatex(root=item.root, why=item.why) for item in rejected],
    )


def _concluded(
    steps: list[str], solutions_latex: list[str], rejected: list[RejectedRoot], lhs: Any, rhs: Any
) -> Literal["finite", "none", "infinite"]:
    """The roots rejected (each one the trace did not check itself), then what the solve
    concludes, written into ``steps``."""
    steps.extend(
        f"Check {item.root} in the original equation: {item.why}, so it is rejected."
        for item in rejected
        if not any(step.startswith(f"Check ${item.root}$") for step in steps)
    )
    if solutions_latex:
        steps.append(f"Solutions: {', '.join(solutions_latex)}")
        return "finite"
    if rejected:
        steps.append("No real solution: every root SymPy found is rejected above.")
        return "none"
    kind = _classify_no_solution(lhs, rhs)
    if kind == "infinite":
        steps.append("Infinitely many solutions (equation is an identity, true for all values).")
    else:
        steps.append("No solutions found (equation is a contradiction).")
    return kind


def _in_real_domain(
    data: EquationInput, sym: Any, solutions: list[dict[Any, Any]]
) -> tuple[list[dict[Any, Any]], list[RejectedRoot]]:
    """The roots the equation as written allows over the reals, and each one it rejects.

    A logarithm needs a positive argument and an even root a radicand >= 0 (``real_domain``).
    A question that asked for real solutions keeps no non-real root: when no real one is
    left, each is rejected as not real (``x^2 + 1 = 0`` over the reals has none); beside a
    real one they go unsaid, as ``_real_roots_when_any`` drops them.
    """
    rules = written_domain_rules(data.lhs, data.rhs, data.variables)
    kept: list[dict[Any, Any]] = []
    rejected: list[RejectedRoot] = []
    for solution in solutions:
        value = solution.get(sym)
        why = None if value is None else rejection(rules, str(sym), value)
        if why is None:
            kept.append(solution)
        else:
            rejected.append(RejectedRoot(root=f"{latex(sym)} = {latex(value)}", why=why))
    if not data.real_only:
        return kept, rejected
    unreal = [item for item in kept if _known_realness(item.get(sym)) is False]
    if len(unreal) < len(kept):
        return [item for item in kept if item not in unreal], rejected
    return [], [*rejected, *(not_real(str(sym), item[sym]) for item in unreal)]


def _real_roots_when_any(solutions: list[dict[Any, Any]], sym: Any) -> list[dict[Any, Any]]:
    """Drop non-real roots when a real one exists: ``x^3 = 8`` is ``x = 2``.

    A root whose realness SymPy cannot decide (it depends on a parameter) is
    kept. With no real root, every root stays, so ``x^2 + 1 = 0`` keeps ``±i``.
    """
    real = [solution for solution in solutions if _known_realness(solution.get(sym)) is True]
    if not real:
        return solutions
    return [solution for solution in solutions if _known_realness(solution.get(sym)) is not False]


@declines(None)
def _known_realness(value: Any) -> bool | None:
    if value is None:
        return None
    return value.is_real
