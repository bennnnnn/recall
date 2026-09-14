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
from app.services.math import match as mtm
from app.services.math.match.scan import word_index

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


def _has_cue(
    lower: str,
    cues: tuple[str, ...],
    regexes: tuple[re.Pattern[str], ...] = (),
) -> bool:
    """Cue match: plain substrings, plus regexes for cues that need a boundary.

    Most cues are safe as substrings ("net force"). A few are not: "find f"
    sits inside "find factors", and "KE" inside "take". Those are expressed as
    regexes instead of widening the tuple.
    """
    if any(cue in lower for cue in cues):
        return True
    return any(rx.search(lower) for rx in regexes)


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
    # Spoken forms of the same question. Naming the ground is unambiguous;
    # "how long ... to fall" needs the regex below, so a share price about to
    # fall 20% is not read as free fall.
    "to hit the ground",
    "to reach the ground",
    "velocity after",
    "speed after",
    "speed when",
    "height after",
    "position after",
    "acceleration of",
)

_KINEMATICS_CUE_RES: tuple[re.Pattern[str], ...] = (re.compile(r"\bhow long\b.{0,60}?\bto fall\b"),)

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
    if "speed after" in lower or "speed when" in lower:
        return True
    # "how fast is it going after 2 s" is the spoken form of "speed after".
    return "how fast" in lower


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
    if not _has_cue(lower, _KINEMATICS_CUES, _KINEMATICS_CUE_RES):
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
    # kinematics problem — let the next extractor try. Speed and velocity at a
    # known time are the exception: v = v0 - g*t needs no height, so
    # "how fast is a dropped ball going after 1 s" is answerable. They are let
    # through here and gated below instead, where a missing time returns None.
    if h0 is None and v0 == 0.0 and not (asks_speed or asks_velocity):
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

# Question-first and verb-first shapes ("a ball is thrown at 20 m/s at 30
# degrees, what is the range?"). The question word is the wrong thing to match
# on — "the range" also appears in "pick a number in the range 2-6", and these
# cues feed the global needs_math_tools pre-filter, not just this extractor.
# A speed and an angle in the same clause is the projectile signature itself,
# and it holds whatever verb the question uses.
_PROJECTILE_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\d\s*(?:m/s|km/h|mph)\b.{0,80}?\d\s*(?:degrees?|deg|°)"),
    re.compile(r"\d\s*(?:degrees?|deg|°).{0,80}?\d\s*(?:m/s|km/h|mph)\b"),
)


def _extract_projectile_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _PROJECTILE_CUES, _PROJECTILE_CUE_RES):
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
    if "maximum height" in lower or "max height" in lower or "how high" in lower:
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
# Momentum: p = m v, impulse J = F dt, and 1D collisions
# ---------------------------------------------------------------------------

# All unambiguous physics words. That is why this extractor runs *before* force
# and energy rather than after: an impulse question names newtons and seconds,
# and a collision names kilograms and m/s, which is exactly the shape those two
# look for. Running momentum first cannot steal from them, running it last can
# lose to them.
_MOMENTUM_CUES = (
    "momentum",
    "impulse",
    "collision",
    "collide",
    "collides",
    "recoil",
    "stick together",
    "sticks together",
)

# Elastic is *not* a cue on its own — an elastic band is not a collision. It
# only tells us which conservation law to apply once a collision is in hand.
# No trailing \b: people write "collides inelastically", and requiring a
# boundary after the stem silently drops the adverb form. "elastic" cannot
# match inside "inelastic" — the leading \b sees the "n" and fails — so the
# two stay distinguishable.
_ELASTIC_RE = re.compile(r"\belastic")
_INELASTIC_RE = re.compile(
    r"\binelastic|sticks? together|stuck together|"
    r"\bcoupled?\b|\bembed(?:s|ded)?\b|\block(?:s|ed)? together\b"
)

_MASS_UNITS = r"kg|mg|g|lb|lbs|oz"
_MOMENTUM_TIME_UNITS = r"milliseconds?|ms|seconds?|secs?|sec|s|minutes?|mins?|min|hours?|hrs?|hr|h"


