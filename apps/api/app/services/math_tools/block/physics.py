"""Physics verified blocks — answer fence + trajectory graph fence.

Builds the system-prompt hint for kinematics/projectile/force/energy
intents: a verified answer (so the model doesn't recompute) plus an
optional trajectory graph fence the model reuses verbatim.
"""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.models.math_schemas import MathIntent
from app.services.math_service import MathServiceError
from app.services.math_tools.block.common import (
    VerifiedMathBlock,
    _diagram_block,
    _fence,
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

    # If there are trajectory graph specs, attach them as fences.
    if result.graph_specs:
        for spec in result.graph_specs:
            lines.append(
                "When a plot helps, emit ONLY this fence ONCE — no 'corrected/final graph "
                "spec' heading, and do NOT paste or re-list the points array in prose "
                "(the app renders the fence as an SVG):\n"
                f"{_fence('graph', spec)}"
            )
        # Use _diagram_block so the canonical_fence carries the graph spec
        # (the post-stream rewriter can match it). The answer goes on
        # canonical_answer so ```answer can also be rewritten.
        return _diagram_block(lines, result.graph_specs[0], result.answer_value)

    # No graph — just the answer fence.
    return _finish_with_answer(lines, result.answer_value)


PHYSICS_BLOCK_BUILDERS = {
    "kinematics": _build_physics_block,
    "projectile": _build_physics_block,
    "force": _build_physics_block,
    "energy": _build_physics_block,
}
