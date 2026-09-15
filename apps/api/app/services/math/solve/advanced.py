"""Verified higher-level function, statistics, and linear-algebra operations.

This module extends existing ``calculus``, ``statistics``, and ``matrix``
MathIntent kinds via ``school_op``. It deliberately reuses the safe expression
parser and the small-matrix bounds already enforced by the main math pipeline
instead of creating a second symbolic-math path.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

from sympy import Eq, S, Symbol, latex, simplify, solve
from sympy.calculus.util import continuous_domain, function_range
from sympy.matrices.exceptions import MatrixError

from app.services.math.solve.discrete import _matrix_from_rows
from app.services.math.solve.parse import MathServiceError, _parse_expression

FunctionFeature = Literal["domain", "range", "inverse", "composition"]
BivariateStatisticsFeature = Literal[
    "correlation",
    "regression",
    "covariance_sample",
    "covariance_population",
]
MatrixFeature = Literal[
    "rank",
    "nullspace",
    "columnspace",
    "rowspace",
    "eigenvectors",
    "diagonalize",
]


def compute_function_feature(
    operation: FunctionFeature,
    expr: str,
    variable: str = "x",
    *,
    expr2: str | None = None,
) -> tuple[str, list[str]]:
    """Return ``(canonical_answer, verified_steps)`` for a function feature."""
    if not expr.strip():
        raise MathServiceError("function expression is required")
    # Match the parser's plain Symbol(variable). Adding assumptions here creates
    # a distinct SymPy symbol with the same printed name, so substitutions can
    # silently fail (e.g. composition would return the original expression).
    x = Symbol(variable)
    parsed = _parse_expression(expr, [variable])

    if operation == "domain":
        try:
            result = continuous_domain(parsed, x, S.Reals)
        except (NotImplementedError, ValueError, TypeError) as exc:
            raise MathServiceError("could not determine the real domain") from exc
        answer = latex(result)
        return answer, [f"\\operatorname{{Dom}}(f) = {answer}"]

    if operation == "range":
        try:
            domain = continuous_domain(parsed, x, S.Reals)
            result = function_range(parsed, x, domain)
        except (NotImplementedError, ValueError, TypeError) as exc:
            raise MathServiceError("could not determine the real range") from exc
        answer = latex(result)
        return answer, [
            f"\\operatorname{{Dom}}(f) = {latex(domain)}",
            f"\\operatorname{{Range}}(f) = {answer}",
        ]

    if operation == "inverse":
        y = Symbol("__inverse_y")
        try:
            branches = solve(Eq(y, parsed), x)
        except (NotImplementedError, ValueError, TypeError) as exc:
            raise MathServiceError("could not solve for an inverse function") from exc
        # A multi-branch relation is not a single inverse function on the full
        # real domain. Refuse instead of silently choosing +sqrt / -sqrt.
        if len(branches) != 1:
            raise MathServiceError(
                "function does not have a unique real inverse on the stated domain"
            )
        candidate = simplify(branches[0])
        try:
            verified = simplify(parsed.subs(x, candidate) - y) == 0
        except Exception as exc:  # SymPy verification failure, not user error.
            raise MathServiceError("could not verify the inverse function") from exc
        if not verified:
            raise MathServiceError("inverse candidate failed symbolic verification")
        display = simplify(candidate.subs(y, x))
        answer = f"f^{{-1}}({variable}) = {latex(display)}"
        return answer, [answer]

    if expr2 is None or not expr2.strip():
        raise MathServiceError("composition requires two function expressions")
    inner = _parse_expression(expr2, [variable])
    composed = simplify(parsed.subs(x, inner))
    answer = latex(composed)
    return answer, [f"(f\\circ g)({variable}) = {answer}"]


def _format_stat_number(value: float) -> str:
    if abs(value) < 5e-13:
        value = 0.0
    return f"{value:.12g}"


def compute_bivariate_statistics(
    x_values: Sequence[float],
    y_values: Sequence[float],
    operation: BivariateStatisticsFeature,
) -> tuple[str, list[str]]:
    """Correlation, covariance, and least-squares regression for paired data."""
    if len(x_values) != len(y_values) or len(x_values) < 2:
        raise MathServiceError("paired statistics need equal-length lists with at least 2 values")
    if len(x_values) > 200:
        raise MathServiceError("paired statistics are capped at 200 values")
    if any(not math.isfinite(v) for v in (*x_values, *y_values)):
        raise MathServiceError("statistics values must be finite numbers")

    n = len(x_values)
    mean_x = math.fsum(x_values) / n
    mean_y = math.fsum(y_values) / n
    centered_x = [value - mean_x for value in x_values]
    centered_y = [value - mean_y for value in y_values]
    cross = math.fsum(a * b for a, b in zip(centered_x, centered_y, strict=True))
    sum_x2 = math.fsum(value * value for value in centered_x)
    sum_y2 = math.fsum(value * value for value in centered_y)

    if operation == "covariance_population":
        covariance = cross / n
        answer = _format_stat_number(covariance)
        return answer, [f"population covariance = {answer}"]

    if operation == "covariance_sample":
        covariance = cross / (n - 1)
        answer = _format_stat_number(covariance)
        return answer, [f"sample covariance = {answer}"]

    if operation == "correlation":
        denominator = math.sqrt(sum_x2 * sum_y2)
        if denominator == 0:
            raise MathServiceError("correlation is undefined when either data list is constant")
        correlation = cross / denominator
        # Clamp tiny floating-point excursions outside the mathematical range.
        correlation = max(-1.0, min(1.0, correlation))
        answer = _format_stat_number(correlation)
        return answer, [f"Pearson r = {answer}"]

    if sum_x2 == 0:
        raise MathServiceError("linear regression needs at least two distinct x values")
    slope = cross / sum_x2
    intercept = mean_y - slope * mean_x
    slope_text = _format_stat_number(slope)
    intercept_text = _format_stat_number(abs(intercept))
    sign = "+" if intercept >= 0 else "-"
    answer = f"y = {slope_text}x {sign} {intercept_text}"
    return answer, [
        f"least-squares slope = {slope_text}",
        f"intercept = {_format_stat_number(intercept)}",
        answer,
    ]


def _basis_latex(vectors: Sequence[object]) -> str:
    if not vectors:
        return r"\{0\}"
    return r"\operatorname{span}\left\{" + ", ".join(latex(v) for v in vectors) + r"\right\}"


def compute_matrix_feature(
    rows: list[list[float]], operation: MatrixFeature
) -> tuple[str, list[str]]:
    """Verified undergraduate linear-algebra operations on a small matrix."""
    mat = _matrix_from_rows(rows)

    if operation == "rank":
        rank = int(mat.rank())
        answer = str(rank)
        return answer, [f"\\operatorname{{rank}}(A) = {answer}"]

    if operation == "nullspace":
        answer = _basis_latex(mat.nullspace())
        return answer, [f"\\operatorname{{Null}}(A) = {answer}"]

    if operation == "columnspace":
        answer = _basis_latex(mat.columnspace())
        return answer, [f"\\operatorname{{Col}}(A) = {answer}"]

    if operation == "rowspace":
        answer = _basis_latex(mat.rowspace())
        return answer, [f"\\operatorname{{Row}}(A) = {answer}"]

    if mat.rows != mat.cols:
        raise MathServiceError("eigenvectors/diagonalization require a square matrix")

    if operation == "eigenvectors":
        pieces: list[str] = []
        for eigenvalue, _multiplicity, basis in mat.eigenvects():
            basis_text = _basis_latex(basis)
            pieces.append(f"\\lambda={latex(eigenvalue)}:\\; {basis_text}")
        answer = r";\quad ".join(pieces)
        return answer, [answer]

    try:
        p, d = mat.diagonalize()
    except (MatrixError, ValueError) as exc:
        raise MathServiceError("matrix is not diagonalizable") from exc
    answer = f"P={latex(p)},\\quad D={latex(d)}"
    return answer, ["A=PDP^{-1}", answer]
