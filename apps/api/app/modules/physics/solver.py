"""Stable public facade for the subject-grouped physics solvers."""

from __future__ import annotations

from collections.abc import Callable

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.solvers.common import (
    _PARAM_SI_DIMENSIONS,
    PhysicsResult,
    _params_in_si,
    _to_si,
)
from app.modules.physics.solvers.electricity_magnetism import solve_circuit, solve_magnetism
from app.modules.physics.solvers.gravity_modern import solve_gravitation, solve_modern
from app.modules.physics.solvers.matter_thermal import (
    solve_fluids,
    solve_materials,
    solve_optics,
    solve_thermal,
)
from app.modules.physics.solvers.mechanics import (
    solve_energy,
    solve_force,
    solve_friction,
    solve_momentum,
)
from app.modules.physics.solvers.motion import solve_kinematics, solve_projectile, solve_suvat
from app.modules.physics.solvers.oscillations_waves import solve_spring, solve_waves
from app.modules.physics.solvers.rotation import solve_circular, solve_rotation, solve_torque
from app.modules.physics.solvers.school_extensions import SCHOOL_SOLVERS
from app.services.solving import SolveServiceError

__all__ = [
    "PHYSICS_SOLVERS",
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


def _accepts_si_params(
    fn: Callable[[dict[str, float]], PhysicsResult],
) -> Callable[[PhysicsIntent], PhysicsResult]:
    def run(intent: PhysicsIntent) -> PhysicsResult:
        return fn(_params_in_si(intent))

    return run


def _claim_solvers() -> dict[str, Callable[[PhysicsIntent], PhysicsResult]]:
    """One operation, one solver. A second claim is a registration error."""
    from app.modules.physics.catalog import CATALOG

    by_kind: dict[str, Callable[[PhysicsIntent], PhysicsResult]] = {
        "kinematics": solve_kinematics,
        "suvat": solve_suvat,
        "projectile": solve_projectile,
        "force": solve_force,
        "energy": solve_energy,
        "momentum": solve_momentum,
        "friction": solve_friction,
        "circular": solve_circular,
        "spring": solve_spring,
        "circuit": solve_circuit,
        "torque": solve_torque,
        "waves": solve_waves,
        "optics": solve_optics,
        "thermal": solve_thermal,
        "gravitation": solve_gravitation,
        "fluids": solve_fluids,
        "rotation": solve_rotation,
        "magnetism": solve_magnetism,
        "materials": solve_materials,
        "modern": solve_modern,
    }
    claimed: dict[str, Callable[[PhysicsIntent], PhysicsResult]] = {}

    def claim(operation: str, fn: Callable[[PhysicsIntent], PhysicsResult]) -> None:
        if operation in claimed:
            raise RuntimeError(f"two physics solvers claim {operation}")
        claimed[operation] = fn

    for operation, fn in SCHOOL_SOLVERS.items():
        claim(operation, _accepts_si_params(fn))
    for spec in CATALOG.values():
        if spec.id in claimed:
            continue
        kind_solver = by_kind.get(spec.kind)
        if kind_solver is None:
            raise RuntimeError(f"no physics solver for kind {spec.kind}")
        claim(spec.id, kind_solver)
    missing = set(CATALOG) - set(claimed)
    if missing:
        raise RuntimeError(f"physics catalog ids without a solver: {sorted(missing)}")
    return claimed


PHYSICS_SOLVERS = _claim_solvers()


def solve_physics(intent: PhysicsIntent) -> PhysicsResult:
    """Dispatch on the operation. The catalog id is the only key."""
    from app.modules.physics.working import attach_recorded_working

    operation = intent.physics_op or ""
    solver = PHYSICS_SOLVERS.get(operation)
    if solver is None:
        raise SolveServiceError(f"unsupported physics op: {operation}")
    return attach_recorded_working(solver(intent), intent)
