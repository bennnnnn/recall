"""What a question says about how a body's speed behaves: at rest at the start or the end,
changing on the way, or brought to rest by braking.

One reader for every law that depends on it. Three readers each kept their own words for
"it stops" before (2026-11-07): the constant-speed extractor knew "to a stop" and "brake",
the binder's constant-speed laws knew "to stop" and "to rest", and SUVAT knew "stops" and
"halts". A question said a fourth way ("stops after 5 s", "to a standstill", "becomes
stationary") reached a reader that missed it and was answered d = vt, verified.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# It stops or halts, as a verb: "between two stops" and "the next stop" name a place, so a
# determiner or a number just before the word makes it a noun. A noun read as a verb only
# costs a decline; a verb read as a noun would answer d = vt, so "the bus stops" stays a verb.
_STOP_VERB = re.compile(r"\b(?:stops?|stopped|stopping|halts?|halted|halting)\b", re.IGNORECASE)
_NOUN_BEFORE = re.compile(
    r"(?:\b(?:a|an|the|its|each|every|next|last|first|two|three|four|five|several|many|no"
    r"|full|complete|sudden|dead)|\d)\s*$",
    re.IGNORECASE,
)

# At rest at the end: it comes to rest, reaches a standstill, becomes stationary, or its
# speed falls to zero (the bare verb is ``_STOP_VERB``).
_ENDS_AT_REST = re.compile(
    r"\b(?:to|into)\s+(?:a\s+)?(?:complete\s+|full\s+|dead\s+)?(?:stop|halt|rest|standstill)\b"
    r"|\b(?:becomes?|became|is\s+(?:then|now)|until\s+(?:it\s+is\s+)?)\s*"
    r"(?:stationary|motionless|at\s+rest)\b"
    r"|\b(?:speed|velocity)\s+(?:becomes|reaches|falls\s+to|drops\s+to|decreases\s+to"
    r"|is\s+reduced\s+to)\s+zero\b"
    r"|\b(?:reduces|reduced|brings)\s+(?:its|their|his|her)\s+(?:speed|velocity)\s+to\s+zero\b",
    re.IGNORECASE,
)

# At rest at the start: from rest, from a standstill, initially stationary.
_STARTS_AT_REST = re.compile(
    r"\b(?:from|at|starts?\s+(?:from|at)|starting\s+(?:from|at)|initially\s+at)\s+"
    r"(?:a\s+)?(?:rest|standstill)\b"
    r"|\b(?:initially|originally|at\s+first)\s+(?:stationary|motionless|at\s+rest)\b"
    r"|\b(?:stationary|motionless)\s+(?:at\s+first|initially)\b",
    re.IGNORECASE,
)

# Its speed changes: it speeds up, slows down, brakes or decelerates.
_CHANGES_SPEED = re.compile(
    r"\b(?:accelerat\w*|decelerat\w*|brak(?:e|es|ed|ing)|retard\w*)\b"
    r"|\bslow(?:s|ed|ing)?\s+down\b|\bslows\b"
    r"|\bspeeds?\s+up\b|\bsped\s+up\b|\bpicks?\s+up\s+speed\b",
    re.IGNORECASE,
)

# Brought to rest by its brakes or a stated deceleration, never turned back: a car does
# not reverse when its brakes have stopped it. A throw against gravity does.
_BRAKES = re.compile(
    r"\bbrak(?:e|es|ed|ing)\b|\bdecelerat\w*\b|\bslow(?:s|ed|ing)?\s+down\b|\bretard\w*\b",
    re.IGNORECASE,
)

# Gravity slows a body only to turn it back: a throw up "decelerates at 9.8 m/s²" and falls
# again, so it never stays stopped (review of #2333). Named, or given as g's own size.
_TURNS_BACK = re.compile(
    r"\bgravit\w*|\bfree[\s-]?fall|\b(?:thrown|throws?|tossed|tosses|launched|projected|fired|"
    r"kicked|hit)\s+(?:\w+\s+){0,2}(?:straight\s+)?(?:up|upward|upwards|vertically)\b|"
    r"\bvertically\b|\b(?:incline|slope|ramp|hill)s?\b",
    re.IGNORECASE,
)
_G_SIZED = re.compile(r"(?<![\d.])9\.8\d?\s*(?:m\s*/\s*s|m\s*s|ms)", re.IGNORECASE)

# The marker the binder's excludes read for a speed that changes (``binding._with_markers``).
SPEED_CHANGE_MARKER = "speedchange"
# The marker for a body that spins as it rolls: ½mv² and √(2gh) leave its spin out (a solid
# sphere rolling down 2 m is 5.29 m/s, not 6.26).
ROLLING_BODY_MARKER = "rollingbody"
# A body that can spin, said to roll: a ball, a hoop, a wheel. A car or a trolley "rolling"
# along a road is moved, not spun, as a whole.
_ROLLING_BODY_RE = re.compile(
    r"\bwithout\s+slipping\b"
    r"|\b(?:sphere|ball|marble|cylinder|disc|disk|hoop|ring|wheel|tyre|tire|can|pipe)s?\b"
    r"[^.?!]{0,80}?\broll(?:s|ed|ing)?\b(?!\s+off\b)",
    re.IGNORECASE,
)


def rolling_body(text: str) -> bool:
    """The question's body spins as it rolls: "a solid sphere rolls down a slope"."""
    return _ROLLING_BODY_RE.search(text) is not None


# An average speed is the whole distance over the whole time, whatever the speed does on the
# way: "starts from rest and covers 100 m in 12 s, average speed?" is 100 / 12.
_AVERAGE_SPEED = re.compile(r"\b(?:average|mean)\s+(?:speed|velocity)\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Motion:
    """How the question says a body's speed behaves."""

    starts_at_rest: bool
    ends_at_rest: bool
    changes_speed: bool
    brakes: bool
    # Brought to rest and kept there: brakes or friction, never gravity.
    halts: bool


def _stops(text: str) -> bool:
    """It stops or halts. Only "stop" and "stops" can name a place ("two stops apart"); a
    "stopping distance" or a train that "halted" is the motion ending."""
    return any(
        match.group().lower() not in {"stop", "stops"}
        or _NOUN_BEFORE.search(text[: match.start()]) is None
        for match in _STOP_VERB.finditer(text)
    )


def constant_speed_laws_hold(text: str) -> bool:
    """d = vt and v = d/t answer the question: its speed never changes, or the speed it states
    or asks is an average (review of #2333: a sprinter "starts from rest" declined d/t)."""
    return not read_motion(text).changes_speed or _AVERAGE_SPEED.search(text) is not None


def read_motion(text: str) -> Motion:
    """How ``text`` says a body's speed behaves. A body at rest at either end of a stated
    speed is changing speed, whatever verb carries it ("stops after 5 s")."""
    starts = _STARTS_AT_REST.search(text) is not None
    ends = _stops(text) or _ENDS_AT_REST.search(text) is not None
    return Motion(
        starts_at_rest=starts,
        ends_at_rest=ends,
        changes_speed=starts or ends or _CHANGES_SPEED.search(text) is not None,
        brakes=(brakes := _BRAKES.search(text) is not None),
        halts=brakes and _TURNS_BACK.search(text) is None and _G_SIZED.search(text) is None,
    )
