"""Solver-owned formula and substitution rows.

The direct reply reads these fields. It does not split a combined equation chain.
"""

from __future__ import annotations

import re
from dataclasses import replace

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.catalog import CATALOG
from app.modules.physics.solvers.common import PhysicsResult

# Operations that solve for whichever one of these quantities was left out.
_ONE_UNKNOWN: dict[str, tuple[tuple[str, str], ...]] = {
    "work_energy": (("W", "W_{net}"), ("m", "m"), ("v1", "v_1"), ("v2", "v_2")),
    "mechanical_energy_gravity": (("v1", "v_1"), ("h1", "h_1"), ("v2", "v_2"), ("h2", "h_2")),
    "mechanical_energy_spring": (("v1", "v_1"), ("x1", "x_1"), ("v2", "v_2"), ("x2", "x_2")),
    "torque_inertia": (("tau", r"\tau"), ("inertia", "I"), ("ang_alpha", r"\alpha")),
    "torque_angular_impulse": (
        ("tau", r"\tau"),
        ("L_i", "L_i"),
        ("L_f", "L_f"),
        ("t", r"\Delta t"),
    ),
    "angular_momentum_conservation": (
        ("inertia_i", "I_i"),
        ("omega_i", r"\omega_i"),
        ("inertia_f", "I_f"),
        ("omega_f", r"\omega_f"),
    ),
    "rolling_speed": (("v", "v"), ("omega", r"\omega"), ("r", "R")),
    "rolling_acceleration": (("a", "a"), ("ang_alpha", r"\alpha"), ("r", "R")),
    "parallel_axis": (("inertia", "I"), ("inertia_cm", "I_{cm}"), ("m", "M"), ("d", "d")),
}

_RESULT_SYMBOLS = {spec.id: spec.result_symbol for spec in CATALOG.values()}
_DECIMAL_VALUE = re.compile(r"(?<![\d.])([+-]?\d+\.\d+)(?![\d.])")


def display_number(value: float) -> str:
    magnitude = abs(value)
    if magnitude and (magnitude >= 1e6 or magnitude < 1e-4):
        return f"{value:.6g}"
    return str(int(value)) if value.is_integer() else f"{value:g}"


def given_unit_suffix(unit: str | None) -> str:
    if not unit:
        return ""
    if unit.lower() in {"deg", "degree", "degrees", "°"}:
        return r"^\circ"
    return rf"\,\mathrm{{{unit}}}"


def _visible_equation(equation: str) -> str:
    equation = _DECIMAL_VALUE.sub(lambda match: match.group(1).rstrip("0").rstrip("."), equation)
    return equation.replace("*", "·")


def _missing_result_symbol(operation: str, params: dict[str, float]) -> str | None:
    slots = _ONE_UNKNOWN.get(operation)
    if slots is None:
        return None
    missing = [symbol for key, symbol in slots if key not in params]
    if len(missing) == 1:
        return missing[0]
    return None


def result_symbol_for(intent: PhysicsIntent) -> str | None:
    """The quantity the solver derived, not merely its shared operation."""
    params = intent.physics_params or {}
    if intent.kind == "force" and intent.physics_op == "net_force":
        missing = [symbol for symbol in ("F", "m", "a") if symbol not in params]
        if len(missing) == 1:
            return missing[0]
    if intent.kind == "torque" and intent.physics_op == "moment_balance" and "d2" in params:
        return "F_2"
    if intent.physics_op == "final_velocity" and params.get("elastic") == 1.0:
        return r"v_1',\ v_2'"
    chosen = _missing_result_symbol(intent.physics_op or "", params)
    if chosen is not None:
        return chosen
    if intent.kind == "kinematics" and intent.physics_op == "speed" and "t" not in params:
        return "v_{impact}"
    return _RESULT_SYMBOLS.get(intent.physics_op or "")


def remember_equation_chain(
    working: str,
    *,
    result_symbol: str | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Record the symbolic formula and the numeric substitution the solver wrote.

    Solvers that already pass ``formulas`` and ``substitutions`` do not come
    through here. This reads a chain only when a solver still emitted one
    combined prompt line and did not store the two parts itself.
    """
    chains = [chain.strip() for chain in working.split(r", \quad ")]
    formulas: list[str] = []
    substitutions: list[str] = []
    for chain in chains:
        parts = chain.split(" = ")
        lhs = result_symbol if len(chains) == 1 and result_symbol else parts[0].strip()
        arrow_rearrangement = len(parts) >= 3 and r"\Rightarrow" in parts[1]
        if arrow_rearrangement:
            formulas.append(f"{lhs} = {parts[2].split(r'\approx', 1)[0].strip()}")
        elif len(parts) >= 2:
            formula_rhs = parts[1].split(r"\approx", 1)[0].strip()
            formulas.append(f"{parts[0].strip()} = {formula_rhs}")
        else:
            formulas.append(chain)

        if len(parts) >= 3:
            substitution_rhs = parts[-1].split(r"\approx", 1)[0].strip()
            substitutions.append(f"{lhs} = {substitution_rhs}")
        else:
            substitutions.append(chain.split(r"\approx", 1)[0].strip())
    return (
        tuple(_visible_equation(formula) for formula in formulas),
        tuple(_visible_equation(substitution) for substitution in substitutions),
    )


def attach_recorded_working(result: PhysicsResult, intent: PhysicsIntent) -> PhysicsResult:
    """Fill any formula or substitution the solver did not store itself."""
    if result.formulas and result.substitutions:
        formulas, substitutions = result.formulas, result.substitutions
    else:
        remembered_formulas, remembered_substitutions = remember_equation_chain(
            result.answer, result_symbol=result_symbol_for(intent)
        )
        formulas = result.formulas or remembered_formulas
        substitutions = result.substitutions or remembered_substitutions
    return replace(
        result,
        formulas=tuple(_visible_equation(item) for item in formulas),
        substitutions=tuple(_visible_equation(item) for item in substitutions),
    )
