"""Verified solvers for high-value math gaps.

All user expressions pass through the same restricted SymPy parser used by the
rest of Recall. Do not replace these calls with raw ``sympify``/``parse_expr``.
"""

from __future__ import annotations

import math
import statistics

from sympy import (
    Eq,
    Integral,
    Matrix,
    Rational,
    S,
    Symbol,
    integrate,
    latex,
    pi,
    simplify,
    solve,
    sqrt,
)
from sympy.calculus.util import continuous_domain, function_range

from app.services.math.solve.parse import (
    MathServiceError,
    _parse_expression,
    format_verified_latex,
)


def _expr(text: str, variable: str = "x"):
    return _parse_expression(text, [variable], real=True)


def _bound(text: str):
    return _parse_expression(text, [], real=True)


def _ordered_bounds(lower: str, upper: str) -> tuple[object, object]:
    lo = _bound(lower)
    hi = _bound(upper)
    try:
        width = float((hi - lo).evalf())
    except (TypeError, ValueError, OverflowError) as exc:
        raise MathServiceError("Integration bounds must be finite ordered real values") from exc
    if not math.isfinite(width) or width <= 0:
        raise MathServiceError("Upper bound must be greater than lower bound")
    return lo, hi


def solve_function_feature(
    op: str,
    expr_text: str,
    expr2_text: str | None = None,
) -> str:
    x = Symbol("x", real=True)
    expr = _expr(expr_text)

    if op == "function_domain":
        domain = continuous_domain(expr, x, S.Reals)
        return latex(domain)

    if op == "function_range":
        try:
            result = function_range(expr, x, S.Reals)
        except NotImplementedError as exc:
            raise MathServiceError(
                "Could not determine this function's range symbolically"
            ) from exc
        return latex(result)

    if op == "function_inverse":
        y = Symbol("y", real=True)
        solutions = solve(Eq(y, expr), x)
        clean = [simplify(value) for value in solutions if not value.has(x)]
        if len(clean) != 1:
            raise MathServiceError(
                "This expression does not have one verified inverse on the full real "
                "domain; specify a restricted domain"
            )
        inverse = format_verified_latex(clean[0].subs(y, x))
        return f"f^{{-1}}(x) = {inverse}"

    if op == "function_even_odd":
        reflected = simplify(expr.subs(x, -x))
        if simplify(reflected - expr) == 0:
            return "even"
        if simplify(reflected + expr) == 0:
            return "odd"
        return "neither"

    if op in {"function_compose_fg", "function_compose_gf"}:
        if expr2_text is None:
            raise MathServiceError("Composition needs both f and g")
        other = _expr(expr2_text)
        if op == "function_compose_fg":
            result = expr.subs(x, other)
            name = "f(g(x))"
        else:
            result = other.subs(x, expr)
            name = "g(f(x))"
        return f"{name} = {format_verified_latex(simplify(result))}"

    raise MathServiceError(f"Unsupported function operation: {op}")


def _matrix(rows: list[list[float]]) -> Matrix:
    return Matrix([[Rational(str(value)) for value in row] for row in rows])


def _vector_list(vectors: list[Matrix]) -> str:
    if not vectors:
        return r"\{\mathbf{0}\}"
    body = ", ".join(latex(vector) for vector in vectors)
    return rf"\operatorname{{span}}\left\{{{body}\right\}}"


def solve_matrix_feature(op: str, rows: list[list[float]]) -> str:
    mat = _matrix(rows)

    if op == "matrix_rank":
        return str(mat.rank())
    if op == "matrix_nullity":
        return str(mat.cols - mat.rank())
    if op == "matrix_nullspace":
        return _vector_list(mat.nullspace())
    if op == "matrix_columnspace":
        return _vector_list(mat.columnspace())
    if op == "matrix_rowspace":
        return _vector_list([Matrix(vector) for vector in mat.rowspace()])
    if op == "matrix_independent_columns":
        return "yes" if mat.rank() == mat.cols else "no"
    if op == "matrix_eigenvectors":
        if mat.rows != mat.cols:
            raise MathServiceError("Eigenvectors require a square matrix")
        pieces: list[str] = []
        for eigenvalue, _multiplicity, vectors in mat.eigenvects():
            basis = _vector_list(vectors)
            pieces.append(f"\\lambda={format_verified_latex(eigenvalue)}: {basis}")
        return r";\quad ".join(pieces)
    if op == "matrix_diagonalize":
        if mat.rows != mat.cols:
            raise MathServiceError("Diagonalization requires a square matrix")
        try:
            p_mat, d_mat = mat.diagonalize()
        except Exception as exc:
            raise MathServiceError(
                "Matrix is not diagonalizable over the available symbolic domain"
            ) from exc
        return f"P={latex(p_mat)},\\quad D={latex(d_mat)}"

    raise MathServiceError(f"Unsupported matrix operation: {op}")


