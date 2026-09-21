"""Stable public facade for the subject-grouped physics solvers."""

from __future__ import annotations

from app.models.schemas.physics import PhysicsIntent
from app.services.physics.solvers.common import (
    _PARAM_SI_DIMENSIONS,
    PhysicsResult,
    _params_in_si,
    _to_si,
)
from app.services.physics.solvers.electricity_magnetism import solve_circuit, solve_magnetism
from app.services.physics.solvers.gravity_modern import solve_gravitation, solve_modern
from app.services.physics.solvers.matter_thermal import (
    solve_fluids,
    solve_materials,
    solve_optics,
    solve_thermal,
)
from app.services.physics.solvers.mechanics import (
    solve_energy,
    solve_force,
    solve_friction,
    solve_momentum,
)
from app.services.physics.solvers.motion import solve_kinematics, solve_projectile, solve_suvat
from app.services.physics.solvers.oscillations_waves import solve_spring, solve_waves
from app.services.physics.solvers.rotation import solve_circular, solve_rotation, solve_torque
from app.services.solving import MathServiceError

__all__ = [
    "_PARAM_SI_DIMENSIONS",
    "PhysicsResult",
    "_params_in_si",
    "_to_si",
    "solve_circuit",
    "solve_circular",
    "solve_energy",
    "solve_fluids",
    "solve_force",
    "solve_friction",
    "solve_gravitation",
    "solve_kinematics",
    "solve_magnetism",
    "solve_materials",
    "solve_modern",
    "solve_momentum",
    "solve_optics",
    "solve_physics",
    "solve_projectile",
    "solve_rotation",
    "solve_spring",
    "solve_suvat",
    "solve_thermal",
    "solve_torque",
    "solve_waves",
]


def solve_physics(intent: PhysicsIntent) -> PhysicsResult:
    """Dispatch to the right solver by intent kind."""
    if intent.kind == "kinematics":
        return solve_kinematics(intent)
    if intent.kind == "suvat":
        return solve_suvat(intent)
    if intent.kind == "projectile":
        return solve_projectile(intent)
    if intent.kind == "force":
        return solve_force(intent)
    if intent.kind == "energy":
        return solve_energy(intent)
    if intent.kind == "momentum":
        return solve_momentum(intent)
    if intent.kind == "friction":
        return solve_friction(intent)
    if intent.kind == "circular":
        return solve_circular(intent)
    if intent.kind == "spring":
        return solve_spring(intent)
    if intent.kind == "circuit":
        return solve_circuit(intent)
    if intent.kind == "torque":
        return solve_torque(intent)
    if intent.kind == "waves":
        return solve_waves(intent)
    if intent.kind == "optics":
        return solve_optics(intent)
    if intent.kind == "thermal":
        return solve_thermal(intent)
    if intent.kind == "gravitation":
        return solve_gravitation(intent)
    if intent.kind == "fluids":
        return solve_fluids(intent)
    if intent.kind == "rotation":
        return solve_rotation(intent)
    if intent.kind == "magnetism":
        return solve_magnetism(intent)
    if intent.kind == "materials":
        return solve_materials(intent)
    if intent.kind == "modern":
        return solve_modern(intent)
    raise MathServiceError(f"not a physics kind: {intent.kind}")