def _ordered_values(text: str, unit_pattern: str) -> list[tuple[float, str]]:
    """Every number carrying one of these units, left to right.

    Collisions need two masses and two velocities *in the order written* —
    "a 2 kg ball at 3 m/s hits a 1 kg ball at rest" binds m1=2, v1=3, m2=1.
    The keyword-nearest search the other extractors use cannot express that.
    """
    return [
        (float(m.group(1)), m.group(2))
        for m in re.finditer(
            rf"(-?\d+(?:\.\d+)?)\s*({unit_pattern})(?![A-Za-z0-9/^])",
            text,
            re.IGNORECASE,
        )
    ]


def _extract_momentum_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _MOMENTUM_CUES):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    masses = _ordered_values(cleaned, _MASS_UNITS)
    velocities = _ordered_values(cleaned, _VELOCITY_UNIT_PATTERN)

    is_collision = (
        any(
            word in lower
            for word in ("collision", "collide", "collides", "hits", "strikes", "recoil")
        )
        or _INELASTIC_RE.search(lower) is not None
    )

    # --- 1D collision: two masses, at least one velocity ---
    if is_collision and len(masses) >= 2:
        elastic = _ELASTIC_RE.search(lower) is not None and not _INELASTIC_RE.search(lower)
        inelastic = _INELASTIC_RE.search(lower) is not None
        # Refuse rather than guess. Elastic and inelastic give genuinely
        # different answers from identical inputs, so an unstated collision type
        # would produce a confidently wrong number — the same failure mode the
        # tension guard closes off.
        if not elastic and not inelastic:
            return None
        m1, m1_unit = masses[0]
        m2, m2_unit = masses[1]
        v1, v1_unit = velocities[0] if velocities else (0.0, "m/s")
        # "hits a ball at rest" leaves v2 unwritten; "at rest" means zero.
        v2, v2_unit = velocities[1] if len(velocities) > 1 else (0.0, "m/s")
        return MathIntent(
            kind="momentum",
            physics_op="final_velocity",
            physics_params={
                "m1": m1,
                "m2": m2,
                "v1": v1,
                "v2": v2,
                "elastic": 1.0 if elastic else 0.0,
            },
            physics_units={
                "m1": m1_unit or "kg",
                "m2": m2_unit or "kg",
                "v1": v1_unit or "m/s",
                "v2": v2_unit or "m/s",
                "elastic": "",
            },
            operation="solve",
        )

    # --- Impulse: J = F dt, or J = m (v2 - v1) ---
    if "impulse" in lower:
        forces = _ordered_values(cleaned, r"N")
        times = _ordered_values(cleaned, _MOMENTUM_TIME_UNITS)
        if forces and times:
            f, f_unit = forces[0]
            dt, dt_unit = times[0]
            return MathIntent(
                kind="momentum",
                physics_op="impulse",
                physics_params={"F": f, "dt": dt},
                physics_units={"F": f_unit or "N", "dt": dt_unit or "s"},
                operation="solve",
            )
        if masses and len(velocities) >= 2:
            m, m_unit = masses[0]
            v1, v1_unit = velocities[0]
            v2, v2_unit = velocities[1]
            return MathIntent(
                kind="momentum",
                physics_op="impulse",
                physics_params={"m": m, "v1": v1, "v2": v2},
                physics_units={"m": m_unit or "kg", "v1": v1_unit or "m/s", "v2": v2_unit or "m/s"},
                operation="solve",
            )
        return None

    # --- Plain momentum: p = m v ---
    if "momentum" in lower and masses and velocities:
        m, m_unit = masses[0]
        v, v_unit = velocities[0]
        return MathIntent(
            kind="momentum",
            physics_op="momentum",
            physics_params={"m": m, "v": v},
            physics_units={"m": m_unit or "kg", "v": v_unit or "m/s"},
            operation="solve",
        )

    return None


# ---------------------------------------------------------------------------
# Friction and inclined planes
#   N = m g cos(theta)          (theta = 0 on level ground)
#   f = mu N
#   a = g (sin(theta) - mu cos(theta))   down the slope
# ---------------------------------------------------------------------------

# "slope" is deliberately absent. It is a mathematics word first — "find the
# slope of the line through (1, 2) and (3, 8)" resolves to a coordinate-geometry
# intent today, and the geometry extractors run *after* physics, so a bare
# "slope" cue here would steal it outright. "ramp" and "incline" carry the same
# meaning without the collision.
# Only the two that are solvable on their own: a normal force needs nothing but
# a mass, and "frictionless" states its own coefficient.
_FRICTION_CUES = (
    "normal force",
    "frictionless",
)

