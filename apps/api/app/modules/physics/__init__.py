"""Physics — a subject domain in its own right, not a corner of math.

Physics asks (kinematics, projectile, force, energy) are detected, solved and
rendered by the four modules here:

- ``solver``  — SymPy solves for the unknown and builds trajectory graph specs
- ``extract`` — recognizes a physics ask and produces a ``PhysicsIntent``
- ``direct``  — decides a complete literal ask may show its verified result
- ``block``   — builds the verified system-prompt block for the chat turn

Physics has its own intent, extraction, verified block, prompt augmentation,
direct presentation, and fence finalization. Only canonical solve transport
and text normalization are shared with other subjects.

The package surface stays lazy. ``math.tools.block`` imports ``physics.block``
while it is still initializing, so eager imports here would close that cycle.
Other modules import only the names in ``_EXPORTS``.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "PHYSICS_BLOCK_BUILDERS": ("block", "PHYSICS_BLOCK_BUILDERS"),
    "PHYSICS_EXTRACTORS": ("registry", "PHYSICS_EXTRACTORS"),
    "PhysicsRequest": ("request", "PhysicsRequest"),
    "build_verified_physics_block": ("block", "build_verified_physics_block"),
    "can_direct_physics": ("direct", "can_direct_physics"),
    "complete_physics_intent": ("request", "complete_physics_intent"),
    "format_direct_physics_working": ("direct", "format_direct_physics_working"),
    "extract_physics_intent": ("extract", "extract_physics_intent"),
    "has_supported_physics_cue": ("registry", "has_supported_physics_cue"),
    "needs_physics": ("extract", "needs_physics"),
    "prepare_physics_request": ("request", "prepare_physics_request"),
    "solve_physics": ("solver", "solve_physics"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(f"app.modules.physics.{module_name}"), attribute)
    globals()[name] = value
    return value
