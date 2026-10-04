"""Constant acceleration in a straight line (SUVAT) for any one unknown."""

from __future__ import annotations

import re

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.ask import ask_clause, asked_phrases
from app.modules.physics.extractors.common import (
    _LENGTH_UNIT_PATTERN,
    _NUMBER,
    _VELOCITY_UNIT_PATTERN,
    _find_value_with_specific_unit,
    _ordered_values,
    _strip_param_assignments,
)
from app.modules.physics.extractors.cues import (
    _has_cue,
)
from app.services.text_match import has_equation

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

# A lone speed the question says it ends at: "accelerates ... and reaches 18 m/s".
# That is v, and a question for v that states it has nothing left to solve.
_FINAL_SPEED_RE = re.compile(
    r"\b(?:reach(?:es|ed|ing)?|final\s+(?:speed|velocity)(?:\s+(?:of|is))?|up\s+to|until\s+it\s+reaches)"
    rf"\s+(?:a\s+(?:speed|velocity)\s+of\s+)?{_NUMBER}\s*(?:{_VELOCITY_UNIT_PATTERN})",
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
            r"\bdisplacement\b|\bhow far\b|\bwhat distance\b"
            r"|\bdistance (?:does|do|is|will|travel|cover)"
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

    clause = ask_clause(cleaned)
    if clause is None:
        return None
    # A stated displacement/final speed is a given, not an unknown. Read the
    # first requested noun before the fallback phrasings ("how far/long/fast").
    phrases = asked_phrases(cleaned)
    unknown = {
        "distance": "suvat_distance",
        "displacement": "suvat_distance",
        "velocity": "suvat_velocity",
        "speed": "suvat_velocity",
        "acceleration": "suvat_acceleration",
        "deceleration": "suvat_acceleration",
        "time": "suvat_time",
    }.get(phrases[0] if phrases else "")
    if unknown is None:
        matches = [
            (match.start(), op)
            for op, rx in _SUVAT_UNKNOWN_RES
            if (match := rx.search("find " + clause)) is not None
        ]
        unknown = min(matches)[1] if matches else None
    if unknown is None:
        return None

    params: dict[str, float] = {}
    units: dict[str, str] = {}

    # --- the two velocities, bound by written order -------------------------
    # "from 10 m/s to 30 m/s" reads left to right; a stated rest state at
    # either end fills the slot that has no number of its own.
    velocities = _ordered_values(cleaned, _VELOCITY_UNIT_PATTERN)
    if (
        len(velocities) > 1
        and re.search(r"\b(?:from|initial(?:ly)?)\b", cleaned, re.IGNORECASE) is None
    ):
        # Written order alone cannot identify which of two unlabeled speeds
        # came first ("has speeds 10 m/s and 30 m/s").
        return None
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
    elif len(velocities) == 1 and _FINAL_SPEED_RE.search(cleaned):
        params["v"], units["v"] = velocities[0]
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
