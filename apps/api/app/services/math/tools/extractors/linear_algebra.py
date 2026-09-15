"""Advanced linear-algebra intent extraction on the existing matrix kind."""

from __future__ import annotations

from typing import Literal

from app.models.schemas.math import MathIntent
from app.services.math.match.discrete import bracket_matrices

AdvancedMatrixOp = Literal[
    "rank",
    "nullspace",
    "columnspace",
    "rowspace",
    "eigenvectors",
    "diagonalize",
]


def _advanced_matrix_op(text: str) -> AdvancedMatrixOp | None:
    lower = text.lower()
    # Specific space names before generic "space" language.
    if "nullspace" in lower or "null space" in lower or "kernel of" in lower:
        return "nullspace"
    if "column space" in lower or "columnspace" in lower or "col space" in lower:
        return "columnspace"
    if "row space" in lower or "rowspace" in lower:
        return "rowspace"
    if "eigenvector" in lower:
        return "eigenvectors"
    if "diagonalize" in lower or "diagonalise" in lower or "diagonalization" in lower:
        return "diagonalize"
    if "rank" in lower:
        return "rank"
    return None


def _extract_advanced_matrix_intent(cleaned: str) -> MathIntent | None:
    operation = _advanced_matrix_op(cleaned)
    if operation is None:
        return None
    matrices = bracket_matrices(cleaned, limit=1)
    if not matrices or len(matrices) != 1:
        return None
    rows = matrices[0]
    if operation in {"eigenvectors", "diagonalize"} and any(
        len(row) != len(rows) for row in rows
    ):
        return None
    return MathIntent(
        kind="matrix",
        school_op=f"matrix_{operation}",
        matrix_rows=rows,
        operation="solve",
    )


ADVANCED_MATRIX_EXTRACTORS = (_extract_advanced_matrix_intent,)
