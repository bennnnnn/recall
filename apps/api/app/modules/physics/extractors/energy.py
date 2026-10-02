"""Energy extractors: kinetic, potential, work, power and conservation."""

from __future__ import annotations

import re
from typing import Literal

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.angles import (
    _stated_angle,
)
from app.modules.physics.extractors.common import (
    _NUMBER,
    _VELOCITY_UNIT_PATTERN,
    _detect_gravity,
    _find_value_with_specific_unit,
    _has_cue_either_case,
    _ordered_values,
    _strip_param_assignments,
)
from app.services.text_match import has_equation

_ENERGY_CUES = (
    "kinetic energy",
    "potential energy",
    "work done",
    "work is done",
    "how much work",
    "work of",
    "what is the power",
    "what is its power",
    "what's the power",
    "what's its power",
    "energy of",
    "what power",
    "how much power",
    "find the power",
    "find its power",
    "calculate the power",
    "power needed",
    "power required",
    "power is needed",
    "mechanical efficiency",
    "machine efficiency",
    "efficiency of a machine",
    "net work",
    "work-energy",
    "work energy",
    "conservation of energy",
    "mechanical energy",
    "energy is conserved",
)

_KE_ABBREV_RE = re.compile(r"\bk\.?\s?e\.?\s+of\b")

_PE_ABBREV_RE = re.compile(r"\bp\.?\s?e\.?\s+of\b")

# ``power`` is also ordinary exponent language. Route it to physics only when
# the request contains a complete input pair for one of the supported laws:
# P = W/t or P = Fv. This handles arbitrary subjects (motor, student, animal)
# without maintaining a noun allowlist or stealing "the third power of 5".
_SOLVABLE_POWER_DATA_RE = re.compile(
    rf"(?is)\A(?=.*\bpower\b)(?:"
    rf"(?=.*{_NUMBER}\s*(?:kilojoules?|joules?|kJ|J)\b)"
    rf"(?=.*{_NUMBER}\s*(?:milliseconds?|ms|seconds?|secs?|sec|s|"
    r"minutes?|mins?|min|hours?|hrs?|hr|h)\b)"
    rf"|(?=.*{_NUMBER}\s*N\b)(?=.*{_NUMBER}\s*(?:{_VELOCITY_UNIT_PATTERN})\b))"
)

_ENERGY_CUE_RES: tuple[re.Pattern[str], ...] = (
    _KE_ABBREV_RE,
    _PE_ABBREV_RE,
    _SOLVABLE_POWER_DATA_RE,
)


def _unstated_work_angle(text: str) -> bool:
    """An angle is mentioned, but no number was given to put in cos θ."""
    has_words = re.search(r"\bat an angle\b", text, re.IGNORECASE) is not None
    return has_words and _stated_angle(text) is None


