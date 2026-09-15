"""Verified-block wrapper for small linear-algebra extensions."""

from __future__ import annotations

from app.core.config import Settings
from app.models.schemas.math import MathIntent
from app.services.math.coverage_extensions import matrix_columns_independent, matrix_nullity
from app.services.math.tools.block.common import VerifiedMathBlock, _finish_with_answer
from app.services.math.tools.block.discrete import _verified_block_matrix


def _verified_block_matrix_with_extensions(
    intent: MathIntent,
    settings: Settings,
    lines: list[str],
) -> VerifiedMathBlock | None:
    if intent.school_op == "matrix_nullity":
        if not intent.matrix_rows:
            return None
        answer = matrix_nullity(intent.matrix_rows)
        lines.append(f"Nullity: {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "matrix_independent_columns":
        if not intent.matrix_rows:
            return None
        answer = matrix_columns_independent(intent.matrix_rows)
        lines.append(f"Columns linearly independent: {answer}")
        return _finish_with_answer(lines, answer)
    return _verified_block_matrix(intent, settings, lines)