# Everything else has to carry something to solve with. "find the friction on a
# 5 kg block" names no coefficient and no angle, so it is unanswerable — and
# because these cues feed the global needs_math_tools pre-filter, firing on it
# would spend a tool round to discover that. Requiring the co-occurrence keeps
# the pre-filter honest, and an existing test in test_math_text_match.py holds
# that line.
_FRICTION_SUBJECT = r"friction|frictional|incline|inclined|ramp"
_FRICTION_GIVEN = r"coefficient|\bmu\s*=|\u03bc\s*=|\d+\s*(?:degrees?|deg|\u00b0)"
_FRICTION_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(rf"(?:{_FRICTION_SUBJECT}).{{0,80}}?(?:{_FRICTION_GIVEN})", re.IGNORECASE),
    re.compile(rf"(?:{_FRICTION_GIVEN}).{{0,80}}?(?:{_FRICTION_SUBJECT})", re.IGNORECASE),
)

# Asking *about* friction is not the same as mentioning it. "what is the net
# force on a 5 kg block with a friction coefficient of 0.2" asks for a
# different quantity, and answering it with mu*m*g would be confidently wrong —
# which is exactly what the P2 refusal test caught when this was looser.
_FRICTION_FORCE_ASK_RE = re.compile(
    r"friction(?:al)?\s+force|force\s+of\s+friction"
    r"|(?:find|calculate|determine|compute|what\s+is)\s+the\s+friction\b",
    re.IGNORECASE,
)

# "coefficient" alone belongs to algebra ("the coefficient of x^2"), so it only
# counts when friction is named or it is written as mu.
_MU_RE = re.compile(
    r"(?:coefficient\s+of\s+(?:kinetic\s+|static\s+)?friction\s*(?:of|=|is)?\s*"
    r"|coefficient\s*(?:of|=|is)?\s*"
    r"|\bmu\s*=\s*|\u03bc\s*=\s*)"
    r"(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_INCLINE_ANGLE_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(?:degrees?|deg|\u00b0)(?![A-Za-z0-9])", re.IGNORECASE
)


def _extract_friction_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _FRICTION_CUES, _FRICTION_CUE_RES):
        return None
    if "net force" in lower:
        # A different quantity. The force extractor refuses it via
        # _UNSUPPORTED_FORCE_CONTEXT rather than guessing, which is right.
        return None
    if mtm.has_equation(_strip_param_assignments(_MU_RE.sub("", cleaned))):
        return None

    mass = _find_value_with_specific_unit(
        cleaned, r"kg|g|mg|lb|lbs|oz", ("mass", "block", "box", "crate", "object", "body")
    )

    frictionless = "frictionless" in lower
    mu_match = _MU_RE.search(cleaned)
    mu = 0.0 if frictionless else (float(mu_match.group(1)) if mu_match else None)

    angle_match = _INCLINE_ANGLE_RE.search(cleaned)
    angle = float(angle_match.group(1)) if angle_match else 0.0

    wants_normal = "normal force" in lower
    wants_acceleration = "acceleration" in lower or "accelerate" in lower
    wants_friction = _FRICTION_FORCE_ASK_RE.search(cleaned) is not None and not frictionless

    op: Literal["friction_force", "normal_force", "incline_acceleration"]
    if wants_acceleration:
        op = "incline_acceleration"
        # No mass requirement here, and that is the point: a = g(sin t - mu cos t)
        # is mass-independent, which is the whole reason the incline result is
        # worth teaching. Demanding a mass would reject the textbook phrasing
        # ("a block on a frictionless 30 degree incline") that omits it.
        if mu is None:
            # Without a coefficient this is only solvable if it is stated to be
            # frictionless — otherwise the answer needs a number nobody gave.
            return None
        if angle == 0.0:
            # "acceleration" with no incline angle is an F = ma question, not
            # this one. Leave it for the force extractor.
            return None
    elif wants_normal:
        op = "normal_force"
        if mass is None:
            return None
        mu = mu if mu is not None else 0.0
    elif wants_friction:
        op = "friction_force"
        if mass is None or mu is None:
            return None
    else:
        return None

    params: dict[str, float] = {"mu": mu, "angle": angle, "g": _detect_gravity(cleaned)}
    units: dict[str, str] = {
        "mu": "",
        "angle": "rad" if re.search(r"\b(?:rad|radians)\b", lower) else "deg",
        "g": "m/s^2",
    }
    if mass is not None:
        params["m"] = mass[0]
        units["m"] = mass[1] or "kg"
    return MathIntent(
        kind="friction",
        physics_op=op,
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


# ---------------------------------------------------------------------------
# Circular motion
#   a_c = v^2 / r,  F_c = m v^2 / r,  T = 2 pi r / v
# ---------------------------------------------------------------------------

# Neither "circle" nor "radius" is a cue. "area of a circle of radius 3"
# resolves to the geometry `circle` intent, and the geometry extractors run
# *after* physics — so either word here would take that question rather than
# compete for it. Only words that mean motion qualify.
_CIRCULAR_CUES = (
    "centripetal",
    "circular motion",
    "orbital",
    "revolution",
)

# "period" is the exception worth spelling out: on its own it belongs to
# trigonometry ("the period of sin(2x)"), so it only counts beside a radius.
_CIRCULAR_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bperiod\b.{0,80}?\bradius\b", re.IGNORECASE),
    re.compile(r"\bradius\b.{0,80}?\bperiod\b", re.IGNORECASE),
)


