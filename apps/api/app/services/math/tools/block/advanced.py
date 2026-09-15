"""Verified-block wrappers for advanced math operations.

The existing kind registry stays unchanged: advanced features reuse the
``calculus``, ``matrix``, and ``statistics`` kinds and are distinguished by
``school_op``.  Unsupported operations fall straight back to the established
builders.
"""

from __future__ import annotations

from app.core.config import Settings
from app.models.schemas.math import MathIntent
from app.services.math.solve.advanced import (
    solve_bivariate_statistics,
    solve_calculus_application,
    solve_function_feature,
    solve_matrix_feature,
)
from app.services.math.tools.block.common import VerifiedMathBlock, _finish_with_answer
from app.services.math.tools.block.discrete import (
    _verified_block_calculus,
    _verified_block_matrix,
    _verified_block_statistics,
)

_FUNCTION_OPS = {
    "function_domain",
    "function_range",
    "function_inverse",
    "function_even_odd",
    "function_compose_fg",
    "function_compose_gf",
}
_MATRIX_OPS = {
    "matrix_rank",
    "matrix_nullity",
    "matrix_nullspace",
    "matrix_columnspace",
    "matrix_rowspace",
    "matrix_independent_columns",
    "matrix_eigenvectors",
    "matrix_diagonalize",
}
_BIVARIATE_OPS = {
    "correlation",
    "sample_covariance",
    "population_covariance",
    "linear_regression",
}
_CALCULUS_APPLICATION_OPS = {
    "area_between_curves",
    "arc_length",
    "volume_revolution_x",
    "volume_revolution_y",
}


def _verified_block_calculus_extended(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    op = intent.school_op
    if op in _FUNCTION_OPS:
        if not intent.expr:
            return None
        answer = solve_function_feature(op, intent.expr, intent.expr2)
        labels = {
            "function_domain": "Domain",
            "function_range": "Range",
            "function_inverse": "Inverse",
            "function_even_odd": "Symmetry",
            "function_compose_fg": "Composition",
            "function_compose_gf": "Composition",
        }
        lines.append(f"{labels[op]}: {answer}")
        return _finish_with_answer(lines, answer)

    if op in _CALCULUS_APPLICATION_OPS:
        if not intent.expr or intent.integral_lower is None or intent.integral_upper is None:
            return None
        answer = solve_calculus_application(
            op,
            intent.expr,
            intent.integral_lower,
            intent.integral_upper,
            intent.expr2,
        )
        labels = {
            "area_between_curves": "Area",
            "arc_length": "Arc length",
            "volume_revolution_x": "Volume about x-axis",
            "volume_revolution_y": "Volume about y-axis",
        }
        lines.append(f"{labels[op]}: {answer}")
        return _finish_with_answer(lines, answer)

    return _verified_block_calculus(intent, settings, lines)


def _verified_block_matrix_extended(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    op = intent.school_op
    if op in _MATRIX_OPS:
        if not intent.matrix_rows:
            return None
        answer = solve_matrix_feature(op, intent.matrix_rows)
        label = op.removeprefix("matrix_").replace("_", " ").title()
        lines.append(f"{label}: {answer}")
        return _finish_with_answer(lines, answer)
    return _verified_block_matrix(intent, settings, lines)


def _verified_block_statistics_extended(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    op = intent.school_op
    if op in _BIVARIATE_OPS:
        if intent.vec_a is None or intent.vec_b is None:
            return None
        answer = solve_bivariate_statistics(op, intent.vec_a, intent.vec_b)
        label = op.replace("_", " ").title()
        lines.append(f"{label}: {answer}")
        return _finish_with_answer(lines, answer)
    return _verified_block_statistics(intent, settings, lines)
