"""Stable public facade and ordered registry for physics extraction."""

from __future__ import annotations

import re
from collections.abc import Callable

from app.models.schemas.physics import PhysicsIntent
from app.services.physics.extractors.common import (
    _LENGTH_UNIT_PATTERN,
    _NUMBER,
    _VALUE_UNIT_RE,
    _VELOCITY_UNIT_PATTERN,
    _detect_gravity,
    _has_cue_either_case,
)
from app.services.physics.extractors.electricity_magnetism import (
    _CIRCUIT_CUE_RES,
    _CIRCUIT_CUES,
    _ELECTROSTATICS_CUE_RES,
    _ELECTROSTATICS_CUES,
    _MAGNETISM_CUE_RES,
    _MAGNETISM_CUES,
    _extract_circuit_intent,
    _extract_electrostatics_intent,
    _extract_magnetism_intent,
)
from app.services.physics.extractors.gravity_modern import (
    _GRAVITATION_CUE_RES,
    _GRAVITATION_CUES,
    _MODERN_CUE_RES,
    _MODERN_CUES,
    _extract_gravitation_intent,
    _extract_modern_intent,
)
from app.services.physics.extractors.matter_thermal import (
    _FLUIDS_CUE_RES,
    _FLUIDS_CUES,
    _MATERIALS_CUE_RES,
    _MATERIALS_CUES,
    _OPTICS_CUES,
    _THERMAL_CUE_RES,
    _THERMAL_CUES,
    _extract_fluids_intent,
    _extract_materials_intent,
    _extract_optics_intent,
    _extract_thermal_intent,
)
from app.services.physics.extractors.mechanics import (
    _COLLISION_SUBJECT_RE,
    _ENERGY_CUE_RES,
    _ENERGY_CUES,
    _FORCE_CUE_RES,
    _FORCE_CUES,
    _FRICTION_CUE_RES,
    _FRICTION_CUES,
    _MASS_UNITS,
    _MOMENTUM_CUES,
    _TENSION_CUE_RES,
    _TWO_DIMENSIONAL_RE,
    _VECTOR_FORCE_CUE_RES,
    _extract_energy_intent,
    _extract_force_intent,
    _extract_friction_intent,
    _extract_momentum_intent,
    _extract_tension_intent,
    _extract_vector_force_intent,
)
from app.services.physics.extractors.motion import (
    _KINEMATICS_CUE_RES,
    _KINEMATICS_CUES,
    _PROJECTILE_CUE_RES,
    _PROJECTILE_CUES,
    _SUVAT_CUE_RES,
    _SUVAT_CUES,
    _extract_kinematics_intent,
    _extract_projectile_intent,
    _extract_suvat_intent,
)
from app.services.physics.extractors.oscillations_waves import (
    _PENDULUM_CUE_RES,
    _SHM_CUE_RES,
    _SPRING_CUE_RES,
    _SPRING_CUES,
    _WAVE_CUE_RES,
    _WAVE_CUES,
    _extract_pendulum_intent,
    _extract_shm_intent,
    _extract_spring_intent,
    _extract_waves_intent,
)
from app.services.physics.extractors.rotation import (
    _CIRCULAR_CUE_RES,
    _CIRCULAR_CUES,
    _ROTATION_CUE_RES,
    _ROTATION_CUES,
    _TORQUE_CUE_RES,
    _TORQUE_CUES,
    _extract_circular_intent,
    _extract_rotation_intent,
    _extract_torque_intent,
)

__all__ = [
    "PHYSICS_CUES",
    "PHYSICS_CUE_RES",
    "PHYSICS_EXTRACTORS",
    "_COLLISION_SUBJECT_RE",
    "_LENGTH_UNIT_PATTERN",
    "_MASS_UNITS",
    "_NUMBER",
    "_TWO_DIMENSIONAL_RE",
    "_VALUE_UNIT_RE",
    "_VELOCITY_UNIT_PATTERN",
    "_detect_gravity",
    "_extract_energy_intent",
    "_extract_force_intent",
    "_extract_kinematics_intent",
    "_extract_projectile_intent",
    "_extract_torque_intent",
    "has_supported_physics_cue",
]

