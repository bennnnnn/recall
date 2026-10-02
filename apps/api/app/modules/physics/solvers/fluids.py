"""Fluid solvers: pressure, upthrust, density, continuity, flow rate, Bernoulli, hydraulics,
Torricelli, Stokes drag, the Reynolds number, surface tension and Laplace pressure.
"""

from __future__ import annotations

import math

from app.models.schemas.physics import PhysicsIntent, SimulationVector
from app.modules.physics.display import plain_number
from app.modules.physics.solvers.common import PhysicsResult, QuantityResult, _params_in_si
from app.modules.physics.solvers.force_scenes import _free_body_scene
from app.services.solving import SolveServiceError


def solve_fluids(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "mass_flow_rate":
        if p["rho"] <= 0 or p["area"] <= 0:
            raise SolveServiceError("mass flow rate needs positive density and area")
        value = p["rho"] * p["area"] * p["v"]
        return PhysicsResult(
            answer=(
                rf"\dot{{m}} = \rho Av = {p['rho']:g} \cdot {p['area']:g} \cdot "
                rf"{p['v']:g} \approx {value:.4g} \text{{ kg/s}}"
            ),
            formulas=(r"\dot{m} = \rho Av",),
            substitutions=(rf"\dot{{m}} = {p['rho']:g} \cdot {p['area']:g} \cdot {p['v']:g}",),
            quantities=(QuantityResult("", value, "kg/s"),),
        )

    if op == "torricelli_speed":
        if p["depth"] < 0 or p["g"] <= 0:
            raise SolveServiceError("Torricelli speed needs nonnegative head and positive gravity")
        value = math.sqrt(2 * p["g"] * p["depth"])
        return PhysicsResult(
            answer=(
                rf"v = \sqrt{{2gh}} = \sqrt{{2 \cdot {p['g']:g} \cdot {p['depth']:g}}} "
                rf"\approx {value:.4g} \text{{ m/s}}"
            ),
            formulas=(r"v = \sqrt{2gh}",),
            substitutions=(rf"v = \sqrt{{2 \cdot {p['g']:g} \cdot {p['depth']:g}}}",),
            quantities=(QuantityResult("", value, "m/s"),),
        )

    if op == "stokes_drag":
        if p["viscosity"] < 0 or p["r"] <= 0 or p["v"] < 0:
            raise SolveServiceError("Stokes drag needs valid viscosity, radius, and speed")
        value = 6 * math.pi * p["viscosity"] * p["r"] * p["v"]
        return PhysicsResult(
            answer=(
                rf"F_d = 6\pi\eta rv = 6\pi \cdot {p['viscosity']:g} \cdot "
                rf"{p['r']:g} \cdot {p['v']:g} \approx {value:.4g} \text{{ N}}"
            ),
            formulas=(r"F_d = 6\pi\eta rv",),
            substitutions=(
                rf"F_d = 6\pi \cdot {p['viscosity']:g} \cdot {p['r']:g} \cdot {p['v']:g}",
            ),
            quantities=(QuantityResult("", value, "N"),),
        )

    if op == "reynolds_number":
        if p["viscosity"] <= 0 or p["rho"] <= 0 or p["L"] <= 0:
            raise SolveServiceError("Reynolds number needs positive density, length, and viscosity")
        value = p["rho"] * p["v"] * p["L"] / p["viscosity"]
        return PhysicsResult(
            answer=(
                rf"Re = \frac{{\rho vL}}{{\eta}} = "
                rf"\frac{{{p['rho']:g} \cdot {p['v']:g} \cdot {p['L']:g}}}"
                rf"{{{p['viscosity']:g}}} \approx {value:.4g}"
            ),
            formulas=(r"Re = \frac{\rho vL}{\eta}",),
            substitutions=(
                rf"Re = \frac{{{p['rho']:g} \cdot {p['v']:g} \cdot {p['L']:g}}}"
                rf"{{{p['viscosity']:g}}}",
            ),
            quantities=(QuantityResult("", value, ""),),
        )

    if op == "surface_tension":
        if p["L"] <= 0:
            raise SolveServiceError("contact length must be positive")
        value = p["F"] / p["L"]
        return PhysicsResult(
            answer=(
                rf"\gamma = \frac{{F}}{{L}} = \frac{{{p['F']:g}}}{{{p['L']:g}}} "
                rf"\approx {value:.4g} \text{{ N/m}}"
            ),
            formulas=(r"\gamma = \frac{F}{L}",),
            substitutions=(rf"\gamma = \frac{{{p['F']:g}}}{{{p['L']:g}}}",),
            quantities=(QuantityResult("", value, "N/m"),),
        )

    if op == "laplace_pressure":
        if p["surface_tension"] < 0 or p["r"] <= 0:
            raise SolveServiceError("Laplace pressure needs valid surface tension and radius")
        value = p["mode_factor"] * p["surface_tension"] / p["r"]
        symbolic = (
            r"\Delta P = \frac{4\gamma}{r}"
            if p["mode_factor"] == 4
            else r"\Delta P = \frac{2\gamma}{r}"
        )
        plugged = rf"\frac{{{p['mode_factor']:g} \cdot {p['surface_tension']:g}}}{{{p['r']:g}}}"
        return PhysicsResult(
            answer=rf"{symbolic} = {plugged} \approx {value:.4g} \text{{ Pa}}",
            formulas=(symbolic,),
            substitutions=(rf"\Delta P = {plugged}",),
            quantities=(QuantityResult("", value, "Pa"),),
        )

    if op == "hydraulic_force":
        if p["A1"] <= 0 or p["A2"] <= 0:
            raise SolveServiceError("hydraulic force needs positive piston areas")
        force = p["F1"] * p["A2"] / p["A1"]
        return PhysicsResult(
            answer=(
                rf"\frac{{F_1}}{{A_1}} = \frac{{F_2}}{{A_2}} \Rightarrow "
                rf"F_2 = \frac{{F_1A_2}}{{A_1}} = "
                rf"\frac{{{p['F1']:g} \cdot {p['A2']:g}}}{{{p['A1']:g}}} "
                rf"\approx {force:g} \text{{ N}}"
            ),
            formulas=(r"F_2 = \frac{F_1A_2}{A_1}",),
            substitutions=(rf"F_2 = \frac{{{p['F1']:g} \cdot {p['A2']:g}}}{{{p['A1']:g}}}",),
            quantities=(QuantityResult("", force, "N"),),
        )

    if op == "bernoulli_pressure":
        if p["rho"] <= 0 or p["pres1"] < 0:
            raise SolveServiceError("Bernoulli pressure needs positive density and valid pressure")
        gravity = p.get("g", 9.81)
        pressure = p["pres1"] + 0.5 * p["rho"] * (p["v1"] ** 2 - p["v2"] ** 2)
        if "h1" in p and "h2" in p:
            pressure += p["rho"] * gravity * (p["h1"] - p["h2"])
        if pressure < 0:
            raise SolveServiceError(
                "the stated ideal-flow values imply a negative absolute pressure"
            )
        if "h1" in p and "h2" in p:
            return PhysicsResult(
                answer=(
                    r"P_1 + \frac{1}{2}\rho v_1^2 + \rho g h_1 = "
                    r"P_2 + \frac{1}{2}\rho v_2^2 + \rho g h_2 "
                    r"\Rightarrow P_2 = P_1 + \frac{1}{2}\rho(v_1^2-v_2^2)"
                    rf" + \rho g(h_1-h_2) \approx {pressure:g} \text{{ Pa}}"
                ),
                formulas=(r"P_2 = P_1 + \frac{1}{2}\rho(v_1^2-v_2^2) + \rho g(h_1-h_2)",),
                substitutions=(
                    rf"P_2 = {p['pres1']:g} + \frac{{1}}{{2}} \cdot {p['rho']:g} \cdot "
                    rf"({p['v1']:g}^2 - {p['v2']:g}^2) + {p['rho']:g} \cdot {gravity:g} \cdot "
                    rf"({p['h1']:g} - {p['h2']:g})",
                ),
                quantities=(QuantityResult("", pressure, "Pa"),),
            )
        return PhysicsResult(
            answer=(
                r"P_1 + \frac{1}{2}\rho v_1^2 = P_2 + \frac{1}{2}\rho v_2^2 "
                r"\Rightarrow P_2 = P_1 + \frac{1}{2}\rho(v_1^2-v_2^2) = "
                rf"{p['pres1']:g} + \frac{{1}}{{2}} \cdot {p['rho']:g} "
                rf"\cdot ({p['v1']:g}^2 - {p['v2']:g}^2) "
                rf"\approx {pressure:g} \text{{ Pa}}"
            ),
            formulas=(r"P_2 = P_1 + \frac{1}{2}\rho(v_1^2-v_2^2)",),
            substitutions=(
                rf"P_2 = {p['pres1']:g} + \frac{{1}}{{2}} \cdot {p['rho']:g} \cdot ({p['v1']:g}^2 "
                rf"- {p['v2']:g}^2)",
            ),
            quantities=(QuantityResult("", pressure, "Pa"),),
        )

    if op == "pressure_from_force":
        area = p["area"]
        if area <= 0:
            raise SolveServiceError("area must be positive")
        pressure = p["F"] / area
        return PhysicsResult(
            answer=(
                rf"P = \frac{{F}}{{A}} = \frac{{{p['F']:g}}}{{{area:g}}} "
                rf"\approx {pressure:.2f} \text{{ Pa}}"
            ),
            formulas=(r"P = \frac{F}{A}",),
            substitutions=(rf"P = \frac{{{p['F']:g}}}{{{area:g}}}",),
            quantities=(QuantityResult("", pressure, "Pa"),),
        )

    if op == "pressure_at_depth":
        pressure = p["rho"] * p.get("g", 9.81) * p["depth"]
        return PhysicsResult(
            answer=(
                rf"P = \rho g h = {p['rho']:g} \cdot {p.get('g', 9.81):g} \cdot "
                rf"{p['depth']:g} \approx {pressure:.2f} \text{{ Pa}}"
            ),
            formulas=(r"P = \rho g h",),
            substitutions=(rf"P = {p['rho']:g} \cdot {p.get('g', 9.81):g} \cdot {p['depth']:g}",),
            # Gauge, and it says so: the absolute reading is this plus one
            # atmosphere, and which one is meant changes the number by 101 kPa.
            quantities=(QuantityResult("", pressure, "Pa", detail="gauge"),),
        )

    if op == "upthrust":
        force = p["rho"] * p["volume"] * p.get("g", 9.81)
        return PhysicsResult(
            answer=(
                rf"F_b = \rho V g = {p['rho']:g} \cdot {p['volume']:g} \cdot "
                rf"{p.get('g', 9.81):g} \approx {force:.2f} \text{{ N}}"
            ),
            formulas=(r"F_b = \rho V g",),
            substitutions=(
                rf"F_b = {p['rho']:g} \cdot {p['volume']:g} \cdot {p.get('g', 9.81):g}",
            ),
            quantities=(QuantityResult("", force, "N"),),
            # The one fluids answer a free body actually draws: an upward
            # buoyant force against the weight it opposes.
            simulation_specs=_free_body_scene(
                [
                    SimulationVector(
                        anchor=[0.0, 0.0],
                        dx=0.0,
                        dy=1.0,
                        label=f"upthrust {plain_number(force)} N",
                        role="force",
                    ),
                    SimulationVector(
                        anchor=[0.0, 0.0], dx=0.0, dy=-1.0, label="weight", role="force"
                    ),
                ],
                label="body",
            ),
        )

    if op == "density":
        volume = p["volume"]
        if volume <= 0:
            raise SolveServiceError("volume must be positive")
        rho = p["m"] / volume
        return PhysicsResult(
            answer=(
                rf"\rho = \frac{{m}}{{V}} = \frac{{{p['m']:g}}}{{{volume:g}}} "
                rf"\approx {rho:.2f} \text{{ kg/m}}^3"
            ),
            formulas=(r"\rho = \frac{m}{V}",),
            substitutions=(rf"\rho = \frac{{{p['m']:g}}}{{{volume:g}}}",),
            quantities=(QuantityResult("", rho, "kg/m^3"),),
        )

    if op == "continuity_velocity":
        a2 = p["A2"]
        if a2 <= 0:
            raise SolveServiceError("the second area must be positive")
        v2 = p["A1"] * p["v"] / a2
        return PhysicsResult(
            answer=(
                rf"A_1 v_1 = A_2 v_2 \Rightarrow v_2 = \frac{{{p['A1']:g} \cdot "
                rf"{p['v']:g}}}{{{a2:g}}} \approx {v2:.2f} \text{{ m/s}}"
            ),
            formulas=(r"v_2 = \frac{A_1 v_1}{A_2}",),
            substitutions=(rf"v_2 = \frac{{{p['A1']:g} \cdot {p['v']:g}}}{{{a2:g}}}",),
            quantities=(QuantityResult("", v2, "m/s"),),
        )

    if op == "flow_rate":
        flow = p["area"] * p["v"]
        return PhysicsResult(
            answer=(
                rf"Q = A v = {p['area']:g} \cdot {p['v']:g} \approx {flow:.4g} "
                rf"\text{{ m}}^3\text{{/s}}"
            ),
            formulas=(r"Q = A v",),
            substitutions=(rf"Q = {p['area']:g} \cdot {p['v']:g}",),
            quantities=(QuantityResult("", flow, "m^3/s"),),
        )

    raise SolveServiceError(f"unsupported fluids op: {op}")
