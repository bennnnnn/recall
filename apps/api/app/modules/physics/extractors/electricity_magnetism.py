"""Circuit, electrostatics, and magnetism extractors."""

from __future__ import annotations

import re
from typing import Literal

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.common import (
    _ELEMENTARY_CHARGE,
    _LENGTH_UNIT_PATTERN,
    _VELOCITY_UNIT_PATTERN,
    _find_value_with_specific_unit,
    _has_cue_either_case,
    _ordered_values,
    _strip_param_assignments,
)
from app.modules.physics.extractors.matter_thermal import _AREA_PATTERN
from app.modules.physics.extractors.mechanics import _MASS_UNITS
from app.services.text_match import has_equation

_MAGNETISM_CUES = (
    "magnetic field",
    "magnetic flux",
    "solenoid",
    "flux density",
    "motional emf",
    "magnetic radius",
    "charged particle radius",
)

_TESLA_PATTERN = r"T|tesla|teslas|mT|millitesla"

_MAGNETISM_CUE_RES: tuple[re.Pattern[str], ...] = (
    # A tesla value beside a current or a charge is the signature itself.
    re.compile(
        rf"\d\s*(?:{_TESLA_PATTERN})(?![A-Za-z0-9]).{{0,80}}?"
        rf"\d\s*(?:A|amps?|amperes?|C|coulombs?)(?![A-Za-z0-9])"
    ),
    re.compile(
        rf"\d\s*(?:A|amps?|amperes?|C|coulombs?)(?![A-Za-z0-9]).{{0,80}}?"
        rf"\d\s*(?:{_TESLA_PATTERN})(?![A-Za-z0-9])"
    ),
)


def _extract_magnetism_intent(cleaned: str) -> PhysicsIntent | None:
    # The tesla signature is case-sensitive (a bare lowercase t is a tonne), so
    # this gate reads the original casing the way the pre-filter now does.
    if not _has_cue_either_case(cleaned, _MAGNETISM_CUES, _MAGNETISM_CUE_RES):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    lower = cleaned.lower()
    field = _find_value_with_specific_unit(cleaned, _TESLA_PATTERN)
    current = _find_value_with_specific_unit(cleaned, _AMP_PATTERN)
    charge = _find_value_with_specific_unit(cleaned, _COULOMB_PATTERN)
    speed = _find_value_with_specific_unit(cleaned, _VELOCITY_UNIT_PATTERN)
    mass = _find_value_with_specific_unit(cleaned, _MASS_UNITS, ("mass", "particle"))
    length = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("wire", "conductor", "long", "length")
    )
    area = _find_value_with_specific_unit(cleaned, _AREA_PATTERN)
    radius = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("distance", "from", "radius"), require_keyword=True
    )

    if charge is None and re.search(r"\b(?:proton|electron)\b", cleaned, re.IGNORECASE):
        # Magnetic force here is a magnitude; the sign distinguishes the
        # direction, which this scalar template intentionally does not infer.
        charge = (_ELEMENTARY_CHARGE, "C")

    # Field around a long straight wire: B = mu0 I / (2 pi r).
    if field is None and "magnetic field" in lower and current is not None and radius is not None:
        if not any(word in lower for word in ("straight wire", "long wire", "from a wire")):
            return None
        return PhysicsIntent(
            kind="magnetism",
            physics_op="magnetic_field_wire",
            physics_params={"I": current[0], "r": radius[0]},
            physics_units={"I": current[1] or "A", "r": radius[1] or "m"},
            operation="solve",
        )

    if field is None:
        return None

    # Radius of a charged particle's circular path in a perpendicular field.
    if "radius" in lower and charge is not None and speed is not None and mass is not None:
        return PhysicsIntent(
            kind="magnetism",
            physics_op="charged_particle_radius",
            physics_params={
                "m": mass[0],
                "v": speed[0],
                "Q": abs(charge[0]),
                "b_field": field[0],
            },
            physics_units={
                "m": mass[1] or "kg",
                "v": speed[1] or "m/s",
                "Q": charge[1] or "C",
                "b_field": field[1] or "T",
            },
            operation="solve",
        )

    # Motional emf for perpendicular field, rod, and motion.
    if "emf" in lower and speed is not None and length is not None:
        if "perpendicular" not in lower:
            return None
        return PhysicsIntent(
            kind="magnetism",
            physics_op="motional_emf",
            physics_params={"b_field": field[0], "wire_L": length[0], "v": speed[0]},
            physics_units={
                "b_field": field[1] or "T",
                "wire_L": length[1] or "m",
                "v": speed[1] or "m/s",
            },
            operation="solve",
        )

    # F = q v B, checked before F = B I L: a moving charge names both.
    if charge is not None and speed is not None:
        return PhysicsIntent(
            kind="magnetism",
            physics_op="magnetic_force_charge",
            physics_params={"Q": charge[0], "v": speed[0], "b_field": field[0]},
            physics_units={
                "Q": charge[1] or "C",
                "v": speed[1] or "m/s",
                "b_field": field[1] or "T",
            },
            operation="solve",
        )

    if current is not None and length is not None:
        return PhysicsIntent(
            kind="magnetism",
            physics_op="magnetic_force_wire",
            physics_params={"I": current[0], "wire_L": length[0], "b_field": field[0]},
            physics_units={
                "I": current[1] or "A",
                "wire_L": length[1] or "m",
                "b_field": field[1] or "T",
            },
            operation="solve",
        )

    if area is not None:
        return PhysicsIntent(
            kind="magnetism",
            physics_op="magnetic_flux",
            physics_params={"area": area[0], "b_field": field[0]},
            physics_units={"area": area[1] or "m^2", "b_field": field[1] or "T"},
            operation="solve",
        )
    return None


