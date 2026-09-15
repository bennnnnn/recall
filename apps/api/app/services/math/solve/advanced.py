"""Verified higher-level function and linear-algebra operations.

This module extends existing ``calculus`` and ``matrix`` MathIntent kinds via
``school_op``. It deliberately reuses the safe expression parser and the
small-matrix bounds already enforced by the main math pipeline instead of
creating a second symbolic-math path.
"""

from __future__ import annotations

from typing import Literal

from sympy import Eq, S, Symbol, latex, simplify, solve
from sympy.calculus.util import continuous_domain, function_range
from sympy.matrices.exceptions import MatrixError

from app.services.math.solve.discrete import _matrix_from_rows
from app.services.math.solve.parse import MathServiceError, _parse_expression

FunctionFeature = Literal["domain", "range", "inverse", "composition"]
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


def _basis_latex(vectors: list[object]) -> str:
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
