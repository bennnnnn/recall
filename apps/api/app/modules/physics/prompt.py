"""Physics-owned prompt augmentation and verified-solve boundary."""

from __future__ import annotations

import logging
from dataclasses import replace

from app.core.config import Settings
from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.block import _build_physics_block
from app.modules.physics.extract import extract_physics_intent, needs_physics
from app.services.chat.prompt_constants.physics import PHYSICS_REPLY_POLICY
from app.services.solving import VerifiedPhysicsBlock, wrap_verified_physics

logger = logging.getLogger(__name__)


def _unverified_physics_note() -> str:
    return (
        "Physics note: a physics request was detected, but no complete verified "
        "solver result is available. Do not claim verification, drop units, or "
        "solve only one fragment of the request. Do not emit answer, graph, or "
        "simulation fences.\n\n"
        f"{PHYSICS_REPLY_POLICY}"
    )


async def _build_verified_physics_block_async(
    intent: PhysicsIntent, settings: Settings
) -> VerifiedPhysicsBlock | None:
    from app.services.sympy_executor import run_sympy

    try:
        block = await run_sympy(
            _build_physics_block,
            intent,
            settings,
            [],
            timeout=settings.math_solve_timeout_seconds,
        )
    except TimeoutError:
        logger.warning(
            "physics solve timed out after %ss for kind=%s",
            settings.math_solve_timeout_seconds,
            intent.kind,
        )
        return None
    except Exception:
        logger.warning("physics solve failed for kind=%s", intent.kind, exc_info=True)
        return None
    if block is None:
        return None
    return replace(block, text=wrap_verified_physics(block.text))


async def build_physics_augmentation(
    user_content: str,
    settings: Settings,
    *,
    needs_subject: bool | None = None,
) -> tuple[str | None, VerifiedPhysicsBlock | None, bool]:
    """Build physics context without passing through math extraction or blocks.

    The third value is true only when a matching template was solved and that
    solve failed. A physics question with no template still gets the prompt
    note, and it is not reported as a failed check.
    """
    if not settings.math_tools_enabled:
        return None, None, False
    detected = needs_physics(user_content) if needs_subject is None else needs_subject
    if not detected:
        return None, None, False
    intent = extract_physics_intent(user_content)
    if intent is None:
        return _unverified_physics_note(), None, False
    verified = await _build_verified_physics_block_async(intent, settings)
    if verified is None:
        return _unverified_physics_note(), None, True
    return f"{verified.text}\n\n{PHYSICS_REPLY_POLICY}", verified, False
