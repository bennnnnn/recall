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
# Scientific notation is how astronomy states a mass, and nothing here read it:
# "6e24 kg" matched as *24 kg*, which answered a planet's surface gravity as
# 0.00 m/s^2 rather than failing. Shared by every value scanner below.
_NUMBER = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"

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
    rf"({_NUMBER})\s*"
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


def _has_cue_either_case(
    cleaned: str,
    cues: tuple[str, ...],
    regexes: tuple[re.Pattern[str], ...] = (),
) -> bool:
    """`_has_cue`, but the regexes see the text as written as well as lowered.

    A few cue regexes mean the SI symbols `V` and `A` and are case-sensitive on
    purpose - "12 V and 3 A" is a circuit, "12 v cards and 3 a piece" is not.
    Handing them only lowercased text silently disables them, which is exactly
    what the pre-filter did: `needs_symbolic` dropped questions the extractor
    would have answered, because the extractor saw the original casing and the
    pre-filter did not. The two have to see the same thing.
    """
    lower = cleaned.lower()
    if any(cue in lower for cue in cues):
        return True
    return any(rx.search(cleaned) or rx.search(lower) for rx in regexes)


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
            rf"({_NUMBER})\s*({unit_pattern})(?![A-Za-z0-9/^])",
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


_STATED_ACCELERATION_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*m/s\^?2(?![0-9])", re.IGNORECASE)


def _states_a_non_gravity_acceleration(text: str) -> bool:
    """True when the question names an acceleration that is not the gravity in play.

    Free fall means gravity *is* the acceleration, so a question that supplies
    its own is not a free-fall question. Without this, kinematics claimed
    "a car accelerates from rest at 3 m/s^2, how long to reach 15 m/s" and
    answered **3.06 s** — which is 15/9.81, the time a ball thrown up at 15 m/s
    takes to stop. The stated 3 m/s² was discarded and Earth's gravity
    substituted for it; the true answer is 5.00 s.

    A named gravity is the exception rather than a special case: "g = 1.6",
    "gravity of 1.62", "on the moon" all set the free-fall acceleration, and
    ``_detect_gravity`` already knows what it is. Comparing against that value
    keeps those questions here and sends only the genuinely different ones on.
    """
    gravity = _detect_gravity(text)
    return any(
        abs(float(m.group(1)) - gravity) > 1e-9 for m in _STATED_ACCELERATION_RE.finditer(text)
    )


def _extract_kinematics_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    # Must have a kinematics cue AND at least one number.
    if not _has_cue(lower, _KINEMATICS_CUES, _KINEMATICS_CUE_RES):
        return None
    # Constant acceleration that is not gravity belongs to SUVAT, which runs
    # next. Claiming it here does not merely answer a different question — it
    # answers with the wrong acceleration.
    if _states_a_non_gravity_acceleration(cleaned):
        return None
    # A launch angle means the speed given is not the vertical speed, and this
    # extractor has no angle: it would use the whole 20 m/s as the vertical
    # component and answer 4.08 s where the projectile's answer is 2.04 s.
    # Same defect as the non-gravity acceleration above — a different question
    # answered with the wrong number, not merely a different question.
    # (``_PROJECTILE_CUE_RES`` is defined further down; module globals resolve
    # at call time.)
    if any(rx.search(lower) for rx in _PROJECTILE_CUE_RES):
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
# SUVAT: motion under any constant acceleration
#   v = u + at        s = ut + ½at²
#   v² = u² + 2as     s = ½(u + v)t
# ---------------------------------------------------------------------------
#
# The largest coverage gap round 1 left: `kinematics` solves free fall under
# gravity, so a car pulling away from a stop was not physics to us at all.
#
# There are no plain-substring cues. Every one of these is a signature — a
# motion verb or a rest state beside an actual velocity or acceleration
# reading — because this tuple feeds the global `needs_math_tools` pre-filter,
# and "accelerates" or "from rest" on their own are ordinary English.
_SUVAT_CUES: tuple[str, ...] = ()

_SUVAT_CUE_RES: tuple[re.Pattern[str], ...] = (
    # "accelerates ... at 3 m/s^2", and the same reading written backwards.
    re.compile(r"\b(?:ac|de)celerat\w*\b.{0,60}?\d\s*m/s\^?2", re.IGNORECASE),
    re.compile(r"\d\s*m/s\^?2.{0,60}?\b(?:ac|de)celerat\w*\b", re.IGNORECASE),
    # A rest state at one end and a speed at the other: "from rest ... 20 m/s",
    # "12 m/s to rest". This is the shape that carries no acceleration at all
    # (s = ½(u+v)t), so it cannot be found by looking for m/s².
    re.compile(r"\b(?:from|at)\s+rest\b.{0,80}?\d\s*(?:m/s|km/h|mph)\b", re.IGNORECASE),
    re.compile(
        r"\d\s*(?:m/s|km/h|mph)\b.{0,80}?\bto\s+(?:rest|a\s+(?:stop|halt))\b", re.IGNORECASE
    ),
    re.compile(r"\b(?:constant|uniform)\s+(?:ac|de)celeration\b", re.IGNORECASE),
)

# "from rest" / "at rest" as the *starting* state, so u = 0.
_AT_REST_START_RE = re.compile(
    r"\b(?:from|at|starts?\s+(?:from|at)|starting\s+(?:from|at)|initially\s+at)\s+rest\b",
    re.IGNORECASE,
)
# The body ends at rest, so v = 0. "before it stops", "comes to a halt".
_AT_REST_END_RE = re.compile(
    r"\bto\s+(?:rest|a\s+(?:stop|halt))\b|\b(?:stops?|stopping|halts?)\b"
    r"|\bcomes?\s+to\s+(?:rest|a\s+(?:stop|halt))\b",
    re.IGNORECASE,
)
_DECELERATION_RE = re.compile(r"\bdecelerat\w*\b|\bslow(?:s|ing|ed)?\s+down\b", re.IGNORECASE)

_SUVAT_TIME_UNITS = r"seconds?|secs?|sec|s|minutes?|mins?|min|hours?|hrs?|hr|h"

# Which of the five the question is asking for. Order matters only in that a
# question naming two is read by the first rule that fires; in practice a SUVAT
# question asks for exactly one.
_SUVAT_UNKNOWN_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "suvat_distance",
        re.compile(
            r"\bhow far\b|\bwhat distance\b|\bdistance (?:does|do|is|will|travel|cover)"
            r"|\bdistance travell?ed\b|\bhow much (?:distance|ground)\b|\bfind the distance\b",
            re.IGNORECASE,
        ),
    ),
    (
        "suvat_velocity",
        re.compile(
            r"\bfinal (?:velocity|speed)\b|\bhow fast\b|\bwhat (?:is its |is the )?"
            r"(?:velocity|speed)\b|\bfind the (?:velocity|speed)\b|\bspeed (?:does|will|is)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "suvat_acceleration",
        re.compile(
            r"\bwhat (?:is the |was the )?(?:ac|de)celeration\b|\bfind the (?:ac|de)celeration\b"
            r"|\bhow (?:quickly|rapidly) (?:does|did) it (?:ac|de)celerate\b",
            re.IGNORECASE,
        ),
    ),
    (
        "suvat_time",
        re.compile(
            r"\bhow long\b|\bhow much time\b|\bwhat time\b|\bfind the time\b"
            r"|\btime (?:does|will|is) it take\b",
            re.IGNORECASE,
        ),
    ),
)


def _extract_suvat_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _SUVAT_CUES, _SUVAT_CUE_RES):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    unknown = next(
        (op for op, rx in _SUVAT_UNKNOWN_RES if rx.search(cleaned)),
        None,
    )
    if unknown is None:
        return None

    params: dict[str, float] = {}
    units: dict[str, str] = {}

    # --- the two velocities, bound by written order -------------------------
    # "from 10 m/s to 30 m/s" reads left to right; a stated rest state at
    # either end fills the slot that has no number of its own.
    velocities = _ordered_values(cleaned, _VELOCITY_UNIT_PATTERN)
    starts_at_rest = _AT_REST_START_RE.search(cleaned) is not None
    ends_at_rest = _AT_REST_END_RE.search(cleaned) is not None

    if starts_at_rest:
        params["u"], units["u"] = 0.0, "m/s"
        if velocities:
            params["v"], units["v"] = velocities[0]
    elif ends_at_rest:
        params["v"], units["v"] = 0.0, "m/s"
        if velocities:
            params["u"], units["u"] = velocities[0]
    elif velocities:
        params["u"], units["u"] = velocities[0]
        if len(velocities) > 1:
            params["v"], units["v"] = velocities[1]

    # --- acceleration -------------------------------------------------------
    # "decelerates at 4 m/s^2" states a magnitude and a direction separately;
    # the sign lives in the word, not the number.
    accel = _find_value_with_specific_unit(
        cleaned,
        r"m/s\^?2|m/s2",
        ("acceleration", "accelerates", "accelerating", "deceleration", "decelerates", "rate"),
    )
    if accel is not None:
        value, unit = accel
        if _DECELERATION_RE.search(cleaned) and value > 0:
            value = -value
        params["a"], units["a"] = value, unit or "m/s^2"

    # --- time and distance --------------------------------------------------
    times = _ordered_values(cleaned, _SUVAT_TIME_UNITS)
    if times:
        params["t"], units["t"] = times[0]
    distances = _ordered_values(cleaned, _LENGTH_UNIT_PATTERN)
    if distances:
        params["d"], units["d"] = distances[0]

    # The unknown must not also be a given, and three of the other four are
    # needed to reach it — every SUVAT equation relates exactly four variables.
    wanted = {
        "suvat_velocity": "v",
        "suvat_distance": "d",
        "suvat_time": "t",
        "suvat_acceleration": "a",
    }[unknown]
    params.pop(wanted, None)
    units.pop(wanted, None)
    if len(params) < 3:
        return None

    return MathIntent(
        kind="suvat",
        physics_op=unknown,  # type: ignore[arg-type]
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
    # The launch-angle question has no angle to co-occur with — the angle is
    # what it is asking for — so the signature above cannot see it. A speed
    # beside an explicit ask for an angle is the signature instead.
    re.compile(
        r"\b(?:what|which)\s+(?:launch\s+)?angle\b.{0,80}?\d\s*(?:m/s|km/h|mph)\b"
        r"|\d\s*(?:m/s|km/h|mph)\b.{0,80}?\b(?:what|which)\s+(?:launch\s+)?angle\b",
        re.IGNORECASE,
    ),
)

