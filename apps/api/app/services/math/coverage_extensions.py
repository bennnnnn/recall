"""Small verified math extensions not covered by the main solver modules."""

from __future__ import annotations

from sympy import Matrix, Rational, Symbol, simplify

from app.services.math.solve.parse import MathServiceError, _parse_expression


def function_parity(expr_text: str, variable: str = "x") -> str:
    """Classify a real single-variable expression as even, odd, or neither."""
    if not expr_text.strip():
        raise MathServiceError("function expression is required")
    expr = _parse_expression(expr_text, [variable], real=True)
    symbol = Symbol(variable, real=True)
    extra = {str(item) for item in expr.free_symbols if str(item) != variable}
    if extra:
        raise MathServiceError("function parity supports one variable at a time")
    reflected = simplify(expr.subs(symbol, -symbol))
    if simplify(reflected - expr) == 0:
        return "even"
    if simplify(reflected + expr) == 0:
        return "odd"
    return "neither"


def _matrix(rows: list[list[float]]) -> Matrix:
    if len(rows) < 2 or len(rows) > 4:
        raise MathServiceError("matrix must have between 2 and 4 rows")
    width = len(rows[0]) if rows else 0
    if width < 1 or width > 4 or any(len(row) != width for row in rows):
        raise MathServiceError("matrix rows must be rectangular and at most 4 wide")
    return Matrix([[Rational(str(value)) for value in row] for row in rows])


def matrix_nullity(rows: list[list[float]]) -> str:
    matrix = _matrix(rows)
    return str(matrix.cols - matrix.rank())


def matrix_columns_independent(rows: list[list[float]]) -> str:
    matrix = _matrix(rows)
    return "yes" if matrix.rank() == matrix.cols else "no"
