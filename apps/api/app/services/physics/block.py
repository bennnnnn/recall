"""Physics verified blocks — numeric answer plus optional trajectory graph.

Builds the system-prompt hint for kinematics/projectile/force/energy/momentum
intents: a verified answer (so the model doesn't recompute) plus an
optional trajectory graph Recall attaches after the stream.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from app.core.config import Settings
from app.models.schemas.math import MathIntent
from app.services.math.solve import MathServiceError
from app.services.math.tools.block.common import (
    VerifiedMathBlock,
    _diagram_block,
    _finish_with_answer,
)
from app.services.physics.solver import PhysicsResult, solve_physics

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

    # A solve may produce both a plot and a scene — a projectile's parabola and
    # the ball flying along it. `canonical_fences` is what carries more than one
    # fence through `validate_math_fences`, so every spec goes there and the
    # primary stays first for the callers that read `canonical_fence` alone.
    specs = [spec.model_dump() for spec in (*result.graph_specs, *result.simulation_specs)]
    if not specs:
        return _finish_with_answer(lines, result.answer_value, allow_direct=False)

    if result.graph_specs:
        # A graph *is* the answer in visual form, so it leads and the turn may
        # take the direct path exactly as it always could.
        block = _diagram_block(lines, specs[0], result.answer_value)
    else:
        # A scene attached to a scalar answer is decoration, not a second
        # answer. Force and energy are unlabeled quantities deliberately kept
        # on the model path so the prompt can name the symbol; giving them a
        # picture must not silently grant the direct reply they were denied.
        block = _finish_with_answer(lines, result.answer_value, allow_direct=False)

    # Extras only. Every reader of `canonical_fences` already prepends
    # `canonical_fence`, so repeating it here would mean a caller that clears
    # the primary still finds a copy — and for a scalar answer the primary
    # *is* the authorisation for a direct reply.
    extras = [spec for spec in specs if spec is not block.canonical_fence]
    return replace(block, canonical_fences=extras)


PHYSICS_BLOCK_BUILDERS = {
    "kinematics": _build_physics_block,
    "suvat": _build_physics_block,
    "projectile": _build_physics_block,
    "force": _build_physics_block,
    "energy": _build_physics_block,
    "momentum": _build_physics_block,
    "friction": _build_physics_block,
    "circular": _build_physics_block,
    "spring": _build_physics_block,
    "circuit": _build_physics_block,
    "waves": _build_physics_block,
    "optics": _build_physics_block,
    "thermal": _build_physics_block,
    "gravitation": _build_physics_block,
    "fluids": _build_physics_block,
    "rotation": _build_physics_block,
    "magnetism": _build_physics_block,
    "materials": _build_physics_block,
    "modern": _build_physics_block,
    "torque": _build_physics_block,
}
