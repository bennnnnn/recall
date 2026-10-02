"""Solve an expression operation: one catalog law, evaluated for its givens.

The catalog states the law and, for each set of givens, the arithmetic that
answers it (``u = v - at`` for v, a and t). This solver evaluates that
arithmetic in SI and prints the formula and the substitution from the same
expression, so the working is the computation.
"""

from __future__ import annotations

import math

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.display import si_symbol
from app.modules.physics.expression import evaluate, to_latex
from app.modules.physics.solvers.common import (
    PhysicsResult,
    QuantityResult,
    _params_in_si,
    solved,
)
from app.services.solving import SolveServiceError


def solve_expression(intent: PhysicsIntent) -> PhysicsResult:
    from app.modules.physics.catalog import CATALOG, matching_variant

    spec = CATALOG.get(intent.physics_op or "")
    if spec is None or spec.expression is None or spec.binding is None:
        raise SolveServiceError(f"{intent.physics_op} is not an expression operation")
    params = _params_in_si(intent)
    variant = matching_variant(spec, params)
    expression = spec.expression
    symbol = spec.result_symbol
    if variant is not None:
        expression = variant.expression or expression
        symbol = variant.result_symbol or symbol
    try:
        value = evaluate(expression, params)
    except (KeyError, ValueError, OverflowError) as exc:
        raise SolveServiceError(f"{spec.id} has no real answer for these givens") from exc
    if not math.isfinite(value):
        raise SolveServiceError(f"{spec.id} answer is not finite")
    if spec.binding.nonnegative and value < 0:
        raise SolveServiceError(f"{spec.id} gives a negative {symbol} for these givens")
    symbols = {variable.name: variable.symbol for variable in spec.variables}
    formula = f"{symbol} = {to_latex(expression, symbols)}"
    substitution = f"{symbol} = {to_latex(expression, symbols, params)}"
    return solved(
        QuantityResult("", value, si_symbol(spec.binding.result[0])),
        answer=substitution,
        formula=formula,
        substitution=substitution,
    )
