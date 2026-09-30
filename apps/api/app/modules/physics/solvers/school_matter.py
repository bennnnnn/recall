"""Closed fluids, gravitation, and thermal solvers."""

from __future__ import annotations

import math

from app.modules.physics.catalog.thermal import HEAVY_PISTON_EQUATIONS
from app.modules.physics.solvers.common import (
    _BIG_G,
    _GAS_CONSTANT,
    PhysicsResult,
    QuantityResult,
    solved,
)
from app.modules.physics.solvers.school_common import positive, result
from app.services.solving import SolveServiceError


def _poiseuille(params: dict[str, float]) -> PhysicsResult:
    positive(params, "r", "L", "viscosity")
    value = (
        math.pi
        * params["r"] ** 4
        * params["delta_pressure"]
        / (8 * params["viscosity"] * params["L"])
    )
    return result(
        "Q",
        r"\frac{\pi r^4\Delta P}{8\eta L}",
        rf"\frac{{\pi {params['r']:g}^4\cdot {params['delta_pressure']:g}}}"
        rf"{{8\cdot {params['viscosity']:g}\cdot {params['L']:g}}}",
        value,
        "m^3/s",
    )


def _potential(params: dict[str, float]) -> PhysicsResult:
    positive(params, "M", "r")
    value = -_BIG_G * params["M"] / params["r"]
    numeric = rf"-\frac{{{_BIG_G:.5g}\cdot {params['M']:g}}}{{{params['r']:g}}}"
    return result("V", r"-\frac{GM}{r}", numeric, value, "J/kg")


def _potential_energy(params: dict[str, float]) -> PhysicsResult:
    positive(params, "M", "r")
    value = -_BIG_G * params["M"] * params["m"] / params["r"]
    numeric = (
        rf"-\frac{{{_BIG_G:.5g}\cdot {params['M']:g}\cdot {params['m']:g}}}{{{params['r']:g}}}"
    )
    return result("U", r"-\frac{GMm}{r}", numeric, value, "J")


def _orbital_energy(params: dict[str, float]) -> PhysicsResult:
    positive(params, "M", "r")
    value = -_BIG_G * params["M"] * params["m"] / (2 * params["r"])
    numeric = (
        rf"-\frac{{{_BIG_G:.5g}\cdot {params['M']:g}\cdot {params['m']:g}}}"
        rf"{{2\cdot {params['r']:g}}}"
    )
    return result("E", r"-\frac{GMm}{2r}", numeric, value, "J")


def _kepler(params: dict[str, float]) -> PhysicsResult:
    positive(params, "M", "r")
    value = 2 * math.pi * math.sqrt(params["r"] ** 3 / (_BIG_G * params["M"]))
    return result(
        "T",
        r"2\pi\sqrt{\frac{r^3}{GM}}",
        rf"2\pi\sqrt{{\frac{{{params['r']:g}^3}}{{{_BIG_G:.5g}\cdot {params['M']:g}}}}}",
        value,
        "s",
    )


def _monatomic(params: dict[str, float]) -> PhysicsResult:
    positive(params, "moles", "temp")
    value = 1.5 * params["moles"] * _GAS_CONSTANT * params["temp"]
    numeric = (
        rf"\frac{{3}}{{2}}\cdot {params['moles']:g}"
        rf"\cdot {_GAS_CONSTANT:.4f}\cdot {params['temp']:g}"
    )
    return result("U", r"\frac{3}{2}nRT", numeric, value, "J")


def _isobaric(params: dict[str, float]) -> PhysicsResult:
    positive(params, "pres", "vol1", "vol2")
    value = params["pres"] * (params["vol2"] - params["vol1"])
    return result(
        "W",
        r"P\Delta V",
        rf"{params['pres']:g}\cdot ({params['vol2']:g}-{params['vol1']:g})",
        value,
        "J",
    )


