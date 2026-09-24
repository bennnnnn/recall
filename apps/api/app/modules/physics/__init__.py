"""Physics — a subject domain in its own right, not a corner of math.

Physics asks (kinematics, projectile, force, energy) are detected, solved and
rendered by the four modules here:

- ``solver``  — SymPy solves for the unknown and builds trajectory graph specs
- ``extract`` — recognizes a physics ask and produces a ``MathIntent``
- ``direct``  — decides a complete literal ask may show its verified result
- ``block``   — builds the verified system-prompt block for the chat turn

Physics shares ``VerifiedMathBlock`` and ``MathServiceError`` with math, but
both live in the subject-neutral ``app.services.solving`` — neither subject
imports the other's package to reach them (see
docs/SUBJECT_SEPARATION_TICKETS.md). The still-open dependency is the intent
type: physics problems are represented as a ``MathIntent`` whose ``kind`` is
one of its twenty physics values (S1, not yet done), and physics plugs into
math's dispatch through four registry seams: ``PHYSICS_EXTRACTORS``,
``PHYSICS_BLOCK_BUILDERS``, ``can_direct_physics`` and
``has_supported_physics_cue``.

The package surface stays lazy. ``math.tools.block`` imports ``physics.block``
while it is still initializing, so eager imports here would close that cycle.
Other modules import only the names in ``_EXPORTS``.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "PHYSICS_BLOCK_BUILDERS": ("block", "PHYSICS_BLOCK_BUILDERS"),
    "PHYSICS_EXTRACTORS": ("extract", "PHYSICS_EXTRACTORS"),
    "PhysicsRequest": ("request", "PhysicsRequest"),
    "can_direct_physics": ("direct", "can_direct_physics"),
    "complete_physics_intent": ("request", "complete_physics_intent"),
    "format_direct_physics_working": ("direct", "format_direct_physics_working"),
    "has_supported_physics_cue": ("extract", "has_supported_physics_cue"),
    "prepare_physics_request": ("request", "prepare_physics_request"),
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