# Phrasing -> op, first match wins. The shape is `_SUVAT_UNKNOWN_RES`, and so is
# the point of it: the ask is read from the question, and a question this table
# does not recognise is refused rather than answered with whatever came first.
#
# Before this, the op was an initializer — `op: Literal[...] = "range"` — so
# every unrecognised ask came back as a horizontal distance. "What is the time
# of flight of a ball thrown at 20 m/s at 30 degrees" answered `35.31 m`.
_PROJECTILE_UNKNOWN_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "max_height",
        re.compile(
            r"\bmax(?:imum)?\s+height\b|\bhow high\b|\bhighest point\b|\bpeak height\b"
            r"|\bapex\b|\bheight (?:does|it) (?:reach|rise)",
            re.IGNORECASE,
        ),
    ),
    (
        # A speed word AND a landing word, in either order. Either alone is a
        # different question: the speed alone is the given it was thrown at,
        # and the landing alone is the time of flight below.
        "impact_speed",
        re.compile(
            r"(?:\bhow fast\b|\bspeed\b|\bvelocity\b).{0,60}?"
            r"(?:\bland\w*\b|\bimpact\b|\bhits?\b|\bstrikes?\b|\btouch(?:es)? down\b)"
            r"|(?:\bland\w*\b|\bimpact\b|\bhits?\b|\bstrikes?\b|\btouch(?:es)? down\b).{0,60}?"
            r"(?:\bhow fast\b|\bspeed\b|\bvelocity\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "time_of_flight",
        re.compile(
            r"\btime of flight\b|\bflight time\b|\bhow long\b|\bhow much time\b"
            r"|\btime (?:in|it spends in) the air\b|\btime (?:to|before) (?:it )?lands?\b",
            re.IGNORECASE,
        ),
    ),
    (
        # Before `range` — this phrasing says "range" itself ("what launch angle
        # gives a range of 35 m"), and there the range is the given.
        "launch_angle",
        re.compile(r"\b(?:what|which)\s+(?:launch\s+)?angle\b|\blaunch angle\b", re.IGNORECASE),
    ),
    (
        "range",
        re.compile(
            r"\brange\b|\bhow far\b|\bhorizontal distance\b|\btrajectory\b"
            r"|\bdistance (?:does|it)\b|\bhow much ground\b",
            re.IGNORECASE,
        ),
    ),
)

# Where the range is the given rather than the answer (the launch-angle case).
_RANGE_GIVEN_KEYWORDS = ("range", "travel", "reach", "cover", "land", "distance", "far")


def _extract_projectile_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _PROJECTILE_CUES, _PROJECTILE_CUE_RES):
        return None
    # A collision is not a projectile, whatever units it carries. The signature
    # cue above is "a speed and an angle in one clause" — which a 2D collision
    # also satisfies, and this extractor runs first. Without this guard,
    # "a 2 kg ball at 3 m/s hits a 1 kg ball at rest ... at 30 degrees" was
    # answered 0.79 m: the range of a ball lobbed at 3 m/s.
    if _COLLISION_SUBJECT_RE.search(cleaned):
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

    if v0 is None:
        return None

    # What is being asked decides which givens are required, so it is read
    # before the angle gate below: the launch-angle question has no angle in it
    # by definition.
    op = next((name for name, rx in _PROJECTILE_UNKNOWN_RES if rx.search(cleaned)), None)
    if op is None:
        return None

    g = _detect_gravity(cleaned)
    angle_unit = "rad" if re.search(r"\b(?:rad|radians)\b", lower) else "deg"

    if op == "launch_angle":
        # The range is the given here and the angle is the answer, so an angle
        # in the text would make the question self-contradictory.
        if angle is not None:
            return None
        ru = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, _RANGE_GIVEN_KEYWORDS, require_keyword=True
        )
        if ru is None:
            return None
        return MathIntent(
            kind="projectile",
            physics_op=op,  # type: ignore[arg-type]
            physics_params={"v0": v0, "d": ru[0], "g": g},
            physics_units={"v0": v0_unit or "m/s", "d": ru[1] or "m", "g": "m/s^2"},
            operation="solve",
        )

    if angle is None:
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

    params: dict[str, float] = {"v0": v0, "angle": angle, "g": g}
    units: dict[str, str] = {"v0": v0_unit or "m/s", "angle": angle_unit, "g": "m/s^2"}
    if h0 is not None:
        params["h0"] = h0
        units["h0"] = h0_unit or "m"
    return MathIntent(
        kind="projectile",
        physics_op=op,  # type: ignore[arg-type]
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

# A question about bodies colliding, whatever units it happens to carry. Used
# by the momentum extractor to find its own work, and by the projectile
# extractor to stay out of it.
# A body landing is not a collision between two bodies. "hit" and "strike" are
# the words for both, so without this exception "how fast does it hit the
# ground" tripped P11's projectile guard and the question got no answer at all
# — a projectile is the one thing it could not be read as.
_LANDING_TARGET = r"ground|floor|water|sea|surface|deck|earth|soil|sand|roof"
_COLLISION_SUBJECT_RE = re.compile(
    r"\bcollision\b|\bcollides?\b|\bcolliding\b|\brecoils?\b"
    rf"|\bhits?\b(?!\s+the\s+(?:{_LANDING_TARGET})\b)"
    rf"|\bstrikes?\b(?!\s+the\s+(?:{_LANDING_TARGET})\b)"
    r"|sticks? together|stuck together",
    re.IGNORECASE,
)

# 2D only ever means "not solved here": conservation is implemented in 1D.
#
# The last alternative is a bare angle, and it is read only from inside the
# collision branch, where an angle has nowhere innocent to belong: a head-on
# collision has no angle to state, so any number of degrees present is the
# deflection this solver cannot do. It is listed because the commonest 2D
# phrasing — "collides with a 1 kg ball at 30 degrees" — carries no 2D word at
# all, and without it the guard above catches the wording and misses the case.
_TWO_DIMENSIONAL_RE = re.compile(
    r"\b2-?d\b|\btwo[- ]dimensional\b|\bdeflect(?:s|ed|ion)?\b"
    r"|\bat an angle\b|\bglancing\b|\boblique\b"
    r"|\d\s*(?:degrees?|deg|°)",
    re.IGNORECASE,
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
            rf"({_NUMBER})\s*({unit_pattern})(?![A-Za-z0-9/^])",
            text,
            re.IGNORECASE,
        )
    ]


