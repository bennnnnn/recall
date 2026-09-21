"""Circuit, electrostatics, and magnetism solvers."""

from __future__ import annotations

import math

from app.models.schemas.physics import (
    PhysicsIntent,
)
from app.services.physics.solvers.common import (
    _COULOMB_K,
    _EPSILON_0,
    _MU_0,
    _RESISTOR_KEY_RE,
    PhysicsResult,
    _latex_num,
    _latex_scientific,
    _params_in_si,
)
from app.services.solving import MathServiceError


def solve_circuit(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "current"

    if op == "parallel_plate_capacitance":
        if p["area"] <= 0 or p["d"] <= 0:
            raise MathServiceError("parallel-plate capacitance needs positive area and spacing")
        value = _EPSILON_0 * p["area"] / p["d"]
        return PhysicsResult(
            answer=(
                rf"C = \frac{{\epsilon_0 A}}{{d}} = "
                rf"\frac{{{_EPSILON_0:.5g} \cdot {p['area']:g}}}{{{p['d']:g}}} "
                rf"\approx {value:.4g} \text{{ F}}"
            ),
            answer_value=f"{value:.4g} F",
        )

    if op == "capacitor_energy":
        if p["capacitance"] < 0:
            raise MathServiceError("capacitance cannot be negative")
        value = 0.5 * p["capacitance"] * p["V"] ** 2
        return PhysicsResult(
            answer=(
                rf"U = \frac{{1}}{{2}}CV^2 = \frac{{1}}{{2}} \cdot "
                rf"{p['capacitance']:g} \cdot {p['V']:g}^2 "
                rf"\approx {value:.4g} \text{{ J}}"
            ),
            answer_value=f"{value:.4g} J",
        )

    if op == "rc_time_constant":
        if p["R"] < 0 or p["capacitance"] < 0:
            raise MathServiceError("RC time constant needs nonnegative R and C")
        value = p["R"] * p["capacitance"]
        return PhysicsResult(
            answer=(
                rf"\tau = RC = {p['R']:g} \cdot {p['capacitance']:g} "
                rf"\approx {value:.4g} \text{{ s}}"
            ),
            answer_value=f"{value:.4g} s",
        )

    if op in ("series_resistance", "parallel_resistance"):
        # Every R the extractor found, not the first two. Reading three and
        # using two is how "2, 3 and 5 ohms in series" answered 5 ohms.
        resistances = [p[key] for key in sorted(p) if _RESISTOR_KEY_RE.fullmatch(key)]
        if len(resistances) < 2:
            raise MathServiceError("a resistor network needs at least two resistances")
        if any(r <= 0 for r in resistances):
            raise MathServiceError("resistances must be positive")
        terms = " + ".join(f"{r:g}" for r in resistances)
        if op == "series_resistance":
            total = sum(resistances)
            answer = rf"R = \sum R_i = {terms} \approx {total:.2f} \,\Omega"
        else:
            total = 1 / sum(1 / r for r in resistances)
            reciprocals = " + ".join(rf"\frac{{1}}{{{r:g}}}" for r in resistances)
            answer = (
                rf"\frac{{1}}{{R}} = {reciprocals} \Rightarrow R "
                rf"\approx {total:.2f} \,\Omega"
            )
        return PhysicsResult(answer=answer, answer_value=f"{total:.2f} ohm")

    if op == "charge":
        q_val = p["I"] * p["t"]
        return PhysicsResult(
            answer=(rf"Q = I t = {p['I']:g} \cdot {p['t']:g} \approx {q_val:.2f} \text{{ C}}"),
            answer_value=f"{q_val:.2f} C",
        )

    if op == "electrical_energy":
        e_val = p["power"] * p["t"]
        kwh = e_val / 3.6e6
        return PhysicsResult(
            answer=(
                rf"E = P t = {p['power']:g} \cdot {p['t']:g} \approx "
                rf"{e_val:.2f} \text{{ J}} \; ({kwh:.2f} \text{{ kWh}})"
            ),
            answer_value=f"{e_val:.2f} J",
        )

    if op == "capacitance":
        if p["V"] == 0:
            raise MathServiceError("capacitance needs a nonzero voltage")
        c_val = p["Q"] / p["V"]
        return PhysicsResult(
            answer=(
                rf"C = \frac{{Q}}{{V}} = \frac{{{p['Q']:g}}}{{{p['V']:g}}} "
                rf"\approx {c_val:.2f} \text{{ F}}"
            ),
            answer_value=f"{c_val:.2f} F",
        )

    if op == "terminal_voltage":
        v_val = p["E_emf"] - p["I"] * p["r_int"]
        return PhysicsResult(
            answer=(
                rf"V = \varepsilon - I r = {p['E_emf']:g} - {p['I']:g} \cdot "
                rf"{p['r_int']:g} \approx {v_val:.2f} \text{{ V}}"
            ),
            answer_value=f"{v_val:.2f} V",
        )

    if op == "electrical_power":
        if "V" in p and "I" in p:
            val = p["V"] * p["I"]
            answer = rf"P = VI = {p['V']:g} \cdot {p['I']:g} \approx {val:.2f} \text{{ W}}"
        elif "I" in p and "R" in p:
            val = p["I"] ** 2 * p["R"]
            answer = (
                rf"P = I^2 R = {_latex_num(p['I'], square=True)} \cdot {p['R']:g} "
                rf"\approx {val:.2f} \text{{ W}}"
            )
        elif "V" in p and "R" in p:
            if p["R"] == 0:
                raise MathServiceError("resistance must be nonzero")
            val = p["V"] ** 2 / p["R"]
            answer = (
                rf"P = \frac{{V^2}}{{R}} = \frac{{{_latex_num(p['V'], square=True)}}}"
                rf"{{{p['R']:g}}} \approx {val:.2f} \text{{ W}}"
            )
        else:
            raise MathServiceError("electrical power needs two of V, I, R")
        return PhysicsResult(answer=answer, answer_value=f"{val:.2f} W")

    if op == "current":
        if p["R"] == 0:
            raise MathServiceError("resistance must be nonzero")
        val = p["V"] / p["R"]
        return PhysicsResult(
            answer=(
                rf"I = \frac{{V}}{{R}} = \frac{{{p['V']:g}}}{{{p['R']:g}}} "
                rf"\approx {val:.2f} \text{{ A}}"
            ),
            answer_value=f"{val:.2f} A",
        )

    if op == "voltage":
        val = p["I"] * p["R"]
        return PhysicsResult(
            answer=rf"V = IR = {p['I']:g} \cdot {p['R']:g} \approx {val:.2f} \text{{ V}}",
            answer_value=f"{val:.2f} V",
        )

    if op == "resistance":
        if p["I"] == 0:
            raise MathServiceError("current must be nonzero")
        val = p["V"] / p["I"]
        return PhysicsResult(
            answer=(
                rf"R = \frac{{V}}{{I}} = \frac{{{p['V']:g}}}{{{p['I']:g}}} "
                rf"\approx {val:.2f} \,\Omega"
            ),
            answer_value=f"{val:.2f} ohm",
        )

    raise MathServiceError(f"unsupported circuit op: {op}")


# ---------------------------------------------------------------------------
# Electrostatics and magnetism
# ---------------------------------------------------------------------------


def solve_magnetism(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "electric_field":
        if p["r"] <= 0:
            raise MathServiceError("distance from the point charge must be positive")
        value = _COULOMB_K * abs(p["Q"]) / p["r"] ** 2
        return PhysicsResult(
            answer=(
                rf"E = k_e\frac{{\lvert Q\rvert}}{{r^2}} = {_COULOMB_K:.7g} \cdot "
                rf"\frac{{\lvert {p['Q']:g}\rvert}}{{{p['r']:g}^2}} "
                rf"\approx {value:.4g} \text{{ N/C}}"
            ),
            answer_value=f"{value:.4g} N/C",
        )

    if op == "electric_potential":
        if p["r"] <= 0:
            raise MathServiceError("distance from the point charge must be positive")
        value = _COULOMB_K * p["Q"] / p["r"]
        return PhysicsResult(
            answer=(
                rf"V = k_e\frac{{Q}}{{r}} = {_COULOMB_K:.7g} \cdot "
                rf"\frac{{{p['Q']:g}}}{{{p['r']:g}}} \approx {value:.4g} \text{{ V}}"
            ),
            answer_value=f"{value:.4g} V",
        )

    if op == "electric_potential_energy":
        if p["r"] <= 0:
            raise MathServiceError("charge separation must be positive")
        value = _COULOMB_K * p["q1"] * p["q2"] / p["r"]
        return PhysicsResult(
            answer=(
                rf"U = k_e\frac{{q_1q_2}}{{r}} = {_COULOMB_K:.7g} \cdot "
                rf"\frac{{{p['q1']:g} \cdot {p['q2']:g}}}{{{p['r']:g}}} "
                rf"\approx {value:.4g} \text{{ J}}"
            ),
            answer_value=f"{value:.4g} J",
        )

    if op == "charged_particle_radius":
        denominator = abs(p["Q"]) * p["b_field"]
        if p["m"] <= 0 or p["v"] < 0 or denominator <= 0:
            raise MathServiceError("magnetic radius needs positive mass, charge, and field")
        value = p["m"] * p["v"] / denominator
        return PhysicsResult(
            answer=(
                rf"r = \frac{{mv}}{{\lvert q\rvert B}} = "
                rf"\frac{{{p['m']:g} \cdot {p['v']:g}}}"
                rf"{{{abs(p['Q']):g} \cdot {p['b_field']:g}}} "
                rf"\approx {value:.4g} \text{{ m}}"
            ),
            answer_value=f"{value:.4g} m",
        )

    if op == "motional_emf":
        value = p["b_field"] * p["wire_L"] * p["v"]
        return PhysicsResult(
            answer=(
                rf"\mathcal{{E}} = BLv = {p['b_field']:g} \cdot {p['wire_L']:g} "
                rf"\cdot {p['v']:g} \approx {value:.4g} \text{{ V}}"
            ),
            answer_value=f"{value:.4g} V",
        )

    if op == "magnetic_field_wire":
        if p["r"] <= 0:
            raise MathServiceError("distance from the wire must be positive")
        value = _MU_0 * p["I"] / (2 * math.pi * p["r"])
        return PhysicsResult(
            answer=(
                rf"B = \frac{{\mu_0 I}}{{2\pi r}} = "
                rf"\frac{{{_MU_0:.7g} \cdot {p['I']:g}}}{{2\pi \cdot {p['r']:g}}} "
                rf"\approx {value:.4g} \text{{ T}}"
            ),
            answer_value=f"{value:.4g} T",
        )

    if op == "electric_force":
        separation = p["r"]
        if separation <= 0:
            raise MathServiceError("charge separation must be positive")
        value = _COULOMB_K * abs(p["q1"] * p["q2"]) / separation**2
        display_value = f"{value:.4g}"
        return PhysicsResult(
            answer=(
                rf"F_e = k_e \frac{{\lvert q_1q_2\rvert}}{{r^2}} = "
                rf"{_latex_scientific(_COULOMB_K)} \cdot "
                rf"\frac{{\lvert {_latex_scientific(p['q1'])} \cdot "
                rf"{_latex_scientific(p['q2'])}"
                rf"\rvert}}{{{_latex_num(separation, square=True)}}} "
                rf"\approx {display_value} \text{{ N}}"
            ),
            answer_value=f"{display_value} N",
        )

    if op == "magnetic_force_wire":
        value = p["b_field"] * p["I"] * p["wire_L"]
        return PhysicsResult(
            answer=(
                rf"F = BIL = {p['b_field']:g} \cdot {p['I']:g} \cdot {p['wire_L']:g} "
                rf"\approx {value:.2f} \text{{ N}}"
            ),
            answer_value=f"{value:.2f} N",
        )

    if op == "magnetic_force_charge":
        value = p["Q"] * p["v"] * p["b_field"]
        display_value = f"{value:.4g}" if 0 < abs(value) < 0.01 else f"{value:.2f}"
        return PhysicsResult(
            answer=(
                rf"F = qvB = {p['Q']:g} \cdot {p['v']:g} \cdot {p['b_field']:g} "
                rf"\approx {display_value} \text{{ N}}"
            ),
            # The full form carries sin(theta); this is the perpendicular case,
            # which is the one every school question states.
            answer_value=f"{display_value} N (field perpendicular to the motion)",
        )

    if op == "magnetic_flux":
        value = p["b_field"] * p["area"]
        return PhysicsResult(
            answer=(
                rf"\Phi = BA = {p['b_field']:g} \cdot {p['area']:g} "
                rf"\approx {value:.4g} \text{{ Wb}}"
            ),
            answer_value=f"{value:.4g} Wb",
        )

    raise MathServiceError(f"unsupported magnetism op: {op}")