def _extract_circular_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _CIRCULAR_CUES, _CIRCULAR_CUE_RES):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    radius = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("radius", "radii"), require_keyword=True
    )
    speed = _find_value_with_specific_unit(cleaned, _VELOCITY_UNIT_PATTERN)
    if radius is None or speed is None:
        return None

    mass = _find_value_with_specific_unit(
        cleaned, r"kg|g|mg|lb|lbs|oz", ("mass", "object", "body", "ball", "car")
    )

    op: Literal["centripetal_force", "centripetal_acceleration", "orbital_period"]
    if "period" in lower or "revolution" in lower:
        op = "orbital_period"
    elif "acceleration" in lower:
        op = "centripetal_acceleration"
    elif "force" in lower:
        op = "centripetal_force"
        # F = m v^2 / r is the only one of the three that needs a mass; the
        # other two are mass-independent, same as the incline result in P5.
        if mass is None:
            return None
    else:
        return None

    params: dict[str, float] = {"r": radius[0], "v": speed[0]}
    units: dict[str, str] = {"r": radius[1] or "m", "v": speed[1] or "m/s"}
    if mass is not None:
        params["m"] = mass[0]
        units["m"] = mass[1] or "kg"
    return MathIntent(
        kind="circular",
        physics_op=op,
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


# ---------------------------------------------------------------------------
# Springs and simple harmonic motion
#   F = k x,  U = 1/2 k x^2,  T = 2 pi sqrt(m / k)
# ---------------------------------------------------------------------------

# "spring" alone is a season and a semester. It only counts beside a spring
# constant, which is what the regexes below require — same co-occurrence shape
# P5 used for friction, and for the same reason: these cues feed the global
# needs_math_tools pre-filter, so a bare "spring break in 3 weeks" would spend a
# tool round on a question nothing here can answer.
_SPRING_CUES = (
    "hooke",
    "spring constant",
    "simple harmonic",
    "oscillation",
    "oscillating",
    "oscillates",
)
_SPRING_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bspring\b.{0,80}?(?:\d+\s*N/m|\bk\s*=)", re.IGNORECASE),
    re.compile(r"(?:\d+\s*N/m|\bk\s*=).{0,80}?\bspring\b", re.IGNORECASE),
)