def _positioned_values(text: str, unit_pattern: str) -> list[tuple[int, float, str]]:
    """Like ``_ordered_values`` but keeps each match's offset.

    Torque balance needs to know *which* force a distance belongs to, which
    written order alone cannot say.
    """
    return [
        (m.start(), float(m.group(1)), m.group(2))
        for m in re.finditer(
            rf"({_NUMBER})\s*({unit_pattern})(?![A-Za-z0-9/^])",
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
        _COLLISION_SUBJECT_RE.search(cleaned) is not None or _INELASTIC_RE.search(lower) is not None
    )

    # --- 1D collision: two masses, at least one velocity ---
    if is_collision and len(masses) >= 2:
        # Only 1D conservation is implemented. Handing back the 1D number for a
        # 2D question is the same defect as the projectile answer it replaces,
        # just less obvious — the arithmetic is right for a problem nobody asked.
        if _TWO_DIMENSIONAL_RE.search(cleaned):
            return None
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
_FRICTION_GIVEN = r"coefficient|\bmu\s*(?:=|is)|\u03bc\s*(?:=|is)|\d+\s*(?:degrees?|deg|\u00b0)"
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
    r"|\bmu\s+is\s+|\bmu\s*=\s*|\u03bc\s+is\s+|\u03bc\s*=\s*)"
    r"(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
# Asking *for* the coefficient, rather than being given one. "coefficient" is
# algebra's word too, so the friction cue tables above still gate this.
_MU_ASK_RE = re.compile(
    r"(?:what|find|calculate|determine|compute)\b[^.?!]{0,40}?"
    r"\bcoefficient\s+of\s+(?:kinetic\s+|static\s+)?friction\b"
    r"|\bcoefficient\s+of\s+(?:kinetic\s+|static\s+)?friction\s*\?",
    re.IGNORECASE,
)
# mu = tan(theta) is only true at the angle where motion begins.
_SLIPPING_RE = re.compile(
    r"\bstarts?\s+to\s+(?:slide|slip|move)\b|\bbegins?\s+to\s+(?:slide|slip|move)\b"
    r"|\bslipping\s+begins?\b|\bjust\s+(?:slides?|slips?|begins)\b"
    r"|\bslides?\s+(?:at|when|down\s+a)\b|\bon\s+the\s+point\s+of\b",
    re.IGNORECASE,
)
# The force that just overcomes static friction on the flat.
_MIN_FORCE_ASK_RE = re.compile(
    r"\bminimum\s+force\b|\bleast\s+force\b|\bsmallest\s+force\b"
    r"|\bforce\s+(?:is\s+)?(?:needed|required)\s+to\s+(?:start|move|push|pull|budge)\b"
    r"|\bforce\s+to\s+(?:start|move|push|pull|budge)\b",
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
    wants_coefficient = _MU_ASK_RE.search(cleaned) is not None
    wants_min_force = _MIN_FORCE_ASK_RE.search(cleaned) is not None

    op: Literal[
        "friction_force",
        "normal_force",
        "incline_acceleration",
        "friction_coefficient",
        "minimum_force",
    ]
    if wants_coefficient:
        # mu = tan(theta) holds only at the angle where it *starts* to slide.
        # On any other incline the angle says nothing about mu, so the slipping
        # wording is required rather than assumed.
        op = "friction_coefficient"
        if angle == 0.0 or mu is not None or not _SLIPPING_RE.search(cleaned):
            return None
    elif wants_min_force:
        op = "minimum_force"
        if mass is None or mu is None:
            return None
        if angle != 0.0:
            # On a slope the minimum force is mu*m*g*cos(t) + m*g*sin(t), a
            # different formula. Not solved here, so not guessed at either.
            return None
    elif wants_acceleration:
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

    params: dict[str, float] = {"angle": angle, "g": _detect_gravity(cleaned)}
    units: dict[str, str] = {
        "angle": "rad" if re.search(r"\b(?:rad|radians)\b", lower) else "deg",
        "g": "m/s^2",
    }
    # For `friction_coefficient` mu is the answer, not a given, so there is
    # none to pass. Every other op has already refused a missing one above.
    if mu is not None:
        params["mu"] = mu
        units["mu"] = ""
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
# Waves
#   v = f lambda,  f = 1/T,  Doppler for a source approaching a still observer
# ---------------------------------------------------------------------------

# "wave" alone is a wave of layoffs and "frequency" is how often something
# happens, so neither is a cue. "wavelength" and "doppler" are unambiguous.
_WAVE_CUES = ("wavelength", "doppler", "sound wave", "light wave", "water wave")
_HERTZ_PATTERN = r"Hz|hertz|kHz|kilohertz|MHz|megahertz"
# A siren does not say "wave", and neither does a moving whistle. A frequency
# beside a sound source in motion is the Doppler signature itself.
_SOUND_SOURCE = r"siren|ambulance|police|horn|whistle|train|engine|speaker|source"
_WAVE_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(rf"\bwaves?\b.{{0,80}}?\d\s*(?:{_HERTZ_PATTERN})\b", re.IGNORECASE),
    re.compile(rf"\d\s*(?:{_HERTZ_PATTERN})\b.{{0,80}}?\bwaves?\b", re.IGNORECASE),
    re.compile(rf"\b(?:{_SOUND_SOURCE})\b.{{0,80}}?\d\s*(?:{_HERTZ_PATTERN})\b", re.IGNORECASE),
    re.compile(rf"\d\s*(?:{_HERTZ_PATTERN})\b.{{0,80}}?\b(?:{_SOUND_SOURCE})\b", re.IGNORECASE),
    # A wave stated by its period carries no Hz at all. The time unit has to
    # follow "period", so "a wave of layoffs over a 3 week period" cannot match
    # - it puts its number before the word, and weeks are not in the pattern.
    re.compile(
        r"\bwaves?\b.{0,80}?\bperiod\b\s*(?:of\s*)?\d+(?:\.\d+)?\s*"
        r"(?:seconds?|secs?|milliseconds?|ms|s)\b",
        re.IGNORECASE,
    ),
)

# Approaching and receding give different answers from identical numbers, so an
# unstated direction is refused rather than assumed - the shape P4 used for an
# unstated collision type.
_APPROACHING_RE = re.compile(
    r"\bapproach\w*\b|\btowards?\b|\bcoming\s+(?:at|toward)\b|\bnearing\b", re.IGNORECASE
)
_RECEDING_RE = re.compile(
    r"\breced\w*\b|\baway\s+from\b|\bmoving\s+away\b|\bdeparting\b", re.IGNORECASE
)
# 343 m/s at 20 C. Stated in the answer, because 340 is taught just as often.
_SPEED_OF_SOUND = 343.0


def _extract_waves_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _WAVE_CUES, _WAVE_CUE_RES):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    freq = _find_value_with_specific_unit(cleaned, _HERTZ_PATTERN)
    wavelength = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("wavelength",), require_keyword=True
    )
    speed = _find_value_with_specific_unit(cleaned, _VELOCITY_UNIT_PATTERN)
    period = _find_value_with_specific_unit(
        cleaned, _SHM_TIME_UNITS, ("period",), require_keyword=True
    )

    moving_source = re.search(rf"\b(?:{_SOUND_SOURCE})\b", lower) is not None
    if "doppler" in lower or (freq is not None and speed is not None and moving_source):
        approaching = _APPROACHING_RE.search(cleaned) is not None
        receding = _RECEDING_RE.search(cleaned) is not None
        if freq is None or speed is None or approaching == receding:
            return None
        return MathIntent(
            kind="waves",
            physics_op="doppler_frequency",
            physics_params={
                "freq": freq[0],
                "v_src": speed[0] if approaching else -speed[0],
                "v_sound": _SPEED_OF_SOUND,
            },
            physics_units={"freq": freq[1] or "Hz", "v_src": "m/s", "v_sound": "m/s"},
            operation="solve",
        )

    # f = 1/T and T = 1/f, whichever of the pair is missing.
    if period is not None and freq is None:
        return MathIntent(
            kind="waves",
            physics_op="wave_frequency_from_period",
            physics_params={"period": period[0]},
            physics_units={"period": period[1] or "s"},
            operation="solve",
        )
    if freq is not None and wavelength is None and speed is None and "period" in lower:
        return MathIntent(
            kind="waves",
            physics_op="wave_period",
            physics_params={"freq": freq[0]},
            physics_units={"freq": freq[1] or "Hz"},
            operation="solve",
        )

    # v = f lambda, solved for whichever of the three is absent.
    given = {
        "freq": freq,
        "wavelength": wavelength,
        "v_wave": speed,
    }
    present = {key: value for key, value in given.items() if value is not None}
    if len(present) != 2:
        return None
    missing = ({"freq", "wavelength", "v_wave"} - set(present)).pop()
    op = {
        "freq": "wave_frequency",
        "wavelength": "wavelength",
        "v_wave": "wave_speed",
    }[missing]
    defaults = {"freq": "Hz", "wavelength": "m", "v_wave": "m/s"}
    return MathIntent(
        kind="waves",
        physics_op=op,  # type: ignore[arg-type]
        physics_params={key: value[0] for key, value in present.items()},
        physics_units={key: (value[1] or defaults[key]) for key, value in present.items()},
        operation="solve",
    )


# ---------------------------------------------------------------------------
# Optics
#   1/f = 1/u + 1/v,  m = v/u,  n1 sin(t1) = n2 sin(t2),  sin(tc) = 1/n
# ---------------------------------------------------------------------------

# "lens", "focus" and "image" are all ordinary English; the multi-word forms
# are not.
_OPTICS_CUES = (
    "focal length",
    "refractive index",
    "critical angle",
    "index of refraction",
    "converging lens",
    "convex lens",
    "magnification",
    "snell",
)

# Sign conventions disagree between textbooks for exactly the interesting
# cases, so only the one every convention agrees on is solved: a converging
# lens forming a real image. A diverging lens, or an object inside the focal
# length, is refused rather than answered with a sign the reader may not share.
_DIVERGING_RE = re.compile(
    r"\bdiverging\b|\bconcave\s+lens\b|\bvirtual\s+image\b|\bnegative\s+focal\b",
    re.IGNORECASE,
)


def _extract_optics_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _OPTICS_CUES):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None
    if _DIVERGING_RE.search(cleaned):
        return None

    index_values = [
        float(m.group(1))
        for m in re.finditer(
            r"(?:refractive\s+index|index\s+of\s+refraction)\s*(?:of|is|=)?\s*"
            r"(-?\d+(?:\.\d+)?)",
            cleaned,
            re.IGNORECASE,
        )
    ]
    angles = [float(m.group(1)) for m in _INCLINE_ANGLE_RE.finditer(cleaned)]
    if len(angles) < 2:
        # "bends from 30 to 20 degrees" puts the unit on the second angle only,
        # so the scan above sees one number where the question gave two.
        pair = re.search(
            r"from\s+(-?\d+(?:\.\d+)?)\s*(?:degrees?|deg|\u00b0)?\s*to\s+"
            r"(-?\d+(?:\.\d+)?)\s*(?:degrees?|deg|\u00b0)",
            cleaned,
            re.IGNORECASE,
        )
        if pair is not None:
            angles = [float(pair.group(1)), float(pair.group(2))]

    if "critical angle" in lower:
        if len(index_values) != 1 or index_values[0] <= 1:
            return None
        return MathIntent(
            kind="optics",
            physics_op="critical_angle",
            physics_params={"n1": index_values[0]},
            physics_units={"n1": ""},
            operation="solve",
        )

    if "refractive index" in lower or "index of refraction" in lower or "snell" in lower:
        # n = sin(t1) / sin(t2) when both angles are given and the index is not.
        if len(angles) == 2 and not index_values:
            return MathIntent(
                kind="optics",
                physics_op="refractive_index",
                physics_params={"angle": angles[0], "angle2": angles[1]},
                physics_units={"angle": "deg", "angle2": "deg"},
                operation="solve",
            )
        return None

    focal = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("focal length", "focal"), require_keyword=True
    )
    obj = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("object",), require_keyword=True
    )
    if "magnification" in lower:
        img = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("image",), require_keyword=True
        )
        if img is None or obj is None:
            return None
        return MathIntent(
            kind="optics",
            physics_op="magnification",
            physics_params={"h_img": img[0], "h_obj": obj[0]},
            physics_units={"h_img": img[1] or "m", "h_obj": obj[1] or "m"},
            operation="solve",
        )

    if focal is None or obj is None:
        return None
    return MathIntent(
        kind="optics",
        physics_op="image_distance",
        physics_params={"focal": focal[0], "d_obj": obj[0]},
        physics_units={"focal": focal[1] or "m", "d_obj": obj[1] or "m"},
        operation="solve",
    )


