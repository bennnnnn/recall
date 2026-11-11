"""Energy solvers: mechanical efficiency and the energy-conservation laws.

Eₖ = ½ mv², Eₚ = mgh, W = Fs and P = Fv or W/t are the catalog's arithmetic
(``catalog/mechanical_energy.py``), solved for any of their quantities; the height in
mgh and the distance in Fs are drawn with their law (``catalog_scenes``).
"""

from __future__ import annotations

from app.modules.physics.display import GIVEN_FIGURES, plain_number
from app.modules.physics.schemas import PhysicsIntent, SimulationBlockSpec, SimulationVector
from app.modules.physics.solvers.force_scenes import free_body_scene
from app.modules.physics.solvers.results import PhysicsResult, QuantityResult
from app.modules.physics.solvers.si import params_in_si
from app.services.solving import SolveServiceError


def solve_energy(intent: PhysicsIntent) -> PhysicsResult:
    from app.modules.physics.solvers.energy_conservation import solve_energy_conservation

    if intent.physics_op in {
        "work_energy",
        "mechanical_energy_gravity",
        "mechanical_energy_spring",
    }:
        return solve_energy_conservation(intent)
    op = intent.physics_op or ""
    if op != "mechanical_efficiency":
        raise SolveServiceError(f"unsupported energy op: {op}")
    p = params_in_si(intent)
    supplied = p["E_in"]
    output = p["E_out"]
    if supplied <= 0 or output < 0:
        raise SolveServiceError("efficiency needs positive input and nonnegative output")
    eta = output / supplied
    plugged = rf"\frac{{{output:g}}}{{{supplied:g}}}"
    return PhysicsResult(
        answer=rf"\eta = \frac{{E_{{out}}}}{{E_{{in}}}} = {plugged} \approx {eta:.4g}",
        formulas=(r"\eta = \frac{E_{out}}{E_{in}}",),
        substitutions=(rf"\eta = {plugged}",),
        quantities=(QuantityResult("", eta, "", detail=f"{eta * 100:.4g}%"),),
    )


def height_scene(mass: float, g: float, height: float) -> list[SimulationBlockSpec]:
    """A mass at a height above the ground, its weight and the height it is at.

    The weight is mg: the answers drawn here (work against gravity, lifting power) write
    work as W, and one letter never names two quantities in an answer."""
    shown_mass = f"{plain_number(mass, GIVEN_FIGURES)} kg"
    return free_body_scene(
        [
            SimulationVector(
                anchor=[0.0, height], dx=0.0, dy=-1.0, label=f"mg = {plain_number(mass * g)} N"
            ),
            SimulationVector(
                # Clear of the body however tall the climb: the frame and
                # the body grow with the height.
                anchor=[-max(0.9, 0.2 * height), 0.0],
                dx=0.0,
                dy=height,
                label=f"h = {plain_number(height, GIVEN_FIGURES)} m",
                role="measure",
            ),
        ],
        label=shown_mass,
        ground=True,
        position=(0.0, height),
        # A mass at a height for its potential energy: no free-body diagram, whose
        # title it had (2026-10-29, a crane lifting 450 kg 50 m).
        title="Height Above the Ground",
        title_key="height",
        alt=(
            f"A {shown_mass} mass {plain_number(height, GIVEN_FIGURES)} m above the ground, "
            f"weighing {plain_number(mass * g)} N."
        ),
    )