def _extract_energy_intent(cleaned: str) -> PhysicsIntent | None:
    from app.modules.physics.extractors.energy_conservation import (
        extract_closed_energy,
        is_closed_energy_request,
    )

    lower = cleaned.lower()
    if not _has_cue_either_case(cleaned, _ENERGY_CUES, _ENERGY_CUE_RES):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None
    closed = extract_closed_energy(cleaned)
    if closed is not None:
        return closed
    if is_closed_energy_request(lower):
        return None

    # A machine's useful energy output divided by its energy input. Thermal
    # engines retain their own W/Q_in operation in the earlier thermal
    # extractor; this branch owns explicitly mechanical/machine wording.
    if "efficiency" in lower:
        if not any(word in lower for word in ("machine", "mechanical", "device", "motor")):
            return None
        energies = _ordered_values(cleaned, r"kilojoules?|joules?|kJ|J")
        if len(energies) != 2:
            return None
        output_match = re.search(
            rf"(?:output|outputs|useful(?:\s+energy)?)\D{{0,24}}?({_NUMBER})\s*"
            r"(kilojoules?|joules?|kJ|J)",
            cleaned,
            re.IGNORECASE,
        )
        input_match = re.search(
            rf"(?:input|supplied|receives?|takes?\s+in)\D{{0,24}}?({_NUMBER})\s*"
            r"(kilojoules?|joules?|kJ|J)",
            cleaned,
            re.IGNORECASE,
        )
        output_reverse = re.search(
            rf"({_NUMBER})\s*(kilojoules?|joules?|kJ|J)\s*(?:output|useful)",
            cleaned,
            re.IGNORECASE,
        )
        input_reverse = re.search(
            rf"({_NUMBER})\s*(kilojoules?|joules?|kJ|J)\s*(?:input|supplied)",
            cleaned,
            re.IGNORECASE,
        )

        def _labelled_energy(
            forward: re.Match[str] | None, reverse: re.Match[str] | None
        ) -> tuple[float, str] | None:
            match = forward or reverse
            return None if match is None else (float(match.group(1)), match.group(2))

        output = _labelled_energy(output_match, output_reverse)
        supplied = _labelled_energy(input_match, input_reverse)
        if output is None or supplied is None:
            # Numeric order alone is not a safe way to infer input vs output.
            return None
        return PhysicsIntent(
            kind="energy",
            physics_op="mechanical_efficiency",
            physics_params={"E_out": output[0], "E_in": supplied[0]},
            physics_units={"E_out": output[1] or "J", "E_in": supplied[1] or "J"},
            operation="solve",
        )

    # Mass (m) — use unit-specific search so force isn't picked up as mass.
    mass: float | None = None
    mass_unit = "kg"
    mu = _find_value_with_specific_unit(
        cleaned,
        r"kg|g|mg|lb|lbs|oz",
        ("mass", "object", "body"),
    )
    if mu is not None:
        mass, mass_unit = mu

    # Velocity (v) — for KE = 1/2 m v^2
    velocity: float | None = None
    vel_unit = "m/s"
    vu = _find_value_with_specific_unit(
        cleaned,
        r"m/s|km/h|mph|cm/s|mm/s",
        ("velocity", "speed", "moving", "traveling", "travelling"),
    )
    if vu is not None:
        velocity, vel_unit = vu

    # Height (h) — for PE = m g h. Use length-specific search.
    height: float | None = None
    height_unit = "m"
    hu = _find_value_with_specific_unit(
        cleaned,
        r"km|cm|mm|m|ft|yd|in|mi",
        ("height", "high", "above"),
    )
    if hu is not None:
        height, height_unit = hu

    # Force (F) — for W = F d
    force: float | None = None
    force_unit = "N"
    fu = _find_value_with_specific_unit(cleaned, r"\bN\b", ("force",))
    if fu is not None:
        force, force_unit = fu

    # Distance (d) — for W = F d. Use length-specific search.
    distance: float | None = None
    dist_unit = "m"
    du = _find_value_with_specific_unit(
        cleaned,
        r"km|cm|mm|m|ft|yd|in|mi",
        ("distance", "over", "through"),
    )
    if du is not None:
        distance, dist_unit = du

    # Energy done (W, in joules) and elapsed time — for P = W / t.
    work_done: float | None = None
    work_unit = "J"
    wu = _find_value_with_specific_unit(cleaned, r"kilojoules?|joules?|kJ|J", ("work", "energy"))
    if wu is not None:
        work_done, work_unit = wu

    elapsed: float | None = None
    elapsed_unit = "s"
    tu = _find_value_with_specific_unit(
        cleaned,
        r"milliseconds?|ms|seconds?|secs?|sec|s|minutes?|mins?|min|hours?|hrs?|hr|h",
    )
    if tu is not None:
        elapsed, elapsed_unit = tu

    # Decide the operation. Power is checked before work because a question
    # naming both ("what power does 100 J of work in 5 s need") is asking for
    # the power; "work done by a 10 N force" names only work and is unaffected.
    op: Literal["kinetic_energy", "potential_energy", "work", "power"]
    if "kinetic energy" in lower or _KE_ABBREV_RE.search(lower):
        op = "kinetic_energy"
        if mass is None or velocity is None:
            return None
    elif "potential energy" in lower or _PE_ABBREV_RE.search(lower):
        op = "potential_energy"
        if mass is None or height is None:
            return None
    elif "power" in lower:
        op = "power"
        if _unstated_work_angle(cleaned):
            return None
        # Either school form: P = F v, or P = W / t.
        if (force is None or velocity is None) and (work_done is None or elapsed is None):
            return None
        # An angle belongs to F v cos θ, not to work divided by time.
        if _stated_angle(cleaned) is not None and (force is None or velocity is None):
            return None
    elif "work" in lower:
        if _unstated_work_angle(cleaned):
            return None
        op = "work"
        if force is None or distance is None:
            return None
    else:
        # "energy of" / "conservation of energy" — pick whichever we can solve.
        if mass is not None and velocity is not None:
            op = "kinetic_energy"
        elif mass is not None and height is not None:
            op = "potential_energy"
        elif force is not None and distance is not None:
            if _unstated_work_angle(cleaned):
                return None
            op = "work"
        else:
            return None

    params: dict[str, float] = {}
    units: dict[str, str] = {}
    if op in ("kinetic_energy", "potential_energy") and mass is not None:
        params["m"] = mass
        units["m"] = mass_unit or "kg"
    if op in ("kinetic_energy", "power") and velocity is not None:
        params["v"] = velocity
        units["v"] = vel_unit or "m/s"
    if op == "potential_energy" and height is not None:
        params["h"] = height
        units["h"] = height_unit or "m"
    if op == "power" and (force is None or velocity is None):
        # P = W / t. Drop any partial F/v so solve_energy picks this form.
        params.pop("v", None)
        units.pop("v", None)
        if work_done is not None and elapsed is not None:
            params["W"] = work_done
            units["W"] = work_unit or "J"
            params["t"] = elapsed
            units["t"] = elapsed_unit or "s"
    elif op in ("work", "power") and force is not None:
        params["F"] = force
        units["F"] = force_unit or "N"
    if op == "work" and distance is not None:
        params["d"] = distance
        units["d"] = dist_unit or "m"
    if op in ("work", "power"):
        angle = _stated_angle(cleaned)
        if angle is not None and "F" in params:
            params["angle"] = angle[0]
            units["angle"] = angle[1]
    if op == "potential_energy":
        params["g"] = _detect_gravity(cleaned)
        units["g"] = "m/s^2"

    return PhysicsIntent(
        kind="energy",
        physics_op=op,
        physics_params=params,
        physics_units=units,
        operation="solve",
    )