def _adiabatic_pressure(params: dict[str, float]) -> PhysicsResult:
    positive(params, "pres1", "vol1", "vol2")
    if params["gamma_gas"] <= 1:
        raise SolveServiceError("adiabatic gamma must be greater than 1")
    value = params["pres1"] * (params["vol1"] / params["vol2"]) ** params["gamma_gas"]
    ratio = f"{params['vol1']:g}/{params['vol2']:g}"
    numeric = rf"{params['pres1']:g}\cdot ({ratio})^{{{params['gamma_gas']:g}}}"
    return result("P_2", r"P_1(V_1/V_2)^\gamma", numeric, value, "Pa")


def _adiabatic_volume(params: dict[str, float]) -> PhysicsResult:
    positive(params, "pres1", "pres2", "vol1")
    if params["gamma_gas"] <= 1:
        raise SolveServiceError("adiabatic gamma must be greater than 1")
    value = params["vol1"] * (params["pres1"] / params["pres2"]) ** (1 / params["gamma_gas"])
    numeric = (
        rf"{params['vol1']:g}\cdot ({params['pres1']:g}/{params['pres2']:g})"
        rf"^{{1/{params['gamma_gas']:g}}}"
    )
    return result("V_2", r"V_1(P_1/P_2)^{1/\gamma}", numeric, value, "m^3")


def _refrigerator(params: dict[str, float]) -> PhysicsResult:
    return _cop("refrigerator_cop", params)


def _heat_pump(params: dict[str, float]) -> PhysicsResult:
    return _cop("heat_pump_cop", params)


def _cop(kind: str, params: dict[str, float]) -> PhysicsResult:
    hot = params["temp"]
    cold = params["temp_env"]
    if cold <= 0 or hot <= cold:
        raise SolveServiceError("need absolute temperatures with the hot side warmer")
    if kind == "heat_pump_cop":
        value = hot / (hot - cold)
        numeric = rf"\frac{{{hot:g}}}{{{hot:g}-{cold:g}}}"
        return result("COP", r"\frac{T_H}{T_H-T_C}", numeric, value, "")
    value = cold / (hot - cold)
    numeric = rf"\frac{{{cold:g}}}{{{hot:g}-{cold:g}}}"
    return result("COP", r"\frac{T_C}{T_H-T_C}", numeric, value, "")


def _heavy_piston(params: dict[str, float]) -> PhysicsResult:
    positive(params, "moles", "M", "area", "p_atm", "temp", "g")
    gas_r = params["gas_r"] if "gas_r" in params else _GAS_CONSTANT
    if gas_r <= 0:
        raise SolveServiceError("gas constant must be positive")
    moles, mass, area = params["moles"], params["M"], params["area"]
    p0, temp, gravity = params["p_atm"], params["temp"], params["g"]
    load = mass * gravity / area
    p_eq, v_eq, t_hot, work_eq, heat_eq, p_flip, v_flip = HEAVY_PISTON_EQUATIONS
    formulas: list[str] = []
    substitutions: list[str] = []
    quantities: list[QuantityResult] = []

    def push(equation: str, numeric: str, value: float, unit: str) -> None:
        symbol = equation.split(" = ", 1)[0]
        formulas.append(equation)
        substitutions.append(f"{symbol} = {numeric}")
        quantities.append(QuantityResult(symbol, value, unit, number_format=".6g"))

    if "upright" in params:
        pressure = p0 + load
        volume = moles * gas_r * temp / pressure
        push(
            p_eq,
            rf"{p0:g} + \frac{{{mass:g} \cdot {gravity:g}}}{{{area:g}}}",
            pressure,
            "Pa",
        )
        push(
            v_eq,
            rf"\frac{{{moles:g} \cdot {gas_r:g} \cdot {temp:g}}}{{{pressure:g}}}",
            volume,
            "m^3",
        )
        if "expand_ratio" in params:
            ratio = params["expand_ratio"]
            if ratio <= 1:
                raise SolveServiceError("expansion ratio must be greater than 1")
            final_t = temp * ratio
            work = moles * gas_r * temp * (ratio - 1)
            push(t_hot, rf"{temp:g} \cdot {ratio:g}", final_t, "K")
            push(
                work_eq,
                rf"{moles:g} \cdot {gas_r:g} \cdot {temp:g} \cdot ({ratio:g} - 1)",
                work,
                "J",
            )
            if "cv_over_r" in params:
                cv = params["cv_over_r"]
                if cv <= 0:
                    raise SolveServiceError("heat capacity must be positive")
                delta_t = final_t - temp
                heat = moles * (cv + 1) * gas_r * delta_t
                cp_tex = r"\frac{5}{2}" if cv + 1 == 2.5 else f"{cv + 1:g}"
                push(
                    heat_eq,
                    rf"{moles:g} \cdot {cp_tex} \cdot {gas_r:g} \cdot {delta_t:g}",
                    heat,
                    "J",
                )
    if "flip" in params:
        # The inverted equilibrium is held at the original temperature.
        flipped = p0 - load
        if flipped <= 0:
            raise SolveServiceError("inverted piston is not supported by the atmosphere")
        volume = moles * gas_r * temp / flipped
        push(
            p_flip,
            rf"{p0:g} - \frac{{{mass:g} \cdot {gravity:g}}}{{{area:g}}}",
            flipped,
            "Pa",
        )
        push(
            v_flip,
            rf"\frac{{{moles:g} \cdot {gas_r:g} \cdot {temp:g}}}{{{flipped:g}}}",
            volume,
            "m^3",
        )
    if not quantities:
        raise SolveServiceError("heavy piston needs an upright or inverted equilibrium")
    return solved(
        *quantities,
        answer="heavy piston",
        formulas=tuple(formulas),
        substitutions=tuple(substitutions),
        joiner="; ",
    )