# ---------------------------------------------------------------------------
# Thermal
#   Q = m c dT,  P V = n R T,  efficiency = W_out / Q_in
# ---------------------------------------------------------------------------

# "heat", "gas" and "efficiency" are all ordinary English, so the cues are the
# multi-word forms and a signature.
_THERMAL_CUES = ("specific heat", "heat capacity", "ideal gas", "gas constant")
_KELVIN_PATTERN = r"K|kelvins?"
_CELSIUS_PATTERN = r"°C|degrees?\s+c(?:elsius)?|celsius"
_THERMAL_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"\b(?:heat|warm|cool)\w*\b.{{0,80}}?\d\s*(?:{_KELVIN_PATTERN}|{_CELSIUS_PATTERN})",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\d\s*(?:{_KELVIN_PATTERN}|{_CELSIUS_PATTERN}).{{0,80}}?\b(?:heat|warm|cool)\w*\b",
        re.IGNORECASE,
    ),
    re.compile(r"\befficiency\b.{0,80}?\d\s*(?:J|joules?|kJ|kilojoules?)\b", re.IGNORECASE),
    re.compile(r"\d\s*(?:J|joules?|kJ|kilojoules?)\b.{0,80}?\befficiency\b", re.IGNORECASE),
)

# 4186 J/kg/K. Only used when the substance is named water and no capacity is
# given; any other substance must state its own.
_WATER_SPECIFIC_HEAT = 4186.0
_GAS_CONSTANT = 8.314462618


def _temperature_value(cleaned: str, keywords: tuple[str, ...]) -> tuple[float, str] | None:
    """A temperature with an explicit scale, or nothing.

    27 C and 27 K differ by a factor of eleven, so a bare number is refused
    rather than assumed - and "degrees" alone cannot help, because it means an
    *angle* everywhere else in this file.
    """
    kelvin = _find_value_with_specific_unit(cleaned, _KELVIN_PATTERN, keywords)
    if kelvin is not None:
        return kelvin[0], "K"
    match = re.search(
        rf"(-?\d+(?:\.\d+)?)\s*(?:{_CELSIUS_PATTERN})",
        cleaned,
        re.IGNORECASE,
    )
    if match is not None:
        return float(match.group(1)), "degC"
    return None


def _extract_thermal_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _THERMAL_CUES, _THERMAL_CUE_RES):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    # --- efficiency: only from two energies -----------------------------
    if "efficiency" in lower:
        energies = _ordered_values(cleaned, r"kilojoules?|joules?|kJ|J")
        if len(energies) != 2:
            # Two temperatures is a Carnot question, which needs absolute
            # temperatures and a different formula. Not solved here.
            return None
        work, supplied = sorted((energies[0][0], energies[1][0]))
        if supplied <= 0:
            return None
        return MathIntent(
            kind="thermal",
            physics_op="thermal_efficiency",
            physics_params={"W_out": work, "Q_in": supplied},
            physics_units={"W_out": "J", "Q_in": "J"},
            operation="solve",
        )

    # --- ideal gas: P V = n R T -----------------------------------------
    moles = _find_value_with_specific_unit(cleaned, r"mol|moles?")
    if moles is not None or "ideal gas" in lower:
        volume = _find_value_with_specific_unit(cleaned, r"m\^?3|cm\^?3|litres?|liters?|l|ml")
        temp = _temperature_value(cleaned, ("temperature", "at"))
        if moles is None or volume is None or temp is None:
            return None
        if temp[1] != "K":
            # PV = nRT needs an absolute temperature. Celsius would be wrong by
            # 273 and look plausible.
            return None
        return MathIntent(
            kind="thermal",
            physics_op="ideal_gas_pressure",
            physics_params={"moles": moles[0], "volume": volume[0], "temp": temp[0]},
            physics_units={
                "moles": "mol",
                "volume": volume[1] or "m^3",
                "temp": "K",
            },
            operation="solve",
        )

    # --- Q = m c dT ------------------------------------------------------
    mass = _find_value_with_specific_unit(cleaned, _MASS_UNITS, ("mass", "of"))
    rise = _temperature_value(cleaned, ("by", "rise", "raise", "change"))
    if mass is None or rise is None:
        return None
    capacity = _find_value_with_specific_unit(
        cleaned, r"J/kg/K|J/\(kg\s*K\)|J/kgK", ("specific heat", "capacity")
    )
    if capacity is not None:
        c_value = capacity[0]
    elif "water" in lower:
        c_value = _WATER_SPECIFIC_HEAT
    else:
        # No capacity and no named substance: the answer would be a guess.
        return None
    # A temperature *difference* is the same number in kelvin and celsius, so
    # this one does not need the scale the absolute reading above does.
    return MathIntent(
        kind="thermal",
        physics_op="heat_energy",
        physics_params={"m": mass[0], "c_heat": c_value, "delta_temp": rise[0]},
        physics_units={"m": mass[1] or "kg", "c_heat": "J/kg/K", "delta_temp": "K"},
        operation="solve",
    )


# ---------------------------------------------------------------------------
# Gravitation
#   F = G M m / r^2,  v_orb = sqrt(GM/r),  v_esc = sqrt(2GM/R),  g = GM/R^2
# ---------------------------------------------------------------------------

# "gravity" alone is the gravity of a situation, and "mass" is a mass email, so
# neither is a cue. Every entry here is unambiguous gravitation vocabulary.
_GRAVITATION_CUES = (
    "gravitational force",
    "gravitational constant",
    "gravitational field",
    "orbital velocity",
    "orbital speed",
    "escape velocity",
    "escape speed",
    "surface gravity",
    "newton's law of gravitation",
    "law of universal gravitation",
)
_GRAVITATION_CUE_RES: tuple[re.Pattern[str], ...] = (
    # "the force between two 1000 kg masses 10 m apart" names no topic word.
    re.compile(r"\bforce\s+between\b.{0,80}?\d\s*(?:kg|tonnes?|tons?)\b", re.IGNORECASE),
    re.compile(r"\bg\s+on\s+a\s+planet\b", re.IGNORECASE),
)

# Earth and the Moon are not in Pint, and a question that says "from earth"
# supplies neither mass nor radius. Resolving the body here rather than in the
# solver keeps the substitution visible in the answer.
#   IAU / CODATA nominal values.
_BODY_PROPERTIES: dict[str, tuple[float, float]] = {
    "earth": (5.9722e24, 6.371e6),
    "moon": (7.342e22, 1.7374e6),
    "mars": (6.4171e23, 3.3895e6),
    "jupiter": (1.8982e27, 6.9911e7),
    "sun": (1.9885e30, 6.957e8),
}


# "two 1000 kg masses", "a pair of 5 kg spheres" - one number, two bodies.
_IDENTICAL_PAIR_RE = re.compile(
    r"\b(?:two|a\s+pair\s+of|both)\b[^.?!]{0,40}?"
    r"\b(?:masses|spheres|balls|objects|bodies|blocks|stars|planets)\b",
    re.IGNORECASE,
)


def _named_body(lower: str) -> tuple[float, float] | None:
    for name, properties in _BODY_PROPERTIES.items():
        if word_index(lower, name) != -1:
            return properties
    return None


def _extract_gravitation_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _GRAVITATION_CUES, _GRAVITATION_CUE_RES):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    body = _named_body(lower)
    masses = _ordered_values(cleaned, r"kg|tonnes?|tons?")
    radius = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("radius", "radii"), require_keyword=True
    )
    altitude = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("above", "altitude", "height"), require_keyword=True
    )
    separation = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("apart", "separation", "between", "distance")
    )

    if "escape" in lower:
        planet_mass, planet_radius = _resolve_body(body, masses, radius)
        if planet_mass is None or planet_radius is None:
            return None
        return MathIntent(
            kind="gravitation",
            physics_op="escape_velocity",
            physics_params={"M": planet_mass, "radius_body": planet_radius},
            physics_units={"M": "kg", "radius_body": "m"},
            operation="solve",
        )

    if "orbital" in lower:
        planet_mass, planet_radius = _resolve_body(body, masses, radius)
        if planet_mass is None or planet_radius is None:
            return None
        # An orbit is measured from the centre, so an altitude adds to the
        # radius - but the two are rarely in the same unit ("400 km above the
        # earth"), so they are passed separately and added after `_to_si`
        # rather than summed here in whatever units they arrived in.
        params: dict[str, float] = {"M": planet_mass, "radius_body": planet_radius}
        units: dict[str, str] = {"M": "kg", "radius_body": "m"}
        if altitude is not None:
            params["altitude"] = altitude[0]
            units["altitude"] = altitude[1] or "m"
        return MathIntent(
            kind="gravitation",
            physics_op="orbital_velocity",
            physics_params=params,
            physics_units=units,
            operation="solve",
        )

    if "surface gravity" in lower or "gravitational field" in lower or "g on a planet" in lower:
        planet_mass, planet_radius = _resolve_body(body, masses, radius)
        if planet_mass is None or planet_radius is None:
            return None
        return MathIntent(
            kind="gravitation",
            physics_op="surface_gravity",
            physics_params={"M": planet_mass, "radius_body": planet_radius},
            physics_units={"M": "kg", "radius_body": "m"},
            operation="solve",
        )

    # F = G M m / r^2 between two stated masses. "two 1000 kg masses" gives one
    # number for both bodies, which is the commonest wording of this question.
    if len(masses) == 1 and separation is not None and _IDENTICAL_PAIR_RE.search(cleaned):
        masses = [masses[0], masses[0]]
    if len(masses) >= 2 and separation is not None:
        return MathIntent(
            kind="gravitation",
            physics_op="gravitational_force",
            physics_params={"m1": masses[0][0], "m2": masses[1][0], "r": separation[0]},
            physics_units={
                "m1": masses[0][1] or "kg",
                "m2": masses[1][1] or "kg",
                "r": separation[1] or "m",
            },
            operation="solve",
        )
    return None


