"""Simplify, factor and expand an expression, and the factorization an equation's answer
shows as its key step."""

from __future__ import annotations

from sympy import Poly, Symbol, degree, expand, factor, latex, simplify

from app.modules.math.schemas import MathExprResult
from app.modules.math.solve.declines import sympy_decline
from app.modules.math.solve.display import format_verified_latex
from app.modules.math.solve.parse import parse_expression


def simplify_expression(expr: str, variable: str = "x") -> MathExprResult:
    # School-level simplification is over the reals unless the prompt names a
    # complex domain.  The real assumption is essential for identities such
    # as sqrt(x^2) = |x|; an unconstrained complex symbol leaves it unchanged.
    parsed = parse_expression(expr, [variable], real=True)
    result = simplify(parsed)
    return MathExprResult(result=str(result), latex=format_verified_latex(result))


def factor_expression(expr: str, variable: str = "x") -> MathExprResult:
    """Factor a polynomial/expression into a product of irreducible factors."""
    parsed = parse_expression(expr, [variable])
    result = factor(parsed)
    # General display simplification can expand a product again. Preserve
    # the requested factor form, including exact symbolic coefficients.
    return MathExprResult(result=str(result), latex=latex(result))


def expand_expression(expr: str, variable: str = "x") -> MathExprResult:
    """Expand a factored expression into a sum of terms."""
    parsed = parse_expression(expr, [variable])
    result = expand(parsed)
    return MathExprResult(result=str(result), latex=latex(result))


def factored_key_step(lhs: str, rhs: str, variable: str = "x") -> str | None:
    """LaTeX factorization of ``lhs - rhs``, when factoring is the actual step.

    A smart person answering "solve x^2 - 5x + 6 = 0" says "factors as
    (x-2)(x-3), so x = 2 or x = 3" — the one line that shows where the answer
    came from. This returns that line's factorization, or None when there is no
    step worth showing: linear equations (one operation), and polynomials that
    do not factor over the rationals, where the quadratic formula did the work
    and naming it adds nothing.
    """
    with sympy_decline():
        symbol = Symbol(variable)
        expr = simplify(parse_expression(lhs, [variable]) - parse_expression(rhs, [variable]))
        if degree(Poly(expr, symbol)) < 2:
            return None
        factored = factor(expr)
        if factored == expr:
            return None
        # A product of factors, or a perfect power like (x + 1)^2.
        if not (factored.is_Mul or factored.is_Pow):
            return None
        return str(latex(factored))
    return None
