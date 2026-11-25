"""Simplify, factor and expand an expression."""

from __future__ import annotations

from typing import Any

from sympy import expand, factor, latex

from app.modules.math.schemas import MathExprResult
from app.modules.math.solve.display import format_verified_latex
from app.modules.math.solve.parse import parse_expression
from app.modules.math.solve.poly_size import (
    MAX_EXPANDED_TERMS,
    MAX_FACTOR_DEGREE,
    add_nodes,
    expansion_size,
    size_degree,
)
from app.modules.math.solve.real_reading import complex_without_cause, read_written
from app.modules.math.solve.simplest_form import simplest_form
from app.services.solving import SolveServiceError


def simplify_expression(expr: str, variable: str = "x") -> MathExprResult:
    # School-level simplification is over the reals unless the prompt names a
    # complex domain.  The real assumption is essential for identities such
    # as sqrt(x^2) = |x|; an unconstrained complex symbol leaves it unchanged.
    parse_expression(expr, [variable], real=True)  # the evaluated parse's checks
    # Read as written: evaluated, (-2.5)^(2/3) is already SymPy's complex principal value.
    written = parse_expression(expr, [variable], real=True, evaluate=False)
    result, book_latex = simplest_form(read_written(written), written)
    if complex_without_cause(written, result):
        raise SolveServiceError("could not verify: an odd root kept no real value")
    return MathExprResult(result=str(result), latex=book_latex or format_verified_latex(result))


def factor_expression(expr: str, variable: str = "x") -> MathExprResult:
    """Factor a polynomial/expression into a product of irreducible factors."""
    parsed = parse_expression(expr, [variable])
    _refuse_large_factoring(parsed)
    result = factor(parsed)
    # General display simplification can expand a product again. Preserve
    # the requested factor form, including exact symbolic coefficients.
    return MathExprResult(result=str(result), latex=latex(result))


def expand_expression(expr: str, variable: str = "x") -> MathExprResult:
    """Expand a factored expression into a sum of terms."""
    parsed = parse_expression(expr, [variable])
    if expansion_size(parsed) > MAX_EXPANDED_TERMS:
        raise SolveServiceError("Expression too large to expand")
    result = expand(parsed)
    return MathExprResult(result=str(result), latex=latex(result))


def _refuse_large_factoring(parsed: Any) -> None:
    """``factor`` expands each sum in the expression and factors it: one of high degree,
    or one whose expansion is huge, runs past the solve's deadline ("(x+1)^300 - 1",
    "1/(x+1)^300 - 1", which it puts over one denominator).
    A power of a small sum ("(x+1)^3000") factors its base alone and stays."""
    for node in add_nodes(parsed):
        degree = size_degree(node)
        if (degree is not None and degree > MAX_FACTOR_DEGREE) or (
            expansion_size(node) > MAX_EXPANDED_TERMS
        ):
            raise SolveServiceError("Expression too large to factor")