def _resolve_body(
    body: tuple[float, float] | None,
    masses: list[tuple[float, str]],
    radius: tuple[float, str] | None,
) -> tuple[float | None, float | None]:
    """A named body, or a stated mass and radius - never a mix of guesses.

    A question that *describes* a planet without naming it and supplies only
    one of the two is refused: silently finishing it with Earth's other number
    is the same defect as the projectile default, one layer up.
    """
    if body is not None:
        return body
    if masses and radius is not None:
        return masses[0][0], radius[0]
    return None, None


# ---------------------------------------------------------------------------
# Fluids
#   P = F/A,  P = rho g h,  upthrust = rho V g,  rho = m/V,  A1 v1 = A2 v2
# ---------------------------------------------------------------------------

# "pressure" is what deadlines apply and "flow" is what cash does, so both are
# co-occurrence only. "upthrust" and "archimedes" are unambiguous.
_FLUIDS_CUES = (
    "upthrust",
    "buoyant force",
    "buoyancy",
    "archimedes",
    "hydrostatic",
    "flow rate",
    "pascal's principle",
)
_AREA_PATTERN = r"m\^?2|cm\^?2|mm\^?2|square\s+met(?:er|re)s?"
_VOLUME_PATTERN = r"m\^?3|cm\^?3|litres?|liters?|ml"
_DENSITY_PATTERN = r"kg/m\^?3|g/cm\^?3|kg\s+per\s+cubic\s+met(?:er|re)"
_PRESSURE_PATTERN = r"Pa|pascals?|kPa|kilopascals?|MPa|megapascals?"
_FLUIDS_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"\bpressure\b.{{0,80}}?\d\s*(?:{_AREA_PATTERN}|{_PRESSURE_PATTERN})\b", re.IGNORECASE
    ),
    re.compile(
        rf"\d\s*(?:{_AREA_PATTERN}|{_PRESSURE_PATTERN})\b.{{0,80}}?\bpressure\b", re.IGNORECASE
    ),
    re.compile(r"\bpressure\b.{0,80}?\bdepth\b", re.IGNORECASE),
    re.compile(rf"\bdensity\b.{{0,80}}?\d\s*(?:{_VOLUME_PATTERN})\b", re.IGNORECASE),
    re.compile(rf"\d\s*(?:{_DENSITY_PATTERN})\b", re.IGNORECASE),
    re.compile(rf"\bpipe\b.{{0,80}}?\d\s*(?:{_AREA_PATTERN})\b", re.IGNORECASE),
)

# Stress is the same F/A. The materials kind owns that vocabulary and runs
# first; refusing it here keeps the two from ever both answering.
_STRESS_WORDS = ("stress", "strain", "young", "modulus", "tensile")
# Depth pressure is *gauge* unless the question says otherwise, and a question
# that says "absolute" wants atmospheric added - a different number.
_ABSOLUTE_PRESSURE_RE = re.compile(r"\babsolute\b|\batmospheric\b", re.IGNORECASE)
_WATER_DENSITY = 1000.0


def _extract_fluids_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _FLUIDS_CUES, _FLUIDS_CUE_RES):
        return None
    if any(word in lower for word in _STRESS_WORDS):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    area = _find_value_with_specific_unit(cleaned, _AREA_PATTERN)
    volume = _find_value_with_specific_unit(cleaned, _VOLUME_PATTERN)
    mass = _find_value_with_specific_unit(cleaned, _MASS_UNITS, ("mass", "of"))
    force = _find_value_with_specific_unit(cleaned, r"N|newtons?", ("force", "weight"))
    depth = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("depth", "deep", "below", "down"), require_keyword=True
    )
    density = _find_value_with_specific_unit(cleaned, _DENSITY_PATTERN)
    speed = _ordered_values(cleaned, _VELOCITY_UNIT_PATTERN)
    areas = _ordered_values(cleaned, _AREA_PATTERN)

    def _fluid_density() -> float | None:
        if density is not None:
            return density[0]
        if "water" in lower:
            return _WATER_DENSITY
        return None

    # --- continuity: A1 v1 = A2 v2 --------------------------------------
    if len(areas) >= 2 and speed:
        if areas[1][0] == 0:
            return None
        return MathIntent(
            kind="fluids",
            physics_op="continuity_velocity",
            physics_params={"A1": areas[0][0], "A2": areas[1][0], "v": speed[0][0]},
            physics_units={
                "A1": areas[0][1] or "m^2",
                "A2": areas[1][1] or "m^2",
                "v": speed[0][1] or "m/s",
            },
            operation="solve",
        )

    # --- flow rate: Q = A v ---------------------------------------------
    if "flow" in lower and area is not None and speed:
        return MathIntent(
            kind="fluids",
            physics_op="flow_rate",
            physics_params={"area": area[0], "v": speed[0][0]},
            physics_units={"area": area[1] or "m^2", "v": speed[0][1] or "m/s"},
            operation="solve",
        )

    # --- upthrust: rho V g ----------------------------------------------
    if any(word in lower for word in ("upthrust", "buoyan", "archimedes")):
        rho = _fluid_density()
        if volume is None or rho is None:
            return None
        if "submerged" not in lower and "immersed" not in lower:
            # A floating body displaces its own weight, not its own volume.
            # Which one is meant changes the answer, so it has to be said.
            return None
        return MathIntent(
            kind="fluids",
            physics_op="upthrust",
            physics_params={"rho": rho, "volume": volume[0], "g": _detect_gravity(cleaned)},
            physics_units={"rho": "kg/m^3", "volume": volume[1] or "m^3", "g": "m/s^2"},
            operation="solve",
        )

    # --- pressure at depth: rho g h -------------------------------------
    if depth is not None:
        if _ABSOLUTE_PRESSURE_RE.search(cleaned):
            return None
        rho = _fluid_density()
        if rho is None:
            return None
        return MathIntent(
            kind="fluids",
            physics_op="pressure_at_depth",
            physics_params={"rho": rho, "depth": depth[0], "g": _detect_gravity(cleaned)},
            physics_units={"rho": "kg/m^3", "depth": depth[1] or "m", "g": "m/s^2"},
            operation="solve",
        )

    # --- density: rho = m / V -------------------------------------------
    if "density" in lower and mass is not None and volume is not None:
        return MathIntent(
            kind="fluids",
            physics_op="density",
            physics_params={"m": mass[0], "volume": volume[0]},
            physics_units={"m": mass[1] or "kg", "volume": volume[1] or "m^3"},
            operation="solve",
        )

    # --- pressure from a force: P = F / A --------------------------------
    if force is not None and area is not None:
        return MathIntent(
            kind="fluids",
            physics_op="pressure_from_force",
            physics_params={"F": force[0], "area": area[0]},
            physics_units={"F": force[1] or "N", "area": area[1] or "m^2"},
            operation="solve",
        )
    return None


# ---------------------------------------------------------------------------
# Rotation
#   omega = theta/t,  I = k m r^2,  L = I omega,  KE = 1/2 I omega^2
# ---------------------------------------------------------------------------

# P9 refused "moment of inertia" on the torque kind because it was not solved.
# It is solved here now, and torque still refuses it - that refusal is what
# stops *torque* claiming it, and this extractor runs afterwards to pick up the
# fall-through.
_ROTATION_CUES = (
    "moment of inertia",
    "rotational inertia",
    "angular momentum",
    "rotational kinetic energy",
    "angular acceleration",
)
_INERTIA_PATTERN = r"kg\s*m\^?2|kg\s*\*\s*m\^?2|kilogram\s+met(?:er|re)\s+squared"
_ROTATION_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(rf"\d\s*(?:{_INERTIA_PATTERN})", re.IGNORECASE),
    re.compile(r"\bangular\s+(?:velocity|speed)\b.{0,80}?\d\s*(?:radians?|rad)\b", re.IGNORECASE),
    re.compile(r"\d\s*(?:radians?|rad)\b.{0,80}?\bangular\s+(?:velocity|speed)\b", re.IGNORECASE),
)

# I = k m r^2, and k is the *shape*. A "wheel" or an "object" is not a shape,
# and answering one with the disc constant is a confidently wrong number - so
# the shape has to be named, and a rod has to name its axis too.
_INERTIA_SHAPES: dict[str, tuple[float, str]] = {
    "hoop": (1.0, "m r^2"),
    "ring": (1.0, "m r^2"),
    "cylindrical shell": (1.0, "m r^2"),
    "disc": (0.5, r"\tfrac{1}{2} m r^2"),
    "disk": (0.5, r"\tfrac{1}{2} m r^2"),
    "solid cylinder": (0.5, r"\tfrac{1}{2} m r^2"),
    "solid sphere": (0.4, r"\tfrac{2}{5} m r^2"),
    "hollow sphere": (2 / 3, r"\tfrac{2}{3} m r^2"),
    "spherical shell": (2 / 3, r"\tfrac{2}{3} m r^2"),
}


