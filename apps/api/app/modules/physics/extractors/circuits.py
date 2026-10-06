"""Circuits: Ohm's law, power, charge flow, energy and resistor networks."""

from __future__ import annotations

import re
from typing import Literal

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.circuit_patterns import (
    _CHARGE_FLOW_RE,
    _CIRCUIT_CUE_RES,
    _CIRCUIT_CUES,
    _CIRCUIT_TIME_UNITS,
    _COULOMB_PATTERN,
    _ELECTRICAL_ENERGY_RE,
    _FARAD_PATTERN,
    _MAX_NETWORK_RESISTORS,
    _TERMINAL_ASK_RE,
    _VOLT_PATTERN,
    _WATT_PATTERN,
    _resistor_values,
)
from app.modules.physics.extractors.common import (
    _AMP_PATTERN,
    _LENGTH_UNIT_PATTERN,
    _OHM_PATTERN,
    _find_value_with_specific_unit,
    _ordered_values,
    _strip_param_assignments,
)
from app.modules.physics.extractors.cues import (
    _has_cue_either_case,
)
from app.modules.physics.extractors.fluid_readings import _AREA_PATTERN
from app.modules.physics.extractors.school_extensions import blocks_circuit
from app.services.text_match import has_equation


def _network_equivalent(values: list[float], *, series: bool) -> float | None:
    """Series sum, or the parallel reciprocal sum. Nonpositive parts decline."""
    if len(values) < 2 or any(value <= 0 for value in values):
        return None
    if series:
        return sum(values)
    return 1.0 / sum(1.0 / value for value in values)


