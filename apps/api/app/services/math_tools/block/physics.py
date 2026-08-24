"""Physics verified blocks — numeric answer plus optional trajectory graph.

Builds the system-prompt hint for kinematics/projectile/force/energy
intents: a verified answer (so the model doesn't recompute) plus an
optional trajectory graph Recall attaches after the stream.
"""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.models.math_schemas import MathIntent
from app.services.math_service import MathServiceError
from app.services.math_tools.block.common import (
    VerifiedMathBlock,
    _diagram_block,
    _finish_with_answer,
)
from app.services.physics_solver import PhysicsResult, solve_physics

logger = logging.getLogger(__name__)


def _build_physics_block(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    """Solve the physics problem and build a verified block with answer + graph."""
    result: PhysicsResult | None = None
    try:
        result = solve_physics(intent)
    except MathServiceError as exc:
        logger.info(
            "physics verification skipped kind=%s op=%s reason=%s",
            intent.kind,
            intent.physics_op,
            exc,
        )
        return None
    except Exception:
        logger.warning(
            "physics verification failed kind=%s op=%s",
            intent.kind,
            intent.physics_op,
            exc_info=True,
        )
        return None

    # Append the verified answer to the hint lines.
    lines.append(f"Verified answer: ${result.answer}$ ({result.answer_value})")

    if result.graph_specs:
        return _diagram_block(lines, result.graph_specs[0], result.answer_value)
    return _finish_with_answer(lines, result.answer_value)


PHYSICS_BLOCK_BUILDERS = {
    "kinematics": _build_physics_block,
    "projectile": _build_physics_block,
    "force": _build_physics_block,
    "energy": _build_physics_block,
}
