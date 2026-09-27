"""Small physics-owned helpers shared by the physics regression suites."""

from app.models.schemas.physics.simulation import SIMULATION_SPEC_TYPES
from app.modules.physics import (
    build_verified_physics_block,
    extract_physics_intent,
    needs_physics,
)
from app.modules.physics.direct import maybe_direct_physics_reply
from app.modules.physics.fence import validate_physics_fences


def _spec_fence_kind(spec: dict[str, object]) -> str | None:
    kind = spec.get("type")
    if kind in SIMULATION_SPEC_TYPES:
        return "simulation"
    if kind in {"trajectory", "function", "vertical", "number_line", "inequality"}:
        return "graph"
    if kind == "answer":
        return "answer"
    return None


__all__ = [
    "_spec_fence_kind",
    "build_verified_physics_block",
    "extract_physics_intent",
    "maybe_direct_physics_reply",
    "needs_physics",
    "validate_physics_fences",
]
