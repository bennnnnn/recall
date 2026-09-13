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

from app.models.schemas.math import MathIntent
from app.services import math_text_match as mtm
from app.services.math_text_match.scan import word_index

logger = logging.getLogger(__name__)

# Length units for drop height — longer spellings before ``m`` so ``miles``
# is not read as metres. ``m`` still has a trailing-boundary lookahead.
_LENGTH_UNIT_PATTERN = (
    r"kilometers?|km|centimeters?|cm|millimeters?|mm|"
    r"miles?|mi|meters?|metres?|m|feet|ft|yards?|yd|inches?|in"
)
_VELOCITY_UNIT_PATTERN = r"m/s|km/h|mph|cm/s|mm/s|miles\s+per\s+hour"

# Default gravitational acceleration (m/s^2). Earth gravity unless the user
# says otherwise ("on the moon", "g = 1.6").
_G_DEFAULT = 9.81

# A number followed by an optional unit word. Captures the numeric value and
# the trailing unit (m, cm, km, ft, mi, m/s, m/s^2, kg, g, N, J, W, ...).
# The unit is matched loosely — we validate via Pint in the solver.
# Trailing boundary so ``m`` cannot bind inside ``miles`` / ``min``.
_VALUE_UNIT_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*"
    r"(m/s\^?2|m/s2|m/s|m\^?2/s\^?2|km/h|mph|miles\s+per\s+hour|cm/s|mm/s|"
    r"kilometers?|centimeters?|millimeters?|"
    r"miles?|minutes?|milliseconds?|seconds?|hours?|"
    r"meters?|metres?|inches?|yards?|feet|"
    r"km|cm|mm|mi|ft|yd|in|"
    r"kg|mg|lb|lbs|oz|"
    r"N|J|W|Pa|Hz|"
    r"s|ms|sec|min|hr|h|"
    r"deg|degrees|°|rad|radians)?"
    r"(?![A-Za-z0-9/^])",
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


def _find_value_after_keyword(text: str, keywords: tuple[str, ...]) -> tuple[float, str] | None:
    """Number immediately after a keyword — never the window before it.

    ``What`` / a preceding height must not bind as v0.
    """
    lower = text.lower()
    for kw in keywords:
        idx = lower.find(kw)
        if idx == -1:
            continue
        after = text[idx + len(kw) : idx + len(kw) + 40]
        m = _VALUE_UNIT_RE.match(after.strip())
        if m:
            return float(m.group(1)), (m.group(2) or "").strip()
    return None