def _extract_circuit_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    # The same check the pre-filter runs, so the two cannot disagree about
    # whether this question is a circuit question.
    if not _has_cue_either_case(cleaned, _CIRCUIT_CUES, _CIRCUIT_CUE_RES):
        return None
    if blocks_circuit(cleaned):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    volts = _ordered_values(cleaned, _VOLT_PATTERN)
    amps = _ordered_values(cleaned, _AMP_PATTERN)
    ohms = _ordered_values(cleaned, _OHM_PATTERN)
    farads = _ordered_values(cleaned, _FARAD_PATTERN)

    # --- parallel-plate capacitance: C = epsilon_0 A / d ----------------
    if "parallel plate" in lower:
        area = _find_value_with_specific_unit(cleaned, _AREA_PATTERN)
        spacing = _find_value_with_specific_unit(
            cleaned,
            _LENGTH_UNIT_PATTERN,
            ("separation", "spacing", "apart", "distance"),
            require_keyword=True,
        )
        if area is None or spacing is None:
            return None
        # A stated dielectric is C = κ ε0 A / d. The vacuum formula would drop κ.
        if "dielectric" in lower or "kappa" in lower:
            return None
        return PhysicsIntent(
            kind="circuit",
            physics_op="parallel_plate_capacitance",
            physics_params={"area": area[0], "d": spacing[0]},
            physics_units={"area": area[1] or "m^2", "d": spacing[1] or "m"},
            operation="solve",
        )

    # --- capacitor stored energy: U = C V^2 / 2 -------------------------
    if "capacitor" in lower and "energy" in lower:
        if len(farads) != 1 or len(volts) != 1:
            return None
        return PhysicsIntent(
            kind="circuit",
            physics_op="capacitor_energy",
            physics_params={"capacitance": farads[0][0], "V": volts[0][0]},
            physics_units={"capacitance": farads[0][1] or "F", "V": volts[0][1] or "V"},
            operation="solve",
        )

    # --- RC time constant: tau = RC -------------------------------------
    if "time constant" in lower or "rc circuit" in lower:
        if len(ohms) != 1 or len(farads) != 1:
            return None
        return PhysicsIntent(
            kind="circuit",
            physics_op="rc_time_constant",
            physics_params={"R": ohms[0][0], "capacitance": farads[0][0]},
            physics_units={"R": ohms[0][1] or "ohm", "capacitance": farads[0][1] or "F"},
            operation="solve",
        )

    # --- resistor networks: two or more resistances and a stated topology ---
    network = _resistor_values(cleaned)
    if len(network) >= 2 and ("series" in lower or "parallel" in lower):
        if len(network) > _MAX_NETWORK_RESISTORS:
            return None
        series = "series" in lower
        # "Find the current" with a supply voltage is Ohm's law on the
        # equivalent resistance. Answering the resistance sum is a different law.
        asks_current = re.search(r"\bcurrents?\b", lower) is not None
        asks_resistance = re.search(r"\bresistances?\b", lower) is not None
        if asks_current and not asks_resistance:
            equivalent = _network_equivalent(network, series=series)
            if len(volts) != 1 or amps or equivalent is None:
                return None
            return PhysicsIntent(
                kind="circuit",
                physics_op="current",
                physics_params={"V": volts[0][0], "R": equivalent},
                physics_units={"V": "volt", "R": "ohm"},
                operation="solve",
            )
        op: Literal[
            "voltage",
            "current",
            "resistance",
            "electrical_power",
            "series_resistance",
            "parallel_resistance",
        ] = "series_resistance" if series else "parallel_resistance"
        return PhysicsIntent(
            kind="circuit",
            physics_op=op,
            physics_params={f"R{n}": value for n, value in enumerate(network, start=1)},
            physics_units={f"R{n}": "ohm" for n in range(1, len(network) + 1)},
            operation="solve",
        )

    params: dict[str, float] = {}
    units: dict[str, str] = {}
    if volts:
        params["V"] = volts[0][0]
        units["V"] = "volt"
    if amps:
        params["I"] = amps[0][0]
        units["I"] = "ampere"
    if ohms:
        params["R"] = ohms[0][0]
        units["R"] = "ohm"

    # --- terminal voltage: V = emf - I r ---------------------------------
    # Only when the question says both that there *is* an internal resistance
    # and that the terminal value is what it wants. Without the second half
    # this is an ordinary Ohm's law question and belongs below - choosing
    # between the EMF and the terminal voltage on the reader's behalf is the
    # kind of guess a verified block must not make.
    if "internal resistance" in lower and _TERMINAL_ASK_RE.search(cleaned):
        r_internal = _find_value_with_specific_unit(
            cleaned, _OHM_PATTERN, ("internal",), require_keyword=True
        )
        if r_internal is None or not volts or not amps:
            return None
        return PhysicsIntent(
            kind="circuit",
            physics_op="terminal_voltage",
            physics_params={
                "E_emf": volts[0][0],
                "I": amps[0][0],
                "r_int": r_internal[0],
            },
            physics_units={"E_emf": "volt", "I": "ampere", "r_int": "ohm"},
            operation="solve",
        )

    # --- capacitance: C = Q / V ------------------------------------------
    # Stored energy from Q and V is not this capacitance. The energy branch
    # above already declined when C was not stated.
    if "capacit" in lower and "energy" not in lower:
        coulombs = _ordered_values(cleaned, _COULOMB_PATTERN)
        if not coulombs or not volts:
            return None
        return PhysicsIntent(
            kind="circuit",
            physics_op="capacitance",
            physics_params={"Q": coulombs[0][0], "V": volts[0][0]},
            physics_units={"Q": "coulomb", "V": "volt"},
            operation="solve",
        )

    # --- charge: Q = I t --------------------------------------------------
    if _CHARGE_FLOW_RE.search(cleaned):
        seconds = _find_value_with_specific_unit(cleaned, _CIRCUIT_TIME_UNITS)
        if not amps or seconds is None:
            return None
        return PhysicsIntent(
            kind="circuit",
            physics_op="charge",
            physics_params={"I": amps[0][0], "t": seconds[0]},
            physics_units={"I": "ampere", "t": seconds[1] or "s"},
            operation="solve",
        )

    # --- electrical energy: E = P t ---------------------------------------
    if _ELECTRICAL_ENERGY_RE.search(cleaned):
        watts = _find_value_with_specific_unit(cleaned, _WATT_PATTERN)
        seconds = _find_value_with_specific_unit(cleaned, _CIRCUIT_TIME_UNITS)
        if watts is None or seconds is None:
            return None
        return PhysicsIntent(
            kind="circuit",
            physics_op="electrical_energy",
            physics_params={"power": watts[0], "t": seconds[0]},
            physics_units={"power": watts[1] or "W", "t": seconds[1] or "s"},
            operation="solve",
        )

    # Electrical power needs electrical units present, which is what keeps it
    # from colliding with the mechanical `power` op (P = F v, in newtons and
    # m/s). Two different quantities that share a name and a unit.
    if "power" in lower or "dissipat" in lower or "watt" in lower:
        if len(params) < 2:
            return None
        return PhysicsIntent(
            kind="circuit",
            physics_op="electrical_power",
            physics_params=params,
            physics_units=units,
            operation="solve",
        )

    # V = I R: whichever of the three is absent is the one being asked for.
    # That reads the question from its givens rather than from its wording,
    # so all three rearrangements work without three sets of phrasings.
    if len(params) != 2:
        return None
    missing = ({"V", "I", "R"} - set(params)).pop()
    asked: Literal["voltage", "current", "resistance"] = {
        "V": "voltage",
        "I": "current",
        "R": "resistance",
    }[missing]  # type: ignore[assignment]
    return PhysicsIntent(
        kind="circuit",
        physics_op=asked,
        physics_params=params,
        physics_units=units,
        operation="solve",
    )
