"""Stopping distance: a reaction time, then braking to rest."""

from __future__ import annotations

import re

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.common import (
    _NUMBER,
    _VELOCITY_UNIT_PATTERN,
)
from app.modules.physics.extractors.suvat import _SUVAT_TIME_UNITS
from app.services.unit_text import TIME_UNITS

_REACT_WORD_RE = re.compile(r"\breact(?:s|ion|ing)?\b", re.IGNORECASE)
_BRAKE_WORD_RE = re.compile(r"\bbrak(?:e|es|ing)\b", re.IGNORECASE)
_STOP_PHRASE_RE = re.compile(
    r"\bto\s+(?:a\s+)?(?:stop|rest|halt)\b",
    re.IGNORECASE,
)
# Reaction and braking have to be about the same event. A wide window would
# mark an unrelated "react" and a later stop as a template we cannot bind.
_STOPPING_CUE_RE = re.compile(
    r"\breact(?:s|ion|ing)?\b.{0,120}?\b(?:brak(?:e|es|ing)|to\s+(?:a\s+)?(?:stop|rest|halt))\b"
    r"|\b(?:brak(?:e|es|ing)|to\s+(?:a\s+)?(?:stop|rest|halt))\b.{0,120}?"
    r"\breact(?:s|ion|ing)?\b",
    re.IGNORECASE,
)
_STOPPING_CUE_RES: tuple[re.Pattern[str], ...] = (_STOPPING_CUE_RE,)
_STOPPING_NEAR = 80


def _quantity_spans(text: str, unit_pattern: str) -> list[tuple[int, int, float, str]]:
    """Number-plus-unit matches with both ends, so two times can be told apart."""
    return [
        (match.start(), match.end(), float(match.group(1)), match.group(2))
        for match in re.finditer(
            rf"({_NUMBER})\s*({unit_pattern})(?![A-Za-z0-9/^])",
            text,
            re.IGNORECASE,
        )
    ]


def _closest_span(
    cues: list[re.Match[str]], spans: list[tuple[int, int, float, str]]
) -> tuple[tuple[int, int, float, str], int] | None:
    best: tuple[tuple[int, int, float, str], int] | None = None
    for cue in cues:
        for span in spans:
            distance = min(abs(cue.start() - span[0]), abs(cue.start() - span[1]))
            if best is None or distance < best[1]:
                best = (span, distance)
    return best


def extract_stopping_distance(cleaned: str) -> PhysicsIntent | None:
    """Reaction distance plus braking to a stop, when both times are distinct.

    One speed, the time next to "react", and a different time next to the
    stop. If those two times cannot be told apart, this returns nothing so a
    constant-speed law cannot invent a single interval.
    """
    if _STOPPING_CUE_RE.search(cleaned) is None:
        return None
    speeds = _quantity_spans(cleaned, _VELOCITY_UNIT_PATTERN)
    times = _quantity_spans(cleaned, _SUVAT_TIME_UNITS)
    if len(speeds) != 1 or len(times) != 2:
        return None
    _speed_start, _speed_end, speed, speed_unit = speeds[0]
    if speed <= 0:
        return None
    reaction = _closest_span(list(_REACT_WORD_RE.finditer(cleaned)), times)
    # The stop phrase names the braking interval. "Brakes" can sit next to
    # the reaction time ("before applying the brakes"), so it is only a
    # fallback when the sentence never says the car stops.
    braking = _closest_span(list(_STOP_PHRASE_RE.finditer(cleaned)), times)
    if braking is None:
        braking = _closest_span(list(_BRAKE_WORD_RE.finditer(cleaned)), times)
    if reaction is None or braking is None:
        return None
    reaction_span, reaction_distance = reaction
    brake_span, brake_distance = braking
    if reaction_span[0] == brake_span[0] or reaction_distance > _STOPPING_NEAR:
        return None
    if brake_distance > _STOPPING_NEAR:
        return None
    reaction_unit = TIME_UNITS.get(reaction_span[3].lower())
    brake_unit = TIME_UNITS.get(brake_span[3].lower())
    if reaction_unit is None or brake_unit is None:
        return None
    if reaction_span[2] < 0 or brake_span[2] <= 0:
        return None
    return PhysicsIntent(
        kind="kinematics",
        physics_op="stopping_distance",
        physics_params={
            "v": speed,
            "t_react": reaction_span[2],
            "t_brake": brake_span[2],
        },
        physics_units={
            "v": speed_unit.lower(),
            "t_react": reaction_unit,
            "t_brake": brake_unit,
        },
        operation="solve",
    )
