"""Verified-block wrapper for integral applications."""

from __future__ import annotations

from app.core.config import Settings
from app.models.schemas.math import MathIntent
from app.services.math.calculus_applications import solve_calculus_application
from app.services.math.tools.block.common import VerifiedMathBlock, _finish_with_answer
from app.services.math.tools.block.discrete import _verified_block_calculus

_CALCULUS_APPLICATION_OPS = {
    "area_between_curves",
    "arc_length",
    "volume_revolution_x",
    "volume_revolution_y",
}


def _verified_block_calculus_with_applications(
    intent: MathIntent,
    settings: Settings,
    lines: list[str],
) -> VerifiedMathBlock | None:
    operation = intent.school_op
    if operation not in _CALCULUS_APPLICATION_OPS:
        return _verified_block_calculus(intent, settings, lines)
    if not intent.expr or intent.integral_lower is None or intent.integral_upper is None:
        return None

    answer = solve_calculus_application(
        operation,
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
    lines.append(f"{labels[operation]}: {answer}")
    return _finish_with_answer(lines, answer)