def _extract_rotation_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _ROTATION_CUES, _ROTATION_CUE_RES):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    inertia = _find_value_with_specific_unit(cleaned, _INERTIA_PATTERN)
    omega = _ANGULAR_FREQ_RE.search(cleaned)
    mass = _find_value_with_specific_unit(cleaned, _MASS_UNITS, ("mass", "of"))
    radius = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("radius", "radii"), require_keyword=True
    )

    if "moment of inertia" in lower or "rotational inertia" in lower:
        shape = next(
            ((k, name) for name, (k, _) in _INERTIA_SHAPES.items() if name in lower),
            None,
        )
        formula = next((tex for name, (_, tex) in _INERTIA_SHAPES.items() if name in lower), None)
        if shape is None or formula is None or mass is None or radius is None:
            return None
        return MathIntent(
            kind="rotation",
            physics_op="moment_of_inertia",
            physics_params={"m": mass[0], "r": radius[0], "shape_factor": shape[0]},
            physics_units={"m": mass[1] or "kg", "r": radius[1] or "m", "shape_factor": ""},
            operation="solve",
        )

    if inertia is not None and omega is not None:
        op = (
            "rotational_kinetic_energy"
            if "kinetic energy" in lower or "rotational energy" in lower
            else "angular_momentum"
        )
        return MathIntent(
            kind="rotation",
            physics_op=op,  # type: ignore[arg-type]
            physics_params={"inertia": inertia[0], "omega": float(omega.group(1))},
            physics_units={"inertia": "kg*m^2", "omega": "rad/s"},
            operation="solve",
        )

    # omega = theta / t
    turned = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:radians?|rad)\b", cleaned, re.IGNORECASE)
    elapsed = _find_value_with_specific_unit(cleaned, r"seconds?|secs?|sec|s|minutes?|mins?|min")
    if turned is not None and elapsed is not None:
        return MathIntent(
            kind="rotation",
            physics_op="angular_velocity",
            physics_params={"theta": float(turned.group(1)), "t": elapsed[0]},
            physics_units={"theta": "rad", "t": elapsed[1] or "s"},
            operation="solve",
        )
    return None


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
#
# "angular" is never a cue by itself either - Angular the framework ships
# version numbers, so "angular 17 released 3 new features" would qualify. It
# counts beside the circle it is angular about.
_ANGULAR_ASK_RE = re.compile(r"\bangular\s+(?:velocity|speed|frequency)\b", re.IGNORECASE)
_CIRCULAR_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bperiod\b.{0,80}?\bradius\b", re.IGNORECASE),
    re.compile(r"\bradius\b.{0,80}?\bperiod\b", re.IGNORECASE),
    re.compile(
        r"\bangular\s+(?:velocity|speed)\b.{0,80}?\b(?:radius|circular|circle|track|orbit)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:radius|circular|circle|track|orbit)\b.{0,80}?\bangular\s+(?:velocity|speed)\b",
        re.IGNORECASE,
    ),
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

    op: Literal[
        "centripetal_force",
        "centripetal_acceleration",
        "orbital_period",
        "angular_velocity",
    ]
    if _ANGULAR_ASK_RE.search(cleaned):
        # Before "period": "angular frequency" contains neither word, but
        # "what angular velocity gives a period of 2 s" contains both.
        op = "angular_velocity"
    elif "period" in lower or "revolution" in lower:
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


# A pendulum is the same oscillation as a mass on a spring with a different
# period formula, so it emits the `spring` kind rather than one of its own.
#
# "pendulum" is physics-specific in a way "spring" and "moment" are not, but
# the idiom ("the pendulum has swung back") is real enough that the cue is a
# co-occurrence like P5's and P7's: the word beside an actual length.
_PENDULUM_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bpendulum\b.{0,80}?\d\s*(?:centimet(?:er|re)s?|met(?:er|re)s?|cm|m)\b", re.I),
    re.compile(r"\d\s*(?:centimet(?:er|re)s?|met(?:er|re)s?|cm|m)\b.{0,80}?\bpendulum\b", re.I),
)

# The period is the only pendulum quantity solved here, so the question has to
# be asking for it. "how long" is the spoken form and means time, not length —
# a pendulum's length is the given, never the ask.
_PENDULUM_PERIOD_RE = re.compile(
    r"\bperiod\b|\bhow long\b|\bswing\w*\b|\boscillat\w*\b|\btime\s+for\s+(?:one|a)\b",
    re.IGNORECASE,
)


def _extract_pendulum_intent(cleaned: str) -> MathIntent | None:
    if not _has_cue(cleaned.lower(), (), _PENDULUM_CUE_RES):
        return None
    if not _PENDULUM_PERIOD_RE.search(cleaned):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    length = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("pendulum", "length", "long", "string", "cord")
    )
    if length is None:
        return None

    params: dict[str, float] = {"L": length[0]}
    units: dict[str, str] = {"L": length[1] or "m"}
    gravity = _detect_gravity(cleaned)
    if gravity != _G_DEFAULT:
        params["g"], units["g"] = gravity, "m/s^2"
    return MathIntent(
        kind="spring",
        physics_op="pendulum_period",
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


# Frequency-from-period and maximum speed need neither a spring constant nor a
# pendulum length, so they fit neither extractor beside this one. They are the
# same simple harmonic motion, so they emit the `spring` kind as the pendulum
# does rather than inventing one.
#
# "frequency" and "period" are both ordinary English on their own ("the
# frequency of these outages", "a quiet period"), so each is required to appear
# beside the other or beside an oscillation word.
_SHM_FREQUENCY_RE = re.compile(
    r"\bfrequency\b.{0,80}?\bperiod\b|\bperiod\b.{0,80}?\bfrequency\b",
    re.IGNORECASE,
)
_SHM_MAX_SPEED_RE = re.compile(
    r"\b(?:max(?:imum)?|peak)\s+(?:speed|velocity)\b.{0,80}?\bamplitude\b"
    r"|\bamplitude\b.{0,80}?\b(?:max(?:imum)?|peak)\s+(?:speed|velocity)\b",
    re.IGNORECASE,
)
_SHM_CUE_RES: tuple[re.Pattern[str], ...] = (_SHM_FREQUENCY_RE, _SHM_MAX_SPEED_RE)

_SHM_TIME_UNITS = r"seconds?|secs?|sec|s|milliseconds?|ms|minutes?|mins?|min"
_ANGULAR_FREQ_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(?:rad(?:ians?)?\s*(?:/|per)\s*s(?:ec(?:ond)?s?)?)",
    re.IGNORECASE,
)


def _extract_shm_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, (), _SHM_CUE_RES):
        return None
    # f = 1/T is the same arithmetic for an oscillator and a wave, but the kind
    # should say which was asked about. Waves runs later, so defer explicitly.
    if "wave" in lower:
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    if _SHM_MAX_SPEED_RE.search(cleaned):
        amplitude = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("amplitude",), require_keyword=True
        )
        omega = _ANGULAR_FREQ_RE.search(cleaned)
        if amplitude is None or omega is None:
            return None
        return MathIntent(
            kind="spring",
            physics_op="shm_max_speed",
            physics_params={"x": amplitude[0], "omega": float(omega.group(1))},
            physics_units={"x": amplitude[1] or "m", "omega": "rad/s"},
            operation="solve",
        )

    period = _find_value_with_specific_unit(
        cleaned, _SHM_TIME_UNITS, ("period",), require_keyword=True
    )
    if period is None:
        return None
    return MathIntent(
        kind="spring",
        physics_op="shm_frequency",
        physics_params={"period": period[0]},
        physics_units={"period": period[1] or "s"},
        operation="solve",
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
)

_VOLT_PATTERN = r"V|volts?"
_AMP_PATTERN = r"A|amps?|amperes?"
_OHM_PATTERN = r"ohms?|\u03a9"

# Cue-side spellings: the symbol is uppercase-only, the word either case. The
# harvest patterns above are used with IGNORECASE and stay as they are.
_VOLT_CUE = r"V|[Vv]olts?"
_AMP_CUE = r"A|[Aa]mp(?:s|ere|eres)?"
_OHM_CUE = r"[Oo]hms?|\u03a9"


# A question can name no circuit *word* and still be one: "the electrical power
# for 12 V and 3 A" is entirely units. Two electrical quantities together are
# the signature - the same shape P2 used for the projectile's speed-and-angle.
#
# These were case-sensitive, to stop "3 a piece" reading as three amps. That
# was the right worry and the wrong mechanism: `needs_symbolic` lowercases
# before testing cues (math/match/needs.py:215-221), so a case-sensitive cue is
# *dead* in the pre-filter. Measured, the question above never reached
# extraction in production - `needs_symbolic` was False - while the extractor
# test passed, because the extractor re-runs these against the original casing.
#
# What makes lowercase safe is that a circuit signature names two *different*
# electrical quantities. A symbol can never pair with itself, so "3 a day ...
# 5 a day" and "the 5 v 5 format beats 3 v 3" cannot match, while "12 v and
# 3 a" does. Measured against a decoy set: this fires on 6/6 real circuit
# questions and 0/7 decoys, where plain re.IGNORECASE on the old patterns fired
# on 5 of those 7.
def _circuit_pair(first: str, second: str) -> re.Pattern[str]:
    """A number in `first`'s unit within 80 chars of a number in `second`'s.

    No IGNORECASE: the bare letters below are the SI symbols, and the spelled
    out forms carry their own case classes. `_has_cue_either_case` is what
    makes this reachable from the pre-filter.
    """
    return re.compile(rf"\d\s*(?:{first})(?![A-Za-z0-9]).{{0,80}}?\d\s*(?:{second})(?![A-Za-z0-9])")


