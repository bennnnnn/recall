"""Physics verified blocks — numeric answer plus optional trajectory graph.

Builds the system-prompt hint for kinematics/projectile/force/energy/momentum
intents: a verified answer (so the model doesn't recompute) plus an
optional trajectory graph Recall attaches after the stream.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from app.core.config import Settings
from app.models.schemas.physics import PhysicsIntent
from app.services.physics.solver import PhysicsResult, solve_physics
from app.services.solving import (
    MathServiceError,
    VerifiedMathBlock,
    _diagram_block,
    _finish_with_answer,
)

logger = logging.getLogger(__name__)

# Display labels only. Supported operations and validation live on PhysicsIntent.
_PROJECTILE_LABELS = {
    "time_of_flight": r"t_{\mathrm{flight}}",
    "max_height": r"H_{\mathrm{max}}",
    "range": "R",
    "impact_speed": r"v_{\mathrm{impact}}",
}


def _solve_requested_quantities(intent: PhysicsIntent) -> PhysicsResult:
    """Solve every requested part before publishing any multipart result.

    Reuse the existing solvers and their verified working. All supported parts
    share one launch and therefore the same path; keep that visual once, not
    one graph and scene per scalar quantity. A failure aborts the whole block.
    """
    if not intent.requested_ops:
        return solve_physics(intent)
    # Validate even a model_copy-constructed intent before trusting its parts.
    intent = PhysicsIntent.model_validate(intent.model_dump())
    results: list[PhysicsResult] = []
    answers: list[str] = []
    for op in intent.requested_ops:
        part = PhysicsIntent.model_validate(
            {**intent.model_dump(), "physics_op": op, "requested_ops": []}
        )
        result = solve_physics(part)
        value, separator, unit = result.answer_value.partition(" ")
        if not separator or unit not in {"s", "m", "m/s"}:
            raise MathServiceError("unexpected projectile result representation")
        answers.append(rf"{_PROJECTILE_LABELS[op]} = {value}\,\mathrm{{{unit}}}")
        results.append(result)
    first = results[0]
    return PhysicsResult(
        answer=r";\quad ".join(result.answer for result in results),
        answer_value=r";\quad ".join(answers),
        graph_specs=first.graph_specs,
        simulation_specs=first.simulation_specs,
    )


def _build_physics_block(
    intent: PhysicsIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    """Solve the physics problem and build a verified block with answer + graph."""
    result: PhysicsResult | None = None
    try:
        result = _solve_requested_quantities(intent)
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

    if intent.requested_ops:
        lines.append("Every requested projectile quantity below was solved for the same givens.")
        lines.append(
            "Working uses uniform gravity, no air resistance, and heights measured from "
            "the landing plane. Copy each verified formula; do not recalculate its numbers."
        )
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


# Any, not PhysicsIntent: the generic dispatch in math/tools/block/__init__.py
# calls whichever builder it looks up with a MathIntent | PhysicsIntent — see
# _BlockBuilder there for why the registry's own Callable type has to be
# this loose even though _build_physics_block's own signature is precise.
_PhysicsBlockBuilder = Callable[[Any, Settings, list[str]], VerifiedMathBlock | None]

PHYSICS_BLOCK_BUILDERS: dict[str, _PhysicsBlockBuilder] = {
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