_SPRING_K_RE = re.compile(r"\bk\s*=\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
_DISPLACEMENT_KEYWORDS = (
    "stretched",
    "compressed",
    "extended",
    "displacement",
    "amplitude",
    "extension",
    "by",
)


def _extract_spring_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _SPRING_CUES, _SPRING_CUE_RES):
        return None
    # Strip "k = 200" before the algebra check: it is a known, not an equation
    # to solve. Without this the whole question is read as algebra — which is
    # what happened before this extractor existed.
    if mtm.has_equation(_strip_param_assignments(_SPRING_K_RE.sub("", cleaned))):
        return None

    k_match = _find_value_with_specific_unit(cleaned, r"N/m")
    if k_match is not None:
        k: float | None = k_match[0]
    else:
        k_assign = _SPRING_K_RE.search(cleaned)
        k = float(k_assign.group(1)) if k_assign else None
    if k is None:
        return None

    displacement = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, _DISPLACEMENT_KEYWORDS
    )
    mass = _find_value_with_specific_unit(
        cleaned, r"kg|mg|lb|lbs|oz", ("mass", "object", "body", "block")
    )

    op: Literal["spring_force", "spring_energy", "shm_period"]
    if "period" in lower or "oscillat" in lower or "simple harmonic" in lower:
        op = "shm_period"
        if mass is None:
            return None
    elif "energy" in lower:
        op = "spring_energy"
        if displacement is None:
            return None
    elif "force" in lower:
        op = "spring_force"
        if displacement is None:
            return None
    else:
        return None

    params: dict[str, float] = {"k": k}
    units: dict[str, str] = {"k": "N/m"}
    if displacement is not None:
        params["x"] = displacement[0]
        units["x"] = displacement[1] or "m"
    if mass is not None:
        params["m"] = mass[0]
        units["m"] = mass[1] or "kg"
    return MathIntent(
        kind="spring",
        physics_op=op,
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


# ---------------------------------------------------------------------------
# Circuits: Ohm's law and resistance networks
#   V = I R,  P = V I,  series R = R1 + R2,  parallel 1/R = 1/R1 + 1/R2
# ---------------------------------------------------------------------------

# "series" and "parallel" are NOT cues. Both belong to mathematics first — a
# geometric series is a `series` intent and a parallelogram is its own kind —
# and they only ever appear here as qualifiers on a question that already names
# resistors. "current" is left out for the same reason ("the current date").
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
)

_VOLT_PATTERN = r"V|volts?"
_AMP_PATTERN = r"A|amps?|amperes?"
_OHM_PATTERN = r"ohms?|\u03a9"

# A question can name no circuit *word* and still be one: "the electrical power
# for 12 V and 3 A" is entirely units. Two electrical quantities together are
# the signature — the same shape P2 used for the projectile's speed-and-angle.
#
# Deliberately case-sensitive on the bare letters. "V" and "A" are the SI
# symbols; matching them case-insensitively would let "3 a piece" read as three
# amps. The spelled-out forms stay case-insensitive.
_ELECTRICAL_QUANTITY = r"V|[Vv]olts?|A|[Aa]mp(?:s|ere|eres)?|[Oo]hms?|\u03a9"
_CIRCUIT_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(rf"\d\s*(?:V|[Vv]olts?)\b.{{0,80}}?\d\s*(?:{_ELECTRICAL_QUANTITY})\b"),
    re.compile(
        rf"\d\s*(?:A|[Aa]mp(?:s|ere|eres)?|[Oo]hms?|\u03a9)\b.{{0,80}}?"
        rf"\d\s*(?:{_ELECTRICAL_QUANTITY})\b"
    ),
)


