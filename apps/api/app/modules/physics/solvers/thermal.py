"""Thermal solvers: Q = mc dT, Carnot and engine efficiency, entropy, conduction, expansion,
latent heat, the first law and PV = nRT.
"""

from __future__ import annotations

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.solvers.common import (
    _GAS_CONSTANT,
    PhysicsResult,
    QuantityResult,
    _latex_num,
    _params_in_si,
)
from app.services.solving import SolveServiceError


def _temperature_change(intent: PhysicsIntent, p: dict[str, float]) -> tuple[float, str | None]:
    """ΔT in kelvin, and the row that shows it when two readings were given."""
    if "temp_initial" not in p or "temp_final" not in p:
        return p["delta_temp"], None
    change = p["temp_final"] - p["temp_initial"]
    raw = intent.physics_params or {}
    units = intent.physics_units or {}
    same_scale = units.get("temp_initial") == units.get("temp_final")
    first = raw["temp_initial"] if same_scale else p["temp_initial"]
    second = raw["temp_final"] if same_scale else p["temp_final"]
    return change, rf"\Delta T = T_2 - T_1 = {second:g} - {first:g} = {change:g}"


def _heat_energy(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    """Q = mcΔT. Cooling releases heat: the answer is its size, marked released."""
    change, change_row = _temperature_change(intent, p)
    q_val = p["m"] * p["c_heat"] * change
    plugged = rf"{p['m']:g} \cdot {p['c_heat']:g} \cdot {_latex_num(change)}"
    rows = (change_row,) if change_row else ()
    return PhysicsResult(
        answer=rf"Q = mc\Delta T = {plugged} \approx {q_val:.2f} \text{{ J}}",
        formulas=(*rows, r"Q = mc\Delta T"),
        substitutions=(rf"Q = {plugged}",),
        quantities=(QuantityResult("", abs(q_val), "J", detail="released" if q_val < 0 else None),),
    )


def solve_thermal(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "carnot_efficiency":
        hot, cold = p["temp"], p["temp_env"]
        if hot <= 0 or cold < 0 or cold >= hot:
            raise SolveServiceError("Carnot efficiency needs 0 <= T_c < T_h in kelvin")
        value = 1 - cold / hot
        return PhysicsResult(
            answer=(
                rf"\eta_C = 1 - \frac{{T_C}}{{T_H}} = 1 - "
                rf"\frac{{{cold:g}}}{{{hot:g}}} \approx {value:.4g} "
                rf"({value * 100:.4g}\%)"
            ),
            formulas=(r"\eta_C = 1 - \frac{T_C}{T_H}",),
            substitutions=(rf"\eta_C = 1 - \frac{{{cold:g}}}{{{hot:g}}}",),
            quantities=(
                QuantityResult(
                    "",
                    value,
                    "",
                    detail=f"{value * 100:.4g}%",
                ),
            ),
        )

    if op == "entropy_change":
        if p["temp"] <= 0:
            raise SolveServiceError("entropy change needs a positive absolute temperature")
        value = p["heat"] / p["temp"]
        return PhysicsResult(
            answer=(
                rf"\Delta S = \frac{{Q_{{rev}}}}{{T}} = "
                rf"\frac{{{p['heat']:g}}}{{{p['temp']:g}}} "
                rf"\approx {value:.4g} \text{{ J/K}}"
            ),
            formulas=(r"\Delta S = \frac{Q_{rev}}{T}",),
            substitutions=(rf"\Delta S = \frac{{{p['heat']:g}}}{{{p['temp']:g}}}",),
            quantities=(QuantityResult("", value, "J/K"),),
        )

    if op == "heat_conduction_rate":
        if p["thermal_conductivity"] < 0 or p["area"] <= 0 or p["L"] <= 0:
            raise SolveServiceError("heat conduction needs positive area and thickness")
        value = p["thermal_conductivity"] * p["area"] * abs(p["delta_temp"]) / p["L"]
        return PhysicsResult(
            answer=(
                rf"\frac{{Q}}{{t}} = kA\frac{{\Delta T}}{{L}} = "
                rf"{p['thermal_conductivity']:g} \cdot {p['area']:g} \cdot "
                rf"\frac{{{abs(p['delta_temp']):g}}}{{{p['L']:g}}} "
                rf"\approx {value:.4g} \text{{ W}}"
            ),
            formulas=(r"\frac{Q}{t} = kA\frac{\Delta T}{L}",),
            substitutions=(
                rf"Q/t = {p['thermal_conductivity']:g} \cdot {p['area']:g} \cdot "
                rf"\frac{{{abs(p['delta_temp']):g}}}{{{p['L']:g}}}",
            ),
            quantities=(QuantityResult("", value, "W"),),
        )

    if op == "linear_expansion":
        if p["L0"] <= 0 or p["alpha"] < 0:
            raise SolveServiceError("linear expansion needs positive length and nonnegative alpha")
        expansion = p["alpha"] * p["L0"] * p["delta_temp"]
        return PhysicsResult(
            answer=(
                rf"\Delta L = \alpha L_0 \Delta T = {p['alpha']:g} \cdot "
                rf"{p['L0']:g} \cdot {p['delta_temp']:g} "
                rf"\approx {expansion:g} \text{{ m}}"
            ),
            formulas=(r"\Delta L = \alpha L_0 \Delta T",),
            substitutions=(
                rf"\Delta L = {p['alpha']:g} \cdot {p['L0']:g} \cdot {p['delta_temp']:g}",
            ),
            quantities=(QuantityResult("", expansion, "m"),),
        )

    if op == "latent_heat":
        if p["m"] < 0 or p["latent_heat"] < 0:
            raise SolveServiceError("latent heat needs nonnegative mass and specific latent heat")
        heat = p["m"] * p["latent_heat"]
        return PhysicsResult(
            answer=(
                rf"Q = mL = {p['m']:g} \cdot {p['latent_heat']:g} "
                rf"\approx {heat:g} \text{{ J}}"
            ),
            formulas=(r"Q = mL",),
            substitutions=(rf"Q = {p['m']:g} \cdot {p['latent_heat']:g}",),
            quantities=(QuantityResult("", heat, "J"),),
        )

    if op == "first_law_internal_energy":
        change = p["heat"] - p["W"]
        return PhysicsResult(
            answer=(
                rf"\Delta U = Q - W = {p['heat']:g} - {p['W']:g} "
                rf"\approx {change:g} \text{{ J}}"
            ),
            formulas=(r"\Delta U = Q - W",),
            substitutions=(rf"\Delta U = {p['heat']:g} - {p['W']:g}",),
            quantities=(QuantityResult("", change, "J"),),
        )

    if op == "heat_energy":
        return _heat_energy(intent, p)

    if op == "ideal_gas_pressure":
        volume = p["volume"]
        if volume <= 0:
            raise SolveServiceError("volume must be positive")
        if p["temp"] <= 0:
            raise SolveServiceError("an absolute temperature must be positive")
        pressure = p["moles"] * _GAS_CONSTANT * p["temp"] / volume
        return PhysicsResult(
            answer=(
                rf"P = \frac{{nRT}}{{V}} = \frac{{{p['moles']:g} \cdot {_GAS_CONSTANT:.4f} "
                rf"\cdot {p['temp']:g}}}{{{volume:g}}} \approx {pressure:.2f} \text{{ Pa}}"
            ),
            formulas=(r"P = \frac{nRT}{V}",),
            substitutions=(
                rf"P = \frac{{{p['moles']:g} \cdot {_GAS_CONSTANT:.4f} \cdot {p['temp']:g}}}"
                rf"{{{volume:g}}}",
            ),
            quantities=(QuantityResult("", pressure, "Pa"),),
        )

    if op == "thermal_efficiency":
        supplied = p["Q_in"]
        if supplied <= 0:
            raise SolveServiceError("the energy supplied must be positive")
        eta = p["W_out"] / supplied
        return PhysicsResult(
            answer=(
                rf"\eta = \frac{{W}}{{Q_{{in}}}} = \frac{{{p['W_out']:g}}}{{{supplied:g}}} "
                rf"\approx {eta:.2f} \; ({eta * 100:.1f}\%)"
            ),
            formulas=(r"\eta = \frac{W}{Q_{in}}",),
            substitutions=(rf"\eta = \frac{{{p['W_out']:g}}}{{{supplied:g}}}",),
            quantities=(
                QuantityResult(
                    "",
                    eta,
                    "",
                    detail=f"{eta * 100:.1f}%",
                ),
            ),
        )

    raise SolveServiceError(f"unsupported thermal op: {op}")