PHYSICS_EXTRACTORS: tuple[Callable[[str], PhysicsIntent | None], ...] = (
    _extract_kinematics_intent,
    # After kinematics, not before: free fall is a constant acceleration too,
    # and kinematics already owns it. SUVAT sees only what gravity did not
    # claim, so adding it perturbs nothing that already answered.
    _extract_suvat_intent,
    _extract_projectile_intent,
    _extract_momentum_intent,
    _extract_friction_intent,
    _extract_circular_intent,
    # Before the pendulum and the spring: both of those read a *period* as the
    # answer, and the two SHM ops read it as a given.
    _extract_shm_intent,
    # Before springs: a pendulum has a length where a spring has a constant,
    # so the two cannot collide, and reading in this order keeps the spring
    # extractor's k requirement untouched.
    _extract_pendulum_intent,
    _extract_spring_intent,
    _extract_electrostatics_intent,
    _extract_circuit_intent,
    _extract_torque_intent,
    # Ahead of force so the two rope shapes below are claimed before the
    # blanket refusal in _UNSUPPORTED_FORCE_CONTEXT sees them. Everything else
    # rope-shaped still reaches that refusal.
    _extract_tension_intent,
    _extract_vector_force_intent,
    # Round 3, all three ahead of force and energy. Each says a word those two
    # own - optics says "power" (of a lens, in dioptres), thermal says "energy"
    # and modern will too - and running first makes the split deterministic
    # rather than lucky.
    _extract_waves_intent,
    _extract_optics_intent,
    _extract_thermal_intent,
    _extract_gravitation_intent,
    _extract_magnetism_intent,
    # Before fluids, and the ordering is load-bearing: sigma = F/A and P = F/A
    # are the same arithmetic, so nothing about the numbers can separate them.
    # Stress is the narrower vocabulary, so it chooses first and fluids refuses
    # those words outright.
    _extract_materials_intent,
    _extract_fluids_intent,
    _extract_modern_intent,
    # After torque, deliberately. P9 refuses "moment of inertia" there because
    # it was not solved; that refusal is what stops *torque* claiming it, and
    # is kept. This picks up the fall-through.
    _extract_rotation_intent,
    _extract_force_intent,
    _extract_energy_intent,
)

PHYSICS_CUES: tuple[str, ...] = tuple(
    dict.fromkeys(
        (
            *_KINEMATICS_CUES,
            *_SUVAT_CUES,
            *_PROJECTILE_CUES,
            *_MOMENTUM_CUES,
            *_WAVE_CUES,
            *_OPTICS_CUES,
            *_THERMAL_CUES,
            *_GRAVITATION_CUES,
            *_FLUIDS_CUES,
            *_ROTATION_CUES,
            *_MAGNETISM_CUES,
            *_MATERIALS_CUES,
            *_MODERN_CUES,
            *_FRICTION_CUES,
            *_CIRCULAR_CUES,
            *_SPRING_CUES,
            *_ELECTROSTATICS_CUES,
            *_CIRCUIT_CUES,
            *_TORQUE_CUES,
            *_FORCE_CUES,
            *_ENERGY_CUES,
        )
    )
)

PHYSICS_CUE_RES: tuple[re.Pattern[str], ...] = (
    *_KINEMATICS_CUE_RES,
    *_SUVAT_CUE_RES,
    *_PROJECTILE_CUE_RES,
    *_FRICTION_CUE_RES,
    *_CIRCULAR_CUE_RES,
    *_WAVE_CUE_RES,
    *_THERMAL_CUE_RES,
    *_GRAVITATION_CUE_RES,
    *_FLUIDS_CUE_RES,
    *_ROTATION_CUE_RES,
    *_MAGNETISM_CUE_RES,
    *_MATERIALS_CUE_RES,
    *_MODERN_CUE_RES,
    *_SHM_CUE_RES,
    *_PENDULUM_CUE_RES,
    *_SPRING_CUE_RES,
    *_ELECTROSTATICS_CUE_RES,
    *_CIRCUIT_CUE_RES,
    *_TORQUE_CUE_RES,
    *_TENSION_CUE_RES,
    *_VECTOR_FORCE_CUE_RES,
    *_FORCE_CUE_RES,
    *_ENERGY_CUE_RES,
)


def has_supported_physics_cue(cleaned: str) -> bool:
    """True when a verified physics template could match this text.

    Takes the text **as written**, not lowercased. See `_has_cue_either_case`.
    """
    return _has_cue_either_case(cleaned, PHYSICS_CUES, PHYSICS_CUE_RES)