def _ideal_volume(params: dict[str, float]) -> PhysicsResult:
    positive(params, "pres", "moles", "temp")
    value = params["moles"] * _GAS_CONSTANT * params["temp"] / params["pres"]
    numeric = (
        rf"\frac{{{params['moles']:g}\cdot {_GAS_CONSTANT:.4f}"
        rf"\cdot {params['temp']:g}}}{{{params['pres']:g}}}"
    )
    return result("V", r"\frac{nRT}{P}", numeric, value, "m^3")


def _ideal_amount(params: dict[str, float]) -> PhysicsResult:
    positive(params, "pres", "volume", "temp")
    value = params["pres"] * params["volume"] / (_GAS_CONSTANT * params["temp"])
    numeric = (
        rf"\frac{{{params['pres']:g}\cdot {params['volume']:g}}}"
        rf"{{{_GAS_CONSTANT:.4f}\cdot {params['temp']:g}}}"
    )
    return result("n", r"\frac{PV}{RT}", numeric, value, "mol")


def _ideal_temperature(params: dict[str, float]) -> PhysicsResult:
    positive(params, "pres", "volume", "moles")
    value = params["pres"] * params["volume"] / (params["moles"] * _GAS_CONSTANT)
    numeric = (
        rf"\frac{{{params['pres']:g}\cdot {params['volume']:g}}}"
        rf"{{{params['moles']:g}\cdot {_GAS_CONSTANT:.4f}}}"
    )
    return result("T", r"\frac{PV}{nR}", numeric, value, "K")


MATTER_SOLVERS = {
    "poiseuille_flow": _poiseuille,
    "gravitational_potential": _potential,
    "gravitational_potential_energy": _potential_energy,
    "orbital_energy": _orbital_energy,
    "kepler_period": _kepler,
    "monatomic_energy": _monatomic,
    "isobaric_work": _isobaric,
    "heavy_piston": _heavy_piston,
    "adiabatic_pressure": _adiabatic_pressure,
    "adiabatic_volume": _adiabatic_volume,
    "refrigerator_cop": _refrigerator,
    "heat_pump_cop": _heat_pump,
    "ideal_gas_volume": _ideal_volume,
    "ideal_gas_amount": _ideal_amount,
    "ideal_gas_temperature": _ideal_temperature,
}