# "charge" is what happens to a card and "energy" is what a person runs out of,
# so neither is a cue on its own. Each qualifies only beside the unit that
# makes it electrical - the co-occurrence shape P5 and P7 used.
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

_COULOMB_PATTERN = r"C|coulombs?"
_CIRCUIT_TIME_UNITS = r"seconds?|secs?|sec|s|minutes?|mins?|min|hours?|hrs?|hr|h"
# The EMF is the other answer to "what voltage", so the ask has to say which.
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


# A network's resistances are not always each given a unit. "4 ohms and 6 ohms"
# carries one per value, but "4 and 6 ohms" and "2, 3 and 6 ohms" carry one for
# the whole list, and `_ordered_values` sees only the first shape - so a
# two-resistor question written the second way returned no intent at all.
_RESISTOR_LIST_RE = re.compile(
    r"(\d+(?:\.\d+)?(?:\s*(?:,|and)\s*\d+(?:\.\d+)?)+)\s*(?:ohms?|\u03a9)",
    re.IGNORECASE,
)

# Each resistance needs a `_PARAM_SI_DIMENSIONS` entry, so the count is bounded.
# Beyond it the question is refused rather than answered from a prefix: reading
# three resistors and using two is how `2, 3 and 5 in series` answered 5 ohms.
_MAX_NETWORK_RESISTORS = 4


def _resistor_values(text: str) -> list[float]:
    """Every resistance in a network, however the units are distributed."""
    listed = _RESISTOR_LIST_RE.search(text)
    if listed is not None:
        return [float(n) for n in re.findall(r"\d+(?:\.\d+)?", listed.group(1))]
    return [value for value, _ in _ordered_values(text, _OHM_PATTERN)]


def _extract_circuit_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    # The same check the pre-filter runs, so the two cannot disagree about
    # whether this question is a circuit question.
    if not _has_cue_either_case(cleaned, _CIRCUIT_CUES, _CIRCUIT_CUE_RES):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    volts = _ordered_values(cleaned, _VOLT_PATTERN)
    amps = _ordered_values(cleaned, _AMP_PATTERN)
    ohms = _ordered_values(cleaned, _OHM_PATTERN)

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
        return MathIntent(
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
        return MathIntent(
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
        return MathIntent(
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
        return MathIntent(
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
        return MathIntent(
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
# Torque and rotational equilibrium
#   tau = F d (or F d sin(theta)),  balance: F1 d1 = F2 d2
# ---------------------------------------------------------------------------

# "moment" is ordinary English — "give me a moment", "at the moment" — so it is
# not a cue on its own. It qualifies only beside a pivot word, which is what the
# regex below requires. The rest are unambiguous mechanics vocabulary.
_TORQUE_CUES = (
    "torque",
    "pivot",
    "fulcrum",
    "lever arm",
    "see-saw",
    "seesaw",
)
_PIVOT_WORDS = r"pivot|fulcrum|lever|see-?saw|balance"
_TORQUE_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(rf"\bmoments?\b.{{0,80}}?(?:{_PIVOT_WORDS})", re.IGNORECASE),
    re.compile(rf"(?:{_PIVOT_WORDS}).{{0,80}}?\bmoments?\b", re.IGNORECASE),
)

# Moment of inertia is a different quantity (kg*m^2) and is not solved here.
_TORQUE_UNSUPPORTED = ("moment of inertia", "angular momentum", "rotational inertia")


def _extract_torque_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _TORQUE_CUES, _TORQUE_CUE_RES):
        return None
    if any(word in lower for word in _TORQUE_UNSUPPORTED):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    placed_forces = _positioned_values(cleaned, r"N")
    placed_distances = _positioned_values(cleaned, _LENGTH_UNIT_PATTERN)
    if not placed_forces or not placed_distances:
        return None

    # Two forces and one distance is the classic balance question. Pair the
    # distance with the force it actually belongs to rather than taking them in
    # written order: "the distance for a 10 N force to balance a 5 N force at
    # 2 m" mentions the 10 N first, but the 2 m is the *5 N* force's arm.
    # Written order answers 4 m there; the true answer is 1 m.
    balancing = "balance" in lower or "see-saw" in lower or "seesaw" in lower
    if balancing and len(placed_forces) >= 2:
        d_pos, d_val, d_unit = placed_distances[0]
        preceding = [f for f in placed_forces if f[0] < d_pos]
        # The force nearest *before* the distance owns it; the remaining force
        # is the one whose arm we are solving for.
        known = preceding[-1] if preceding else placed_forces[0]
        others = [f for f in placed_forces if f[0] != known[0]]
        if not others:
            return None
        unknown = others[0]
        return MathIntent(
            kind="torque",
            physics_op="moment_balance",
            physics_params={"F1": known[1], "d1": d_val, "F2": unknown[1]},
            physics_units={
                "F1": known[2] or "N",
                "d1": d_unit or "m",
                "F2": unknown[2] or "N",
            },
            operation="solve",
        )
    forces = [(f[1], f[2]) for f in placed_forces]
    distances = [(d[1], d[2]) for d in placed_distances]

    angle_match = _INCLINE_ANGLE_RE.search(cleaned)
    params: dict[str, float] = {"F": forces[0][0], "d": distances[0][0]}
    units: dict[str, str] = {"F": forces[0][1] or "N", "d": distances[0][1] or "m"}
    if angle_match:
        params["angle"] = float(angle_match.group(1))
        units["angle"] = "rad" if re.search(r"\b(?:rad|radians)\b", lower) else "deg"
    return MathIntent(
        kind="torque",
        physics_op="torque",
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


# ---------------------------------------------------------------------------
# Tension and Atwood machines
#   Hanging / accelerating mass:  T = m(g ± a)
#   Atwood pair:  a = (m1 - m2)g / (m1 + m2),  T = 2 m1 m2 g / (m1 + m2)
# ---------------------------------------------------------------------------
#
# P2 put `tension` and `pulley` into _UNSUPPORTED_FORCE_CONTEXT after finding
# "the tension supporting a 5 kg mass accelerating at 2 m/s^2" answered 10.00 N
# (m*a) when the answer is 59.05 N. That refusal was right and stays: this
# extractor runs *ahead* of force and claims only the two shapes below, so
# everything else still falls through to the refusal — P5's correction applied
# rather than the entries being deleted wholesale.

# "tension", a mass, and a word putting the rope vertical — all three, in any
# order, which is why these are lookaheads rather than one linear pattern.
#
# All three are needed because this tuple feeds the global needs_math_tools
# pre-filter. Dropping the third caught "find the tension in a 10 kg rope",
# which is a rope's own mass rather than a hanging load: nothing here can
# answer it, and an existing pre-filter test said so before this shipped.
_TENSION_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?=.*\btension\b)(?=.*\d\s*(?:kg|lbs?|oz)\b)"
        r"(?=.*(?:lift|rais|hoist|hang|suspend|hold|support|lower|descend|elevator))",
        re.IGNORECASE | re.DOTALL,
    ),
    # An Atwood pair often never says "tension" at all.
    re.compile(r"\batwood\b", re.IGNORECASE),
    re.compile(r"\bpulley\b.{0,80}?\d\s*(?:kg|lbs?|oz)\b", re.IGNORECASE),
    re.compile(r"\d\s*(?:kg|lbs?|oz)\b.{0,80}?\bpulley\b", re.IGNORECASE),
)

# The rope must be vertical for T = m(g ± a) to be the right formula. Nothing
# in the numbers says which way it points, so the question has to.
_TENSION_UP_RE = re.compile(
    r"\blift(?:s|ing|ed)?\b|\brais(?:e|es|ing|ed)\b|\bhoist\w*\b|\bpull(?:s|ed|ing)?\s+up\b"
    r"|\bupwards?\b|\bris(?:e|es|ing)\b|\bascend\w*\b|\baccelerat\w*\s+up\w*\b",
    re.IGNORECASE,
)
_TENSION_DOWN_RE = re.compile(
    r"\blower(?:s|ing|ed)?\b|\bdescend\w*\b|\bdownwards?\b|\bfall(?:s|ing)\b|\bdropp?(?:s|ing|ed)\b",
    re.IGNORECASE,
)
_TENSION_STATIC_RE = re.compile(
    r"\bhang(?:s|ing)?\b|\bsuspend\w*\b|\bhold(?:s|ing)?\b|\bsupport(?:s|ing)?\b"
    r"|\bstationary\b|\bat rest\b|\bequilibrium\b",
    re.IGNORECASE,
)

# Shapes that carry the word but not the formula. A rope at an angle is a
# vector problem (P17's territory), a rope across a table is horizontal so the
# weight does not enter at all, and two ropes share the load between them —
# each would be answered confidently and wrongly by T = m(g ± a).
_UNSUPPORTED_TENSION_CONTEXT = (
    "incline",
    "ramp",
    "slope",
    "angle",
    "degree",
    "°",
    "friction",
    "coefficient",
    "horizontal",
    "floor",
    "table",
    "across",
    "two ropes",
    "both ropes",
    "each rope",
    "two cables",
    "both cables",
    "each cable",
    "two strings",
    "each string",
)


def _extract_tension_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, (), _TENSION_CUE_RES):
        return None
    if any(word in lower for word in _UNSUPPORTED_TENSION_CONTEXT):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    masses = _ordered_values(cleaned, r"kg|lbs?|oz")
    if not masses:
        return None

    # --- Atwood: two masses sharing one pulley --------------------------------
    is_pair = "atwood" in lower or "pulley" in lower
    if is_pair and len(masses) >= 2:
        # The heavier mass descends, so ordering them here makes the sign of
        # the acceleration a property of the physics rather than of the
        # sentence. Its magnitude is what the question asks for either way.
        heavy, light = sorted((masses[0], masses[1]), key=lambda pair: pair[0], reverse=True)
        return MathIntent(
            kind="force",
            physics_op="atwood",
            physics_params={"m1": heavy[0], "m2": light[0]},
            physics_units={"m1": heavy[1] or "kg", "m2": light[1] or "kg"},
            operation="solve",
        )
    if is_pair:
        # A pulley with one mass named is an incomplete Atwood, not a hanging
        # mass: the rope runs over the pulley to something we were not told
        # about. Refusing beats assuming the other side is fixed.
        return None

    # --- a single rope, which must be vertical -------------------------------
    goes_up = _TENSION_UP_RE.search(cleaned) is not None
    goes_down = _TENSION_DOWN_RE.search(cleaned) is not None
    is_static = _TENSION_STATIC_RE.search(cleaned) is not None
    if not (goes_up or goes_down or is_static):
        return None

    params: dict[str, float] = {"m": masses[0][0]}
    units: dict[str, str] = {"m": masses[0][1] or "kg"}
    accel = _find_value_with_specific_unit(
        cleaned,
        r"m/s\^?2|m/s2",
        ("acceleration", "accelerates", "accelerating", "accelerated"),
    )
    if accel is not None:
        value, unit = accel
        # Down is the only direction that has to be stated; "supporting a mass
        # accelerating at 2 m/s^2" reads as upward, which is what P2's example
        # meant by 59.05 N.
        params["a"] = -value if goes_down else value
        units["a"] = unit or "m/s^2"

    return MathIntent(
        kind="force",
        physics_op="tension",
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


# ---------------------------------------------------------------------------
# Vector forces
#   Resultant:  R = sqrt(F1^2 + F2^2 + 2 F1 F2 cos(phi)),  theta from F1
#   Resolve:    Fx = F cos(theta),  Fy = F sin(theta)
# ---------------------------------------------------------------------------
#
# Everything else on the `force` kind is scalar, which is why "a 3 N force east
# and a 4 N force north" had no answer at all.
#
# `services/math/` already owns a `vector` kind for magnitude/dot/cross, and the
# ticket asked which should be used. It is not reusable here: that extractor
# matches literal angle-bracket operands ("magnitude of <3, 4>") through
# `is_closed_coordinate_vector_request`, and a force question names units and
# compass directions instead. The two never see the same sentence, so this is a
# physics extractor and the maths one is left alone.

# "resultant" is specific enough to stand almost alone, but it is still paired
# with a newton reading. "resolve" and "component" are not specific at all —
# resolving a dispute, a component of a plan — so they need the force *and* the
# angle before they count. These feed the global pre-filter, as always.
#
# Case-insensitive, deliberately, where the circuit cues are not: those had to
# tell "12 V" from "12 v cards", and the bare letters V and A carry that risk
# because they are also English words. N is not, and every pattern here already
# demands a word beside the reading — so the pre-filter, which lowercases
# before it asks, can still see these. Matching case-sensitively would have
# made the whole topic unreachable in the real pipeline while every extractor
# test passed.
_VECTOR_FORCE_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bresultant\b.{0,80}?\d\s*N\b", re.IGNORECASE),
    re.compile(r"\d\s*N\b.{0,80}?\bresultant\b", re.IGNORECASE),
    re.compile(
        r"(?=.*\b(?:resolv\w*|components?)\b)(?=.*\d\s*N\b)(?=.*\d\s*(?:degrees?|deg|°))",
        re.IGNORECASE | re.DOTALL,
    ),
)