_CIRCUIT_CUES = (
    "ohm",
    "voltage",
    "volts",
    "resistor",
    "resistance",
    "ampere",
    "amps",
    "circuit",
    "battery",
    # Round 3. Each of these is electrical vocabulary and nothing else -
    # unlike "charge" (a card is charged) and "current" (the current date),
    # which stay out and are reached by co-occurrence below.
    "capacitance",
    "capacitor",
    "farad",
    "coulomb",
    "internal resistance",
    "terminal voltage",
    "electromotive force",
    "time constant",
    "parallel plate",
)

_VOLT_PATTERN = r"V|volts?"

_AMP_PATTERN = r"A|amps?|amperes?"

_OHM_PATTERN = r"ohms?|\u03a9"

_VOLT_CUE = r"V|[Vv]olts?"

_AMP_CUE = r"A|[Aa]mp(?:s|ere|eres)?"

_OHM_CUE = r"[Oo]hms?|\u03a9"


def _circuit_pair(first: str, second: str) -> re.Pattern[str]:
    """A number in `first`'s unit within 80 chars of a number in `second`'s.

    No IGNORECASE: the bare letters below are the SI symbols, and the spelled
    out forms carry their own case classes. `_has_cue_either_case` is what
    makes this reachable from the pre-filter.
    """
    return re.compile(rf"\d\s*(?:{first})(?![A-Za-z0-9]).{{0,80}}?\d\s*(?:{second})(?![A-Za-z0-9])")


_CHARGE_FLOW_RE = re.compile(
    rf"\bcharge\b.{{0,60}}?\d\s*(?:{_AMP_PATTERN})(?![A-Za-z0-9])"
    rf"|\d\s*(?:{_AMP_PATTERN})(?![A-Za-z0-9]).{{0,60}}?\bcharge\b",
    re.IGNORECASE,
)

_WATT_PATTERN = r"W|watts?|kW|kilowatts?"

_ELECTRICAL_ENERGY_RE = re.compile(
    rf"\b(?:energy|consumes?|consumed|uses?|used|costs?)\b.{{0,80}}?"
    rf"\d\s*(?:{_WATT_PATTERN})(?![A-Za-z0-9])"
    rf"|\d\s*(?:{_WATT_PATTERN})(?![A-Za-z0-9]).{{0,80}}?"
    rf"\b(?:energy|consumes?|consumed|uses?|used|costs?)\b",
    re.IGNORECASE,
)

_COULOMB_PATTERN = r"uC|µC|C|microcoulombs?|coulombs?"

_FARAD_PATTERN = r"mF|uF|µF|nF|pF|F|farads?|microfarads?|nanofarads?|picofarads?"

_CIRCUIT_TIME_UNITS = r"seconds?|secs?|sec|s|minutes?|mins?|min|hours?|hrs?|hr|h"

_TERMINAL_ASK_RE = re.compile(
    r"\bterminal\b|\bacross the terminals\b|\blost volts\b|\bp\.?d\.? across\b",
    re.IGNORECASE,
)