def _extract_circuit_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _CIRCUIT_CUES) and not any(
        rx.search(cleaned) for rx in _CIRCUIT_CUE_RES
    ):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    volts = _ordered_values(cleaned, _VOLT_PATTERN)
    amps = _ordered_values(cleaned, _AMP_PATTERN)
    ohms = _ordered_values(cleaned, _OHM_PATTERN)

    # --- resistor networks: two or more resistances and a stated topology ---
    if len(ohms) >= 2 and ("series" in lower or "parallel" in lower):
        op: Literal[
            "voltage",
            "current",
            "resistance",
            "electrical_power",
            "series_resistance",
            "parallel_resistance",
        ] = "series_resistance" if "series" in lower else "parallel_resistance"
        return MathIntent(
            kind="circuit",
            physics_op=op,
            physics_params={"R1": ohms[0][0], "R2": ohms[1][0]},
            physics_units={"R1": "ohm", "R2": "ohm"},
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

    # Electrical power needs electrical units present, which is what keeps it
    # from colliding with the mechanical `power` op (P = F v, in newtons and
    # m/s). Two different quantities that share a name and a unit.
    if "power" in lower or "dissipat" in lower or "watt" in lower:
        if len(params) < 2:
            return None
        return MathIntent(
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
    return MathIntent(
        kind="circuit",
        physics_op=asked,
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
    # Question-first and verb-first shapes ("what force accelerates 5 kg...",
    # "calculate the force on a 5 kg object"). solve_force still needs exactly
    # two of F, m, a with units, so a non-physics "force" sentence returns None.
    "what force",
    "how much force",
    "force needed",
    "force on",
    "force acts",
    "force applied",
    "accelerates at",
    "accelerating at",
    "accelerated at",
)

# Free-body problems whose answer is not F = ma. Tension on an accelerating
# mass is T = m(g + a), not m*a; friction needs mu and a normal force; an
# incline needs its angle. Answering "10 N" for a 5 kg mass accelerating at
# 2 m/s^2 under tension is not a near miss, it is confidently wrong, and a
# wrong number in the verified block is worse than none.
#
# Until now these were kept out by accident — no cue matched their usual
# wording. Widening the cues removed that cover, so the boundary is stated
# here instead.
#
# P5 did NOT delete its lines when friction landed, and the earlier note saying
# it would was wrong. `_extract_friction_intent` runs ahead of this extractor
# and claims what it can solve; what reaches here is the remainder — a friction
# question missing its coefficient, say — and for that remainder F = ma is
# still the wrong formula. The entries guard the fall-through, so P6 and P7
# should keep theirs for the same reason.
_UNSUPPORTED_FORCE_CONTEXT = (
    "tension",
    "friction",
    "coefficient",
    "incline",
    "ramp",
    "slope",
    "pulley",
    "normal force",
    "spring",
    "centripetal",
    "buoyan",
)

# "find f" cannot be a substring cue: it sits inside "find factors", and
# "find f(x)" is calculus. Boundary + no opening paren keeps both out.
_FORCE_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:find|calculate|determine|compute)\s+f\b(?!\s*\()"),
)


def _extract_force_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _FORCE_CUES, _FORCE_CUE_RES):
        return None
    if any(word in lower for word in _UNSUPPORTED_FORCE_CONTEXT):
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
    "what power",
    "how much power",
    "power needed",
    "power required",
    "power is needed",
)

# "KE"/"PE" only where they clearly name a quantity. A bare \bpe\b would fire
# on "PE at 3pm"; requiring "of" after it keeps the abbreviation to physics.
_KE_ABBREV_RE = re.compile(r"\bk\.?\s?e\.?\s+of\b")
_PE_ABBREV_RE = re.compile(r"\bp\.?\s?e\.?\s+of\b")
_ENERGY_CUE_RES: tuple[re.Pattern[str], ...] = (_KE_ABBREV_RE, _PE_ABBREV_RE)


def _has_work_angle(text: str) -> bool:
    """True when work is at an angle (W = Fd cos θ) — unsupported."""
    lower = text.lower()
    return "degrees" in lower or "at an angle" in lower or "°" in text


def _extract_energy_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _ENERGY_CUES, _ENERGY_CUE_RES):
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
        # Either school form: P = F v, or P = W / t.
        if (force is None or velocity is None) and (work_done is None or elapsed is None):
            return None
    elif "work" in lower:
        # W = Fd cos θ is unsupported — same refusal as friction/tension.
        if _has_work_angle(cleaned):
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
    _extract_momentum_intent,
    _extract_friction_intent,
    _extract_circular_intent,
    _extract_spring_intent,
    _extract_circuit_intent,
    _extract_force_intent,
    _extract_energy_intent,
)

PHYSICS_CUES: tuple[str, ...] = tuple(
    dict.fromkeys(
        (
            *_KINEMATICS_CUES,
            *_PROJECTILE_CUES,
            *_MOMENTUM_CUES,
            *_FRICTION_CUES,
            *_CIRCULAR_CUES,
            *_SPRING_CUES,
            *_CIRCUIT_CUES,
            *_FORCE_CUES,
            *_ENERGY_CUES,
        )
    )
)

# The boundary-sensitive half of the same table — see ``_has_cue``.
PHYSICS_CUE_RES: tuple[re.Pattern[str], ...] = (
    *_KINEMATICS_CUE_RES,
    *_PROJECTILE_CUE_RES,
    *_FRICTION_CUE_RES,
    *_CIRCULAR_CUE_RES,
    *_SPRING_CUE_RES,
    *_CIRCUIT_CUE_RES,
    *_FORCE_CUE_RES,
    *_ENERGY_CUE_RES,
)


def has_supported_physics_cue(lower: str) -> bool:
    """True when a verified physics template could match this (lowercased) text."""
    return _has_cue(lower, PHYSICS_CUES, PHYSICS_CUE_RES)
