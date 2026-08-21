"""Physics extractors for kinematics / projectile / force / energy intents.

These run *before* the generic equation extractor so a phrase like
"A ball is dropped from 20m, how long until it hits the ground?" is
recognized as a kinematics problem (verified solve + trajectory graph)
instead of falling through to "solve 20 = 0".
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Literal

from app.models.math_schemas import MathIntent
from app.services import math_text_match as mtm

logger = logging.getLogger(__name__)

# Default gravitational acceleration (m/s^2). Earth gravity unless the user
# says otherwise ("on the moon", "g = 1.6").
_G_DEFAULT = 9.81

# Regex helpers --------------------------------------------------------------
# A number with optional decimal, possibly negative.
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")

# A number followed by an optional unit word. Captures the numeric value and
# the trailing unit (m, cm, km, ft, mi, m/s, m/s^2, kg, g, N, J, W, ...).
# The unit is matched loosely — we validate via Pint in the solver.
_VALUE_UNIT_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*"
    r"(m/s\^?2|m/s|m\^?2/s\^?2|km/h|mph|m/s2|cm/s|mm/s|"
    r"km|cm|mm|m|mi|ft|yd|in|"
    r"kg|g|mg|lb|lbs|oz|"
    r"N|J|W|Pa|Hz|"
    r"s|ms|sec|min|hr|h|"
    r"deg|degrees|°|rad|radians)?",
    re.IGNORECASE,
)


def _find_value_with_unit(text: str, keywords: tuple[str, ...]) -> tuple[float, str] | None:
    """Find the first number near a keyword (e.g. "height of 20m", "20m high").

    Returns (value, unit) where unit is "" if no unit was found. The unit is
    not validated here — the solver runs it through Pint.
    """
    lower = text.lower()
    for kw in keywords:
        idx = lower.find(kw)
        if idx == -1:
            continue
        # Search a window after the keyword for a number (the common case:
        # "height of 20m", "velocity 15 m/s"). Also search a small window
        # *before* the keyword ("20m high", "15 m/s initial velocity").
        after = text[idx + len(kw) : idx + len(kw) + 40]
        m = _VALUE_UNIT_RE.match(after.strip())
        if m:
            val = float(m.group(1))
            unit = (m.group(2) or "").strip()
            return val, unit
        before = text[max(0, idx - 40) : idx]
        m = _VALUE_UNIT_RE.search(before)
        if m:
            val = float(m.group(1))
            unit = (m.group(2) or "").strip()
            return val, unit
    return None


def _find_value_with_specific_unit(
    text: str, unit_pattern: str, keywords: tuple[str, ...] = ()
) -> tuple[float, str] | None:
    """Find a number followed by a specific unit (e.g. "20 N", "5 kg").

    When keywords are present in the text, prefer the unit-bearing value
    nearest one of them; otherwise use the first matching value. This avoids
    binding an earlier unrelated quantity to the requested mass/force/etc.
    """
    matches = list(
        re.finditer(
            rf"(-?\d+(?:\.\d+)?)\s*({unit_pattern})(?![A-Za-z0-9/^])",
            text,
            re.IGNORECASE,
        )
    )
    if not matches:
        return None

    match = matches[0]
    if keywords:
        lower = text.lower()
        keyword_spans: list[tuple[int, int]] = []
        for keyword in keywords:
            start = 0
            while (idx := lower.find(keyword.lower(), start)) != -1:
                keyword_spans.append((idx, idx + len(keyword)))
                start = idx + len(keyword)
        if keyword_spans:

            def distance_to_keyword(candidate: re.Match[str]) -> int:
                distances: list[int] = []
                for start, end in keyword_spans:
                    if candidate.end() <= start:
                        distances.append(start - candidate.end())
                    elif end <= candidate.start():
                        distances.append(candidate.start() - end)
                    else:
                        distances.append(0)
                return min(distances)

            match = min(matches, key=distance_to_keyword)

    return float(match.group(1)), match.group(2)


def _find_all_numbers(text: str) -> list[float]:
    """All numbers in the text (in order). Used when keyword search fails."""
    return [float(m.group(0)) for m in _NUM_RE.finditer(text)]


def _detect_gravity(text: str) -> float:
    """If the user named a gravity value, use it; else default 9.81 m/s^2."""
    lower = text.lower()
    # "g = 1.6", "gravity = 1.62", "g = 1.6 m/s^2"
    m = re.search(r"\bg\s*=\s*(-?\d+(?:\.\d+)?)", lower)
    if m:
        return float(m.group(1))
    m = re.search(r"\bgravity\s*(?:of|is|=)?\s*(-?\d+(?:\.\d+)?)", lower)
    if m:
        return float(m.group(1))
    if "moon" in lower:
        return 1.62
    if "mars" in lower:
        return 3.71
    return _G_DEFAULT


def _strip_param_assignments(text: str) -> str:
    """Remove "g = 1.6", "gravity = 9.8" style parameter specs so has_equation
    doesn't mistake them for equations to solve (the physics solver handles
    these as knowns, not as algebra).
    """
    return re.sub(
        r"\b(?:g|gravity)\s*=\s*-?\d+(?:\.\d+)?(?:\s*m/s\^?2)?",
        "",
        text,
        flags=re.IGNORECASE,
    )


# ---------------------------------------------------------------------------
# Kinematics: 1D motion under gravity (free fall, dropped, thrown up/down)
# ---------------------------------------------------------------------------

_KINEMATICS_CUES = (
    "dropped",
    "free fall",
    "freefall",
    "falls from",
    "fall from",
    "thrown upward",
    "thrown upward",
    "thrown down",
    "thrown downward",
    "launched upward",
    "launched downward",
    "how long until",
    "how long to hit",
    "how long to reach",
    "how long to fall",
    "time to hit",
    "time to reach",
    "velocity after",
    "speed after",
    "height after",
    "position after",
    "acceleration of",
)


def _extract_kinematics_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    # Must have a kinematics cue AND at least one number.
    if not any(cue in lower for cue in _KINEMATICS_CUES):
        return None
    # Defer to the equation extractor if there's an explicit "=" equation —
    # but strip "g = 1.6" parameter specs first (those are knowns, not algebra).
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    # Initial height (h0): "from 20m", "height of 20m", "20m high", "dropped from 20m"
    h0: float | None = None
    h0_unit = "m"
    hu = _find_value_with_unit(
        cleaned,
        ("from", "initial height", "height of", "high", "above", "cliff"),
    )
    if hu is not None:
        h0, h0_unit = hu

    # Initial velocity (v0): "thrown upward at 15 m/s", "velocity of 15 m/s", "at 15 m/s"
    v0: float = 0.0
    v0_unit = "m/s"
    vu = _find_value_with_unit(
        cleaned, ("velocity of", "velocity", "speed of", "speed", "at", "with", "initial")
    )
    if vu is not None:
        v0, v0_unit = vu

    # If we found no height and no nonzero velocity, this isn't a solvable
    # kinematics problem — let the next extractor try.
    if h0 is None and v0 == 0.0:
        return None

    # Decide what the user is asking for.
    op: Literal["position", "velocity", "acceleration", "time_to_ground"] = "time_to_ground"
    if "velocity after" in lower or "speed after" in lower:
        op = "velocity"
    elif "height after" in lower or "position after" in lower:
        op = "position"
    elif "acceleration" in lower:
        op = "acceleration"

    time_value: float | None = None
    time_unit = "s"
    if op in ("position", "velocity"):
        time_match = _find_value_with_specific_unit(
            cleaned,
            r"milliseconds?|ms|seconds?|secs?|sec|s|minutes?|mins?|min|hours?|hrs?|hr|h",
        )
        if time_match is None:
            # "velocity after" / "height after" without a duration is
            # ambiguous; do not silently answer with impact time.
            return None
        time_value, time_unit = time_match

    g = _detect_gravity(cleaned)
    params: dict[str, float] = {"g": g}
    units: dict[str, str] = {"g": "m/s^2"}
    if h0 is not None:
        params["h0"] = h0
        units["h0"] = h0_unit or "m"
    params["v0"] = v0
    units["v0"] = v0_unit or "m/s"
    if time_value is not None:
        params["t"] = time_value
        units["t"] = time_unit or "s"

    return MathIntent(
        kind="kinematics",
        physics_op=op,
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


# ---------------------------------------------------------------------------
# Projectile: 2D motion at an angle (range, max height, trajectory)
# ---------------------------------------------------------------------------

_PROJECTILE_CUES = (
    "projectile",
    "launched at angle",
    "launched at an angle",
    "fired at angle",
    "thrown at angle",
    "thrown at an angle",
    "range of",
    "maximum height",
    "max height",
    "trajectory",
)


def _extract_projectile_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not any(cue in lower for cue in _PROJECTILE_CUES):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    # Initial speed (v0): "at 15 m/s", "speed of 15 m/s", "velocity of 15 m/s"
    # Search for a number followed by a velocity unit (m/s, km/h) so "at 45 degrees"
    # isn't mistaken for the speed.
    v0: float | None = None
    v0_unit = "m/s"
    speed_m = re.search(
        r"(-?\d+(?:\.\d+)?)\s*(m/s|km/h|mph|cm/s|mm/s)",
        cleaned,
        re.IGNORECASE,
    )
    if speed_m:
        v0 = float(speed_m.group(1))
        v0_unit = speed_m.group(2)
    else:
        vu = _find_value_with_unit(cleaned, ("speed of", "velocity of", "speed", "velocity"))
        if vu is not None:
            v0, v0_unit = vu

    # Angle (theta): "angle of 45", "at an angle of 30", "at 45 degrees", "at 30°"
    angle: float | None = None
    # Prefer "angle of N" / "at an angle of N" — unambiguous.
    angle_m = re.search(
        r"(?:angle\s*(?:of)?\s*|at\s+an\s+angle\s*(?:of)?\s*)(-?\d+(?:\.\d+)?)\s*(?:degrees?|°|deg)?",
        lower,
    )
    if angle_m is None:
        # Fall back to "at N degrees/°/deg" — only when the unit word is
        # present so "at 15 m/s" (speed) isn't mistaken for an angle.
        angle_m = re.search(
            r"\bat\s+(-?\d+(?:\.\d+)?)\s*(?:degrees?|°|deg)\b",
            lower,
        )
    if angle_m:
        angle = float(angle_m.group(1))

    if v0 is None or angle is None:
        return None

    # Decide what the user is asking for.
    op: Literal["range", "max_height"] = "range"
    if "maximum height" in lower or "max height" in lower:
        op = "max_height"
    elif "trajectory" in lower:
        op = "range"  # trajectory implies range + plot

    g = _detect_gravity(cleaned)
    return MathIntent(
        kind="projectile",
        physics_op=op,
        physics_params={"v0": v0, "angle": angle, "g": g},
        physics_units={"v0": v0_unit or "m/s", "angle": "deg", "g": "m/s^2"},
        operation="solve",
    )


# ---------------------------------------------------------------------------
# Force: Newton's laws, net force, friction
# ---------------------------------------------------------------------------

_FORCE_CUES = (
    "net force",
    "newton's",
    "newtons law",
    "friction",
    "force of",
    "force required",
    "acceleration given",
    "given force",
    "normal force",
    "tension",
)


def _extract_force_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not any(cue in lower for cue in _FORCE_CUES):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    # Mass (m): "mass of 5 kg", "5 kg mass", "5kg object" — use unit-specific
    # search so "20 N" (force) isn't picked up as the mass.
    mass: float | None = None
    mass_unit = "kg"
    mu = _find_value_with_specific_unit(
        cleaned,
        r"kg|g|mg|lb|lbs|oz",
        ("mass", "object", "body"),
    )
    if mu is not None:
        mass, mass_unit = mu

    # Force (F): "force of 20 N", "20 N force" — use unit-specific search.
    force: float | None = None
    force_unit = "N"
    fu = _find_value_with_specific_unit(cleaned, r"N", ("force",))
    if fu is not None:
        force, force_unit = fu

    # Acceleration (a): "acceleration of 2 m/s^2"
    accel: float | None = None
    accel_unit = "m/s^2"
    au = _find_value_with_specific_unit(
        cleaned,
        r"m/s\^?2|m/s2",
        ("acceleration", "accelerates"),
    )
    if au is not None:
        accel, accel_unit = au

    # Need at least two of (mass, force, accel) to solve F = ma.
    known = [v for v in (mass, force, accel) if v is not None]
    if len(known) < 2:
        return None

    params: dict[str, float] = {}
    units: dict[str, str] = {}
    if mass is not None:
        params["m"] = mass
        units["m"] = mass_unit or "kg"
    if force is not None:
        params["F"] = force
        units["F"] = force_unit or "N"
    if accel is not None:
        params["a"] = accel
        units["a"] = accel_unit or "m/s^2"

    return MathIntent(
        kind="force",
        physics_op="net_force",
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


# ---------------------------------------------------------------------------
# Energy: kinetic, potential, work, power
# ---------------------------------------------------------------------------

_ENERGY_CUES = (
    "kinetic energy",
    "potential energy",
    "work done",
    "work is done",
    "how much work",
    "work of",
    "power of",
    "energy of",
    "conservation of energy",
)


def _extract_energy_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not any(cue in lower for cue in _ENERGY_CUES):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

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

    # Decide the operation.
    op: Literal["kinetic_energy", "potential_energy", "work", "power"]
    if "kinetic energy" in lower:
        op = "kinetic_energy"
        if mass is None or velocity is None:
            return None
    elif "potential energy" in lower:
        op = "potential_energy"
        if mass is None or height is None:
            return None
    elif "work" in lower:
        op = "work"
        if force is None or distance is None:
            return None
    elif "power" in lower:
        op = "power"
        if force is None or velocity is None:
            return None
    else:
        # "energy of" / "conservation of energy" — pick whichever we can solve.
        if mass is not None and velocity is not None:
            op = "kinetic_energy"
        elif mass is not None and height is not None:
            op = "potential_energy"
        elif force is not None and distance is not None:
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
    if op in ("work", "power") and force is not None:
        params["F"] = force
        units["F"] = force_unit or "N"
    if op == "work" and distance is not None:
        params["d"] = distance
        units["d"] = dist_unit or "m"
    if op == "potential_energy":
        params["g"] = _detect_gravity(cleaned)
        units["g"] = "m/s^2"

    return MathIntent(
        kind="energy",
        physics_op=op,
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


# ---------------------------------------------------------------------------
# Registry — ordered before the generic equation extractor (see extract.py).
# Kinematics first (most common homework cue), then projectile, force, energy.
# ---------------------------------------------------------------------------

PHYSICS_EXTRACTORS: tuple[Callable[[str], MathIntent | None], ...] = (
    _extract_kinematics_intent,
    _extract_projectile_intent,
    _extract_force_intent,
    _extract_energy_intent,
)
