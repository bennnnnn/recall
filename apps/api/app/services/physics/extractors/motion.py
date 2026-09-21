"""Kinematics, SUVAT, and projectile-motion extractors."""

from __future__ import annotations

import re
from typing import Literal

from app.models.schemas.physics import PhysicsIntent
from app.services.physics.extractors.common import (
    _LENGTH_UNIT_PATTERN,
    _T_ASSIGN_RE,
    _VELOCITY_UNIT_PATTERN,
    _detect_gravity,
    _find_value_after_keyword,
    _find_value_with_specific_unit,
    _find_value_with_unit,
    _has_cue,
    _ordered_values,
    _strip_param_assignments,
)
from app.services.physics.extractors.mechanics import _COLLISION_SUBJECT_RE
from app.services.text_match import has_equation

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
    "impact speed",
    "speed at impact",
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
    if any(
        cue in lower for cue in ("speed after", "speed when", "impact speed", "speed at impact")
    ):
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


def _extract_kinematics_intent(cleaned: str) -> PhysicsIntent | None:
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
    if has_equation(stripped):
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
    if v0 > 0 and (
        any(
            cue in lower
            for cue in (
                "thrown down",
                "thrown downward",
                "launched downward",
                "velocity downward",
                "speed downward",
                "downward velocity",
            )
        )
        or ("downward" in lower and ("initial velocity" in lower or "initial speed" in lower))
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
        impact_speed = op == "speed" and ("impact speed" in lower or "speed at impact" in lower)
        if time_match is None and not impact_speed:
            # "velocity after" / "height after" without a duration is
            # ambiguous; do not silently answer with impact time.
            return None
        if time_match is not None:
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

    return PhysicsIntent(
        kind="kinematics",
        physics_op=op,
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


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
    re.compile(r"\bslows?\b.{0,80}?\d\s*m/s\^?2", re.IGNORECASE),
    re.compile(
        r"\d\s*(?:m/s|km/h|mph)\b.{0,80}?\d\s*(?:m/s|km/h|mph)\b"
        r".{0,80}?\d\s*(?:seconds?|secs?|sec|s)\b.{0,80}?\bacceleration\b",
        re.IGNORECASE,
    ),
)

_AT_REST_START_RE = re.compile(
    r"\b(?:from|at|starts?\s+(?:from|at)|starting\s+(?:from|at)|initially\s+at)\s+rest\b",
    re.IGNORECASE,
)

_AT_REST_END_RE = re.compile(
    r"\bto\s+(?:rest|a\s+(?:stop|halt))\b|\b(?:stops?|stopping|halts?)\b"
    r"|\bcomes?\s+to\s+(?:rest|a\s+(?:stop|halt))\b",
    re.IGNORECASE,
)

_DECELERATION_RE = re.compile(r"\bdecelerat\w*\b|\bslow(?:s|ing|ed)?\s+down\b", re.IGNORECASE)

_SUVAT_TIME_UNITS = r"seconds?|secs?|sec|s|minutes?|mins?|min|hours?|hrs?|hr|h"

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
            r"|\btime (?:does|will|is) it take\b|\bstopping time\b|\btime to stop\b",
            re.IGNORECASE,
        ),
    ),
)


def _extract_suvat_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _SUVAT_CUES, _SUVAT_CUE_RES):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
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

    return PhysicsIntent(
        kind="suvat",
        physics_op=unknown,  # type: ignore[arg-type]
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


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

_RANGE_GIVEN_KEYWORDS = ("range", "travel", "reach", "cover", "land", "distance", "far")


def _extract_projectile_intent(cleaned: str) -> PhysicsIntent | None:
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
    if has_equation(_strip_param_assignments(cleaned)):
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
        return PhysicsIntent(
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
    return PhysicsIntent(
        kind="projectile",
        physics_op=op,  # type: ignore[arg-type]
        physics_params=params,
        physics_units=units,
        operation="solve",
    )
