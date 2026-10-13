"""Circuit solvers: Ohm's law, power, charge, energy, resistor networks and capacitors."""

from __future__ import annotations

from collections.abc import Callable

from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.solvers.common import (
    _EPSILON_0,
    _RESISTOR_KEY_RE,
    PhysicsResult,
    QuantityResult,
    _latex_num,
    _params_in_si,
)
from app.services.solving import SolveServiceError


def solve_circuit(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "current"
    solver = _OPERATIONS.get(op)
    if solver is None:
        raise SolveServiceError(f"unsupported circuit op: {op}")
    return solver(intent, p)


def _parallel_plate_capacitance(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    if p["area"] <= 0 or p["d"] <= 0:
        raise SolveServiceError("parallel-plate capacitance needs positive area and spacing")
    value = _EPSILON_0 * p["area"] / p["d"]
    return PhysicsResult(
        answer=(
            rf"C = \frac{{\epsilon_0 A}}{{d}} = "
            rf"\frac{{{_EPSILON_0:.5g} \cdot {p['area']:g}}}{{{p['d']:g}}} "
            rf"\approx {value:.4g} \text{{ F}}"
        ),
        formulas=(r"C = \frac{\epsilon_0 A}{d}",),
        substitutions=(rf"C = \frac{{{_EPSILON_0:.5g} \cdot {p['area']:g}}}{{{p['d']:g}}}",),
        quantities=(QuantityResult("", value, "F"),),
    )


def _capacitor_energy(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    if p["capacitance"] < 0:
        raise SolveServiceError("capacitance cannot be negative")
    value = 0.5 * p["capacitance"] * p["V"] ** 2
    return PhysicsResult(
        answer=(
            rf"U = \frac{{1}}{{2}}CV^2 = \frac{{1}}{{2}} \cdot "
            rf"{p['capacitance']:g} \cdot {p['V']:g}^2 "
            rf"\approx {value:.4g} \text{{ J}}"
        ),
        formulas=(r"U = \frac{1}{2}CV^2",),
        substitutions=(rf"U = \frac{{1}}{{2}} \cdot {p['capacitance']:g} \cdot {p['V']:g}^2",),
        quantities=(QuantityResult("", value, "J"),),
    )


def _rc_time_constant(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    if p["R"] < 0 or p["capacitance"] < 0:
        raise SolveServiceError("RC time constant needs nonnegative R and C")
    value = p["R"] * p["capacitance"]
    return PhysicsResult(
        answer=(
            rf"\tau = RC = {p['R']:g} \cdot {p['capacitance']:g} "
            rf"\approx {value:.4g} \text{{ s}}"
        ),
        formulas=(r"\tau = RC",),
        substitutions=(rf"\tau = {p['R']:g} \cdot {p['capacitance']:g}",),
        quantities=(QuantityResult("", value, "s"),),
    )


def _combined_resistance(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    op = intent.physics_op or "current"
    # Every R the extractor found, not the first two. Reading three and
    # using two is how "2, 3 and 5 ohms in series" answered 5 ohms.
    resistances = [p[key] for key in sorted(p) if _RESISTOR_KEY_RE.fullmatch(key)]
    if len(resistances) < 2:
        raise SolveServiceError("a resistor network needs at least two resistances")
    if any(r <= 0 for r in resistances):
        raise SolveServiceError("resistances must be positive")
    terms = " + ".join(f"{r:g}" for r in resistances)
    if op == "series_resistance":
        total = sum(resistances)
        answer = rf"R = \sum R_i = {terms} \approx {total:.2f} \,\Omega"
        formula = r"R = \sum R_i"
        substitution = rf"R_s = {terms}"
    else:
        total = 1 / sum(1 / r for r in resistances)
        reciprocals = " + ".join(rf"\frac{{1}}{{{r:g}}}" for r in resistances)
        symbols = " + ".join(
            rf"\frac{{1}}{{R_{index}}}" for index in range(1, len(resistances) + 1)
        )
        answer = (
            rf"\frac{{1}}{{R}} = {reciprocals} \Rightarrow R "
            rf"\approx {total:.2f} \,\Omega"
        )
        formula = rf"\frac{{1}}{{R_p}} = {symbols}"
        substitution = reciprocals
    return PhysicsResult(
        answer=answer,
        formulas=(formula,),
        substitutions=(substitution,),
        quantities=(QuantityResult("", total, "ohm"),),
    )


def _charge(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    q_val = p["I"] * p["t"]
    return PhysicsResult(
        answer=(rf"Q = I t = {p['I']:g} \cdot {p['t']:g} \approx {q_val:.2f} \text{{ C}}"),
        formulas=(r"Q = I t",),
        substitutions=(rf"Q = {p['I']:g} \cdot {p['t']:g}",),
        quantities=(QuantityResult("", q_val, "C"),),
    )


def _electrical_energy(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    e_val = p["power"] * p["t"]
    kwh = e_val / 3.6e6
    return PhysicsResult(
        answer=(
            rf"E = P t = {p['power']:g} \cdot {p['t']:g} \approx "
            rf"{e_val:.2f} \text{{ J}} \; ({kwh:.2f} \text{{ kWh}})"
        ),
        formulas=(r"E = P t",),
        substitutions=(rf"E = {p['power']:g} \cdot {p['t']:g}",),
        quantities=(QuantityResult("", e_val, "J"),),
    )


def _capacitance(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    if p["V"] == 0:
        raise SolveServiceError("capacitance needs a nonzero voltage")
    c_val = p["Q"] / p["V"]
    return PhysicsResult(
        answer=(
            rf"C = \frac{{Q}}{{V}} = \frac{{{p['Q']:g}}}{{{p['V']:g}}} "
            rf"\approx {c_val:.2f} \text{{ F}}"
        ),
        formulas=(r"C = \frac{Q}{V}",),
        substitutions=(rf"C = \frac{{{p['Q']:g}}}{{{p['V']:g}}}",),
        quantities=(QuantityResult("", c_val, "F"),),
    )


def _terminal_voltage(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    v_val = p["E_emf"] - p["I"] * p["r_int"]
    return PhysicsResult(
        answer=(
            rf"V = \varepsilon - I r = {p['E_emf']:g} - {p['I']:g} \cdot "
            rf"{p['r_int']:g} \approx {v_val:.2f} \text{{ V}}"
        ),
        formulas=(r"V = \varepsilon - I r",),
        substitutions=(rf"V_{{terminal}} = {p['E_emf']:g} - {p['I']:g} \cdot {p['r_int']:g}",),
        quantities=(QuantityResult("", v_val, "V"),),
    )


def _electrical_power(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    if "V" in p and "I" in p:
        val = p["V"] * p["I"]
        answer = rf"P = VI = {p['V']:g} \cdot {p['I']:g} \approx {val:.2f} \text{{ W}}"
        formula = r"P = VI"
        substitution = rf"P = {p['V']:g} \cdot {p['I']:g}"
    elif "I" in p and "R" in p:
        val = p["I"] ** 2 * p["R"]
        plugged = rf"{_latex_num(p['I'], square=True)} \cdot {p['R']:g}"
        answer = rf"P = I^2 R = {plugged} \approx {val:.2f} \text{{ W}}"
        formula = r"P = I^2 R"
        substitution = rf"P = {plugged}"
    elif "V" in p and "R" in p:
        if p["R"] == 0:
            raise SolveServiceError("resistance must be nonzero")
        val = p["V"] ** 2 / p["R"]
        plugged = rf"\frac{{{_latex_num(p['V'], square=True)}}}{{{p['R']:g}}}"
        answer = rf"P = \frac{{V^2}}{{R}} = {plugged} \approx {val:.2f} \text{{ W}}"
        formula = r"P = \frac{V^2}{R}"
        substitution = rf"P = {plugged}"
    else:
        raise SolveServiceError("electrical power needs two of V, I, R")
    return PhysicsResult(
        answer=answer,
        formulas=(formula,),
        substitutions=(substitution,),
        quantities=(QuantityResult("", val, "W"),),
    )


def _current(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    if p["R"] == 0:
        raise SolveServiceError("resistance must be nonzero")
    val = p["V"] / p["R"]
    return PhysicsResult(
        answer=(
            rf"I = \frac{{V}}{{R}} = \frac{{{p['V']:g}}}{{{p['R']:g}}} "
            rf"\approx {val:.2f} \text{{ A}}"
        ),
        formulas=(r"I = \frac{V}{R}",),
        substitutions=(rf"I = \frac{{{p['V']:g}}}{{{p['R']:g}}}",),
        quantities=(QuantityResult("", val, "A"),),
    )


def _voltage(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    val = p["I"] * p["R"]
    return PhysicsResult(
        answer=rf"V = IR = {p['I']:g} \cdot {p['R']:g} \approx {val:.2f} \text{{ V}}",
        formulas=(r"V = IR",),
        substitutions=(rf"V = {p['I']:g} \cdot {p['R']:g}",),
        quantities=(QuantityResult("", val, "V"),),
    )


def _resistance(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    if p["I"] == 0:
        raise SolveServiceError("current must be nonzero")
    val = p["V"] / p["I"]
    return PhysicsResult(
        answer=(
            rf"R = \frac{{V}}{{I}} = \frac{{{p['V']:g}}}{{{p['I']:g}}} "
            rf"\approx {val:.2f} \,\Omega"
        ),
        formulas=(r"R = \frac{V}{I}",),
        substitutions=(rf"R = \frac{{{p['V']:g}}}{{{p['I']:g}}}",),
        quantities=(QuantityResult("", val, "ohm"),),
    )


_OPERATIONS: dict[str, Callable[[PhysicsIntent, dict[str, float]], PhysicsResult]] = {
    "parallel_plate_capacitance": _parallel_plate_capacitance,
    "capacitor_energy": _capacitor_energy,
    "rc_time_constant": _rc_time_constant,
    "series_resistance": _combined_resistance,
    "parallel_resistance": _combined_resistance,
    "charge": _charge,
    "electrical_energy": _electrical_energy,
    "capacitance": _capacitance,
    "terminal_voltage": _terminal_voltage,
    "electrical_power": _electrical_power,
    "current": _current,
    "voltage": _voltage,
    "resistance": _resistance,
}