def _find_value_with_specific_unit(
    text: str,
    unit_pattern: str,
    keywords: tuple[str, ...] = (),
    *,
    require_keyword: bool = False,
) -> tuple[float, str] | None:
    """Find a number followed by a specific unit (e.g. "20 N", "5 kg").

    When keywords are present in the text, prefer the unit-bearing value
    nearest one of them; otherwise use the first matching value. This avoids
    binding an earlier unrelated quantity to the requested mass/force/etc.

    ``require_keyword`` (projectile h0): if none of the keywords appear, return
    None instead of the first unlabeled length (``wall is 15 m away``).
    Kinematics unlabeled ``free fall 20 m`` still binds.
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
        if require_keyword and not keyword_spans:
            return None
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
        elif require_keyword:
            return None

    return float(match.group(1)), match.group(2)


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
    if word_index(lower, "moon") != -1:
        return 1.62
    if word_index(lower, "mars") != -1:
        return 3.71
    return _G_DEFAULT


_PARAM_ASSIGN_RE = re.compile(
    r"\b(?:gravity|theta|angle|h0|v0|h|F|m|g)\s*=\s*(?=-?\d)",
    re.IGNORECASE,
)
_T_ASSIGN_RE = re.compile(r"\bt\s*=\s*(?=-?\d)", re.IGNORECASE)


def _strip_param_assignments(text: str) -> str:
    """Remove ``h0 =`` / ``v0 =`` / ``g =`` labels so has_equation does not
    treat textbook knowns as algebra. The number and unit stay for scanners.

    Do not strip ``t`` / ``v`` / ``a`` / ``d`` — those are often the unknown
    (``find v when t = 1 s``) and stripping them silently solves the wrong op.
    """
    return _PARAM_ASSIGN_RE.sub("", text)


# ---------------------------------------------------------------------------
# Kinematics: 1D motion under gravity (free fall, dropped, thrown up/down)
# ---------------------------------------------------------------------------

_GRAVITY_MOTION_CUES = (
    "dropped",
    "free fall",
    "freefall",
    "falls from",
    "fall from",
    "falls off",
    "thrown upward",
    "thrown up",
    "thrown down",
    "thrown downward",
    "launched upward",
    "launched downward",
)

_KINEMATICS_CUES = (
    *_GRAVITY_MOTION_CUES,
    "how long until",
    "how long to hit",
    "how long to reach",
    "how long to fall",
    "time to hit",
    "time to reach",
    "velocity after",
    "speed after",
    "speed when",
    "height after",
    "position after",
    "acceleration of",
)

_H0_KEYWORDS = (
    "from",
    "initial height",
    "height of",
    "high",
    "above",
    "cliff",
    "off",
    "ledge",
    "h0",
    "dropped",
)


def _asks_speed(lower: str) -> bool:
    return "speed after" in lower or "speed when" in lower


def _asks_velocity(lower: str) -> bool:
    if "velocity after" in lower or "velocity when" in lower:
        return True
    if "what is its velocity" in lower or "what is the velocity" in lower:
        return True
    if "v when" in lower:
        return True
    return re.search(r"\b(?:find|what is)\s+v\b", lower) is not None


def _asks_position(lower: str) -> bool:
    return "height after" in lower or "position after" in lower


def _extract_kinematics_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    # Must have a kinematics cue AND at least one number.
    if not any(cue in lower for cue in _KINEMATICS_CUES):
        return None
    asks_speed = _asks_speed(lower)
    asks_velocity = _asks_velocity(lower)
    asks_position = _asks_position(lower)
    # Defer to the equation extractor if there's an explicit "=" equation —
    # but strip "g = 1.6" parameter specs first (those are knowns, not algebra).
    # When they asked for v/speed/position at a time, ``t = 1`` is a given,
    # not the problem to solve.
    stripped = _strip_param_assignments(cleaned)
    if asks_speed or asks_velocity or asks_position:
        stripped = _T_ASSIGN_RE.sub("", stripped)
    if mtm.has_equation(stripped):
        return None

    # Initial height (h0): length units only so "5 kg" is not a drop height.
    # Unlabeled ``free fall 20 m`` still binds; projectile keeps require_keyword
    # so a wall ``15 m away`` is not a launch height.
    h0: float | None = None
    h0_unit = "m"
    hu = _find_value_with_specific_unit(
        cleaned,
        _LENGTH_UNIT_PATTERN,
        _H0_KEYWORDS,
        require_keyword=False,
    )
    if hu is not None:
        h0, h0_unit = hu

    # Initial velocity (v0): velocity words or a velocity unit — never the
    # substring "at" inside "What" / "with".
    v0: float = 0.0
    v0_unit = "m/s"
    vu = _find_value_with_specific_unit(
        cleaned,
        _VELOCITY_UNIT_PATTERN,
        ("velocity of", "speed of", "velocity", "speed", "initial velocity"),
    )
    if vu is None:
        vu = _find_value_after_keyword(
            cleaned,
            ("velocity of", "speed of", "initial velocity", "velocity", "speed"),
        )
    if vu is not None:
        v0, v0_unit = vu
    if v0 > 0 and any(
        cue in lower for cue in ("thrown down", "thrown downward", "launched downward")
    ):
        v0 = -v0

    # If we found no height and no nonzero velocity, this isn't a solvable
    # kinematics problem — let the next extractor try.
    if h0 is None and v0 == 0.0:
        return None

    # Decide what the user is asking for.
    op: Literal["position", "velocity", "speed", "acceleration", "time_to_ground"] = (
        "time_to_ground"
    )
    if asks_speed:
        op = "speed"
    elif asks_velocity:
        op = "velocity"
    elif asks_position:
        op = "position"
    elif "acceleration" in lower:
        if not any(cue in lower for cue in _GRAVITY_MOTION_CUES):
            return None
        op = "acceleration"

    time_value: float | None = None
    time_unit = "s"
    if op in ("position", "velocity", "speed"):
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
    "fired at an angle",
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
        r"(-?\d+(?:\.\d+)?)\s*(m/s|km/h|mph|cm/s|mm/s|miles\s+per\s+hour)",
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
        r"(?:angle\s*(?:of|=)?\s*|at\s+an\s+angle\s*(?:of)?\s*)(-?\d+(?:\.\d+)?)\s*"
        r"(?:degrees?|°|deg|radians?|rad)?",
        lower,
    )
    if angle_m is None:
        # Fall back to "at N degrees/°/deg" — only when the unit word is
        # present so "at 15 m/s" (speed) isn't mistaken for an angle.
        # ``°`` is not a word char, so a trailing ``\b`` would miss ``30°?``.
        angle_m = re.search(
            r"\bat\s+(-?\d+(?:\.\d+)?)\s*(?:degrees?|°|deg)(?![A-Za-z0-9])",
            lower,
        )
    if angle_m is None:
        # After stripping ``angle = 30``, only ``30 deg`` remains.
        angle_m = re.search(
            r"(-?\d+(?:\.\d+)?)\s*(?:degrees?|°|deg|radians?|rad)(?![A-Za-z0-9])",
            lower,
        )
    if angle_m:
        angle = float(angle_m.group(1))

    if v0 is None or angle is None:
        return None

    h0: float | None = None
    h0_unit = "m"
    hu = _find_value_with_specific_unit(
        cleaned,
        _LENGTH_UNIT_PATTERN,
        ("from", "initial height", "height of", "high", "above", "cliff", "h0"),
        require_keyword=True,
    )
    if hu is not None:
        h0, h0_unit = hu

    # Decide what the user is asking for.
    op: Literal["range", "max_height"] = "range"
    if "maximum height" in lower or "max height" in lower:
        op = "max_height"
    elif "trajectory" in lower:
        op = "range"  # trajectory implies range + plot

    g = _detect_gravity(cleaned)
    angle_unit = "rad" if re.search(r"\b(?:rad|radians)\b", lower) else "deg"
    params: dict[str, float] = {"v0": v0, "angle": angle, "g": g}
    units: dict[str, str] = {"v0": v0_unit or "m/s", "angle": angle_unit, "g": "m/s^2"}
    if h0 is not None:
        params["h0"] = h0
        units["h0"] = h0_unit or "m"
    return MathIntent(
        kind="projectile",
        physics_op=op,
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


# ---------------------------------------------------------------------------
# Force: scalar Newton's second law (F = ma)
# ---------------------------------------------------------------------------

_FORCE_CUES = (
    "net force",
    "newton's second law",
    "newtons second law",
    "force of",
    "force required",
    "what is the force",
    "what's the force",
    "find the force",
    "find the mass",
    "acceleration given",
    "given force",
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
        ("acceleration", "accelerates", "accelerated"),
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
    "what is the power",
    "what's the power",
    "energy of",
)


def _has_work_angle(text: str) -> bool:
    """True when work is at an angle (W = Fd cos θ) — unsupported."""
    lower = text.lower()
    return "degrees" in lower or "at an angle" in lower or "°" in text


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
        # W = Fd cos θ is unsupported — same refusal as friction/tension.
        if _has_work_angle(cleaned):
            return None
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
            if _has_work_angle(cleaned):
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

PHYSICS_CUES: tuple[str, ...] = tuple(
    dict.fromkeys((*_KINEMATICS_CUES, *_PROJECTILE_CUES, *_FORCE_CUES, *_ENERGY_CUES))
)


def has_supported_physics_cue(lower: str) -> bool:
    """True when a verified physics template could match this (lowercased) text."""
    return any(cue in lower for cue in PHYSICS_CUES)