_CIRCUIT_CUE_RES: tuple[re.Pattern[str], ...] = (
    _circuit_pair(_VOLT_CUE, rf"{_AMP_CUE}|{_OHM_CUE}"),
    _circuit_pair(rf"{_AMP_CUE}|{_OHM_CUE}", _VOLT_CUE),
    _circuit_pair(_AMP_CUE, _OHM_CUE),
    _circuit_pair(_OHM_CUE, _AMP_CUE),
    _CHARGE_FLOW_RE,
    _ELECTRICAL_ENERGY_RE,
)

_RESISTOR_LIST_RE = re.compile(
    r"(\d+(?:\.\d+)?(?:\s*(?:,|and)\s*\d+(?:\.\d+)?)+)\s*(?:ohms?|\u03a9)",
    re.IGNORECASE,
)

_MAX_NETWORK_RESISTORS = 4


def _resistor_values(text: str) -> list[float]:
    """Every resistance in a network, however the units are distributed."""
    listed = _RESISTOR_LIST_RE.search(text)
    if listed is not None:
        return [float(n) for n in re.findall(r"\d+(?:\.\d+)?", listed.group(1))]
    return [value for value, _ in _ordered_values(text, _OHM_PATTERN)]


def _extract_circuit_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    # The same check the pre-filter runs, so the two cannot disagree about
    # whether this question is a circuit question.
    if not _has_cue_either_case(cleaned, _CIRCUIT_CUES, _CIRCUIT_CUE_RES):
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
        op: Literal[
            "voltage",
            "current",
            "resistance",
            "electrical_power",
            "series_resistance",
            "parallel_resistance",
        ] = "series_resistance" if "series" in lower else "parallel_resistance"
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
    if "capacit" in lower:
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


_ELECTROSTATICS_CUES = (
    "electrostatic",
    "electric force",
    "coulomb force",
    "coulomb's law",
    "coulomb law",
    "point charge",
    "electric field",
    "electric potential",
    "electric potential energy",
)

_TWO_CHARGES_RE = re.compile(r"\btwo\s+(?:point\s+)?charges?\b", re.IGNORECASE)

_ELECTROSTATICS_CUE_RES: tuple[re.Pattern[str], ...] = (_TWO_CHARGES_RE,)


def _extract_electrostatics_intent(cleaned: str) -> PhysicsIntent | None:
    if not _has_cue_either_case(cleaned, _ELECTROSTATICS_CUES, _ELECTROSTATICS_CUE_RES):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None
    lower = cleaned.lower()
    charges = _ordered_values(cleaned, _COULOMB_PATTERN)
    if len(charges) == 1 and "each" in lower and _TWO_CHARGES_RE.search(cleaned):
        charges = [charges[0], charges[0]]
    separation = _find_value_with_specific_unit(
        cleaned,
        _LENGTH_UNIT_PATTERN,
        ("separated", "separation", "apart", "distance", "from"),
        require_keyword=True,
    )
    if separation is None or separation[0] <= 0:
        return None

    if "potential energy" in lower:
        if len(charges) != 2:
            return None
        return PhysicsIntent(
            kind="magnetism",
            physics_op="electric_potential_energy",
            physics_params={"q1": charges[0][0], "q2": charges[1][0], "r": separation[0]},
            physics_units={
                "q1": charges[0][1] or "C",
                "q2": charges[1][1] or "C",
                "r": separation[1] or "m",
            },
            operation="solve",
        )

    if "electric field" in lower:
        if len(charges) != 1:
            return None
        return PhysicsIntent(
            kind="magnetism",
            physics_op="electric_field",
            physics_params={"Q": charges[0][0], "r": separation[0]},
            physics_units={"Q": charges[0][1] or "C", "r": separation[1] or "m"},
            operation="solve",
        )

    if "electric potential" in lower:
        if len(charges) != 1:
            return None
        return PhysicsIntent(
            kind="magnetism",
            physics_op="electric_potential",
            physics_params={"Q": charges[0][0], "r": separation[0]},
            physics_units={"Q": charges[0][1] or "C", "r": separation[1] or "m"},
            operation="solve",
        )

    if ("force" not in lower and "coulomb" not in lower) or len(charges) != 2:
        return None

    return PhysicsIntent(
        kind="magnetism",
        physics_op="electric_force",
        physics_params={"q1": charges[0][0], "q2": charges[1][0], "r": separation[0]},
        physics_units={
            "q1": charges[0][1] or "C",
            "q2": charges[1][1] or "C",
            "r": separation[1] or "m",
        },
        operation="solve",
    )