def _paired(
    x_values: list[float],
    y_values: list[float],
) -> tuple[list[float], list[float]]:
    if len(x_values) != len(y_values) or len(x_values) < 2:
        raise MathServiceError(
            "Paired statistics need equal-length lists with at least two values"
        )
    if len(x_values) > 200:
        raise MathServiceError("Paired statistics are capped at 200 values")
    if not all(math.isfinite(v) for v in [*x_values, *y_values]):
        raise MathServiceError("Statistics values must be finite")
    return x_values, y_values


def solve_bivariate_statistics(
    op: str,
    x_values: list[float],
    y_values: list[float],
) -> str:
    xs, ys = _paired(x_values, y_values)
    n = len(xs)
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    cross = math.fsum(
        (x - mean_x) * (y - mean_y)
        for x, y in zip(xs, ys, strict=True)
    )
    ss_x = math.fsum((x - mean_x) ** 2 for x in xs)
    ss_y = math.fsum((y - mean_y) ** 2 for y in ys)

    if op == "population_covariance":
        return f"{cross / n:.6g}"
    if op == "sample_covariance":
        return f"{cross / (n - 1):.6g}"
    if op == "correlation":
        denom = math.sqrt(ss_x * ss_y)
        if denom == 0:
            raise MathServiceError(
                "Correlation is undefined when one list has zero variance"
            )
        return f"{cross / denom:.6g}"
    if op == "linear_regression":
        if ss_x == 0:
            raise MathServiceError("Regression is undefined when all x values are equal")
        slope = cross / ss_x
        intercept = mean_y - slope * mean_x
        r_squared = 1.0 if ss_y == 0 else (cross * cross) / (ss_x * ss_y)
        sign = "+" if intercept >= 0 else "-"
        return (
            f"y = {slope:.6g}x {sign} {abs(intercept):.6g},"
            f"\\quad R^2 = {r_squared:.6g}"
        )

    raise MathServiceError(f"Unsupported statistics operation: {op}")


def _closed_integral(value, label: str) -> str:
    if value.has(Integral):
        raise MathServiceError(f"No closed-form {label} was found")
    if value in {S.NaN, S.ComplexInfinity, S.Infinity, S.NegativeInfinity}:
        raise MathServiceError(f"{label.capitalize()} is not finite")
    return format_verified_latex(simplify(value))


def _integrate_absolute(expr, variable: Symbol, lower, upper):
    """Integrate |expr| by splitting at verified real zeros in the interval."""
    if simplify(expr) == 0:
        return S.Zero
    try:
        roots = solve(Eq(expr, 0), variable)
    except Exception as exc:
        raise MathServiceError("Could not locate the curve crossings symbolically") from exc
    if len(roots) > 32:
        raise MathServiceError("Too many curve crossings to verify safely")

    lo_float = float(lower.evalf())
    hi_float = float(upper.evalf())
    internal: list[tuple[float, object]] = []
    for root in roots:
        if root.has(variable) or root.is_real is False:
            continue
        try:
            root_float = float(root.evalf())
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(root_float) and lo_float < root_float < hi_float:
            if not any(abs(root_float - seen) < 1e-10 for seen, _ in internal):
                internal.append((root_float, root))
    internal.sort(key=lambda item: item[0])

    points = [lower, *(root for _, root in internal), upper]
    total = S.Zero
    for left, right in zip(points, points[1:], strict=True):
        midpoint = simplify((left + right) / 2)
        try:
            sign = float(expr.subs(variable, midpoint).evalf())
        except (TypeError, ValueError, OverflowError) as exc:
            raise MathServiceError("Could not determine the sign between crossings") from exc
        if not math.isfinite(sign):
            raise MathServiceError("The integrand is not finite between the requested bounds")
        piece = integrate(expr, (variable, left, right))
        if piece.has(Integral):
            raise MathServiceError("No closed-form integral was found")
        total += -piece if sign < 0 else piece
    return simplify(total)


def solve_calculus_application(
    op: str,
    expr_text: str,
    lower: str,
    upper: str,
    expr2_text: str | None = None,
) -> str:
    x = Symbol("x", real=True)
    expr = _expr(expr_text)
    lo, hi = _ordered_bounds(lower, upper)

    if op == "area_between_curves":
        if expr2_text is None:
            raise MathServiceError("Area between curves needs two functions")
        other = _expr(expr2_text)
        result = _integrate_absolute(expr - other, x, lo, hi)
        return _closed_integral(result, "area")

    if op == "arc_length":
        result = integrate(sqrt(1 + expr.diff(x) ** 2), (x, lo, hi))
        return _closed_integral(result, "arc length")

    if op == "volume_revolution_x":
        result = pi * integrate(expr**2, (x, lo, hi))
        return _closed_integral(result, "volume")

    if op == "volume_revolution_y":
        # Cylindrical shells. Split at sign changes so geometric volume stays
        # non-negative even when a radius/height expression crosses an axis.
        shells = _integrate_absolute(x * expr, x, lo, hi)
        return _closed_integral(2 * pi * shells, "volume")

    raise MathServiceError(f"Unsupported calculus application: {op}")
