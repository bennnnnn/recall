"""Energy solvers: KE = ½ mv², PE = mgh, W = Fd, P = Fv or W/t."""

from __future__ import annotations

import math

from app.models.schemas.physics import PhysicsIntent, SimulationBlockSpec, SimulationVector
from app.modules.physics.display import GIVEN_FIGURES, plain_number
from app.modules.physics.solvers.common import (
    PhysicsResult,
    QuantityResult,
    _latex_num,
    _params_in_si,
    gravity_of,
)
from app.modules.physics.solvers.force_scenes import _free_body_scene
from app.services.solving import SolveServiceError


def solve_energy(intent: PhysicsIntent) -> PhysicsResult:
    from app.modules.physics.solvers.energy_conservation import solve_energy_conservation

    if intent.physics_op in {
        "work_energy",
        "mechanical_energy_gravity",
        "mechanical_energy_spring",
    }:
        return solve_energy_conservation(intent)

    p = _params_in_si(intent)
    g = gravity_of(p)
    op = intent.physics_op or "kinetic_energy"
    work_direction = (1.0, 0.0)

    if op == "mechanical_efficiency":
        supplied = p["E_in"]
        output = p["E_out"]
        if supplied <= 0 or output < 0:
            raise SolveServiceError("efficiency needs positive input and nonnegative output")
        eta = output / supplied
        plugged = rf"\frac{{{output:g}}}{{{supplied:g}}}"
        answer_latex = rf"\eta = \frac{{E_{{out}}}}{{E_{{in}}}} = {plugged} \approx {eta:.4g}"
        formula = r"\eta = \frac{E_{out}}{E_{in}}"
        substitution = rf"\eta = {plugged}"
        quantity = QuantityResult("", eta, "", detail=f"{eta * 100:.4g}%")
    elif op == "kinetic_energy":
        ke_val = 0.5 * p["m"] * p["v"] ** 2
        v_sq = _latex_num(p["v"], square=True)
        plugged = rf"\frac{{1}}{{2}} \cdot {p['m']:g} \cdot {v_sq}"
        answer_latex = rf"KE = \frac{{1}}{{2}} m v^2 = {plugged} \approx {ke_val:.2f} \text{{ J}}"
        formula = r"KE = \frac{1}{2} m v^2"
        substitution = rf"KE = {plugged}"
        quantity = QuantityResult("", ke_val, "J")
    elif op == "potential_energy":
        pe_val = p["m"] * g * p["h"]
        plugged = rf"{p['m']:g} \cdot {g:g} \cdot {p['h']:g}"
        answer_latex = rf"PE = m g h = {plugged} \approx {pe_val:.2f} \text{{ J}}"
        formula = r"PE = m g h"
        substitution = rf"PE = {plugged}"
        quantity = QuantityResult("", pe_val, "J")
    elif op == "work":
        theta = p.get("angle")
        if theta is None:
            w_val = p["F"] * p["d"]
            plugged = rf"{p['F']:g} \cdot {p['d']:g}"
            answer_latex = rf"W = F \cdot d = {plugged} \approx {w_val:.2f} \text{{ J}}"
            formula = r"W = F \cdot d"
        else:
            w_val = p["F"] * p["d"] * math.cos(theta)
            deg = math.degrees(theta)
            plugged = rf"{p['F']:g} \cdot {p['d']:g} \cdot \cos({deg:g}^\circ)"
            answer_latex = rf"W = Fd\cos\theta = {plugged} \approx {w_val:.2f} \text{{ J}}"
            formula = r"W = Fd\cos\theta"
            work_direction = (math.cos(theta), math.sin(theta))
        substitution = rf"W = {plugged}"
        quantity = QuantityResult("", w_val, "J")
    elif op == "power":
        if "W" in p and "t" in p and "angle" not in p:
            # P = W / t — the other school form, when no force/velocity pair
            # was given ("100 J of work in 5 s").
            if p["t"] == 0:
                raise SolveServiceError("power needs a nonzero time")
            power_val = p["W"] / p["t"]
            plugged = rf"\frac{{{p['W']:g}}}{{{p['t']:g}}}"
            answer_latex = rf"P = \frac{{W}}{{t}} = {plugged} \approx {power_val:.2f} \text{{ W}}"
            formula = r"P = \frac{W}{t}"
        else:
            theta = p.get("angle")
            if theta is None:
                power_val = p["F"] * p["v"]
                plugged = rf"{p['F']:g} \cdot {p['v']:g}"
                answer_latex = rf"P = F \cdot v = {plugged} \approx {power_val:.2f} \text{{ W}}"
                formula = r"P = F \cdot v"
            else:
                power_val = p["F"] * p["v"] * math.cos(theta)
                deg = math.degrees(theta)
                plugged = rf"{p['F']:g} \cdot {p['v']:g} \cdot \cos({deg:g}^\circ)"
                answer_latex = rf"P = Fv\cos\theta = {plugged} \approx {power_val:.2f} \text{{ W}}"
                formula = r"P = Fv\cos\theta"
        substitution = rf"P = {plugged}"
        quantity = QuantityResult("", power_val, "W")
    else:
        raise SolveServiceError(f"unsupported energy op: {op}")

    # Only where there is something spatial to show. A block with a "3 m/s"
    # arrow beside it tells you nothing the sentence did not — the height in
    # mgh and the distance in Fd are quantities you can point at, and a speed
    # is not, so kinetic energy and power get no picture rather than a
    # decorative one.
    scene: list[SimulationBlockSpec] = []
    if op == "potential_energy":
        height = p["h"]
        scene = _free_body_scene(
            [
                SimulationVector(
                    anchor=[0.0, height], dx=0.0, dy=-1.0, label=f"W = {plain_number(p['m'] * g)} N"
                ),
                SimulationVector(
                    anchor=[-0.9, 0.0],
                    dx=0.0,
                    dy=height,
                    label=f"h = {plain_number(height, GIVEN_FIGURES)} m",
                    role="measure",
                ),
            ],
            label=f"{plain_number(p['m'], GIVEN_FIGURES)} kg",
            ground=True,
            position=(0.0, height),
        )
    elif op == "work":
        distance = p["d"]
        scene = _free_body_scene(
            [
                SimulationVector(
                    anchor=[0.0, 0.0],
                    dx=work_direction[0],
                    dy=work_direction[1],
                    label=f"F = {plain_number(p['F'], GIVEN_FIGURES)} N",
                    role="result",
                ),
                SimulationVector(
                    anchor=[0.0, -0.8],
                    dx=distance,
                    dy=0.0,
                    label=f"d = {plain_number(distance, GIVEN_FIGURES)} m",
                    role="measure",
                ),
            ],
            ground=True,
        )
    return PhysicsResult(
        answer=answer_latex,
        formulas=(formula,),
        substitutions=(substitution,),
        quantities=(quantity,),
        simulation_specs=scene,
    )