# Two forces meet at a right angle. Compass pairs say so without the word, and
# that is the commonest phrasing by far.
_PERPENDICULAR_RE = re.compile(
    r"\bperpendicular\b|\bright angles?\b|\bat 90\s*(?:degrees?|deg|°)"
    r"|\b(?:north|south)\b.{0,60}?\b(?:east|west)\b|\b(?:east|west)\b.{0,60}?\b(?:north|south)\b"
    r"|\bhorizontal\b.{0,60}?\bvertical\b|\bvertical\b.{0,60}?\bhorizontal\b",
    re.IGNORECASE,
)
# An angle stated as the one *between* the two forces, rather than the
# direction of a single force.
_ANGLE_BETWEEN_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(?:degrees?|deg|°)(?:[^.]{0,40}?"
    r"(?:to each other|between them|apart|to one another))",
    re.IGNORECASE,
)
_ANGLE_VALUE_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(?:degrees?|deg|°)(?![A-Za-z0-9])", re.IGNORECASE
)
_RESOLVE_RE = re.compile(r"\bresolv\w*\b|\bcomponents?\b", re.IGNORECASE)


def _extract_vector_force_intent(cleaned: str) -> MathIntent | None:
    if not _has_cue(cleaned.lower(), (), _VECTOR_FORCE_CUE_RES):
        return None
    if mtm.has_equation(_strip_param_assignments(cleaned)):
        return None

    forces = _ordered_values(cleaned, r"N")

    # --- resultant of two forces -------------------------------------------
    if "resultant" in cleaned.lower() and len(forces) >= 2:
        between = _ANGLE_BETWEEN_RE.search(cleaned)
        if between is not None:
            phi = float(between.group(1))
        elif _PERPENDICULAR_RE.search(cleaned):
            phi = 90.0
        else:
            # Two forces and no stated geometry is not a resultant question
            # anyone can answer — the angle between them is the whole problem.
            return None
        return MathIntent(
            kind="force",
            physics_op="resultant_force",
            physics_params={"F1": forces[0][0], "F2": forces[1][0], "angle": phi},
            physics_units={"F1": "N", "F2": "N", "angle": "deg"},
            operation="solve",
        )

    # --- one force split into components ------------------------------------
    if _RESOLVE_RE.search(cleaned) and forces:
        angle = _ANGLE_VALUE_RE.search(cleaned)
        if angle is None:
            return None
        return MathIntent(
            kind="force",
            physics_op="resolve_force",
            physics_params={"F": forces[0][0], "angle": float(angle.group(1))},
            physics_units={"F": forces[0][1] or "N", "angle": "deg"},
            operation="solve",
        )

    return None


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
    # After kinematics, not before: free fall is a constant acceleration too,
    # and kinematics already owns it. SUVAT sees only what gravity did not
    # claim, so adding it perturbs nothing that already answered.
    _extract_suvat_intent,
    _extract_projectile_intent,
    _extract_momentum_intent,
    _extract_friction_intent,
    _extract_circular_intent,
    # Before the pendulum and the spring: both of those read a *period* as the
    # answer, and the two SHM ops read it as a given.
    _extract_shm_intent,
    # Before springs: a pendulum has a length where a spring has a constant,
    # so the two cannot collide, and reading in this order keeps the spring
    # extractor's k requirement untouched.
    _extract_pendulum_intent,
    _extract_spring_intent,
    _extract_circuit_intent,
    _extract_torque_intent,
    # Ahead of force so the two rope shapes below are claimed before the
    # blanket refusal in _UNSUPPORTED_FORCE_CONTEXT sees them. Everything else
    # rope-shaped still reaches that refusal.
    _extract_tension_intent,
    _extract_vector_force_intent,
    # Round 3, all three ahead of force and energy. Each says a word those two
    # own - optics says "power" (of a lens, in dioptres), thermal says "energy"
    # and modern will too - and running first makes the split deterministic
    # rather than lucky.
    _extract_waves_intent,
    _extract_optics_intent,
    _extract_thermal_intent,
    _extract_gravitation_intent,
    _extract_fluids_intent,
    # After torque, deliberately. P9 refuses "moment of inertia" there because
    # it was not solved; that refusal is what stops *torque* claiming it, and
    # is kept. This picks up the fall-through.
    _extract_rotation_intent,
    _extract_force_intent,
    _extract_energy_intent,
)

PHYSICS_CUES: tuple[str, ...] = tuple(
    dict.fromkeys(
        (
            *_KINEMATICS_CUES,
            *_SUVAT_CUES,
            *_PROJECTILE_CUES,
            *_MOMENTUM_CUES,
            *_WAVE_CUES,
            *_OPTICS_CUES,
            *_THERMAL_CUES,
            *_GRAVITATION_CUES,
            *_FLUIDS_CUES,
            *_ROTATION_CUES,
            *_FRICTION_CUES,
            *_CIRCULAR_CUES,
            *_SPRING_CUES,
            *_CIRCUIT_CUES,
            *_TORQUE_CUES,
            *_FORCE_CUES,
            *_ENERGY_CUES,
        )
    )
)

# The boundary-sensitive half of the same table — see ``_has_cue``.
PHYSICS_CUE_RES: tuple[re.Pattern[str], ...] = (
    *_KINEMATICS_CUE_RES,
    *_SUVAT_CUE_RES,
    *_PROJECTILE_CUE_RES,
    *_FRICTION_CUE_RES,
    *_CIRCULAR_CUE_RES,
    *_WAVE_CUE_RES,
    *_THERMAL_CUE_RES,
    *_GRAVITATION_CUE_RES,
    *_FLUIDS_CUE_RES,
    *_ROTATION_CUE_RES,
    *_SHM_CUE_RES,
    *_PENDULUM_CUE_RES,
    *_SPRING_CUE_RES,
    *_CIRCUIT_CUE_RES,
    *_TORQUE_CUE_RES,
    *_TENSION_CUE_RES,
    *_VECTOR_FORCE_CUE_RES,
    *_FORCE_CUE_RES,
    *_ENERGY_CUE_RES,
)


def has_supported_physics_cue(cleaned: str) -> bool:
    """True when a verified physics template could match this text.

    Takes the text **as written**, not lowercased. See `_has_cue_either_case`.
    """
    return _has_cue_either_case(cleaned, PHYSICS_CUES, PHYSICS_CUE_RES)
