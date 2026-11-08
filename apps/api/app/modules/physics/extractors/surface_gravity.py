"""The g a question means: one it states, the body it names, or Earth's."""

from __future__ import annotations

import re

from app.modules.physics.bodies import SCHOOL_GRAVITY
from app.modules.physics.extractors.written_unit import written_unit
from app.services.solving import SolveServiceError
from app.services.text_match import word_index

EARTH_G = SCHOOL_GRAVITY["earth"]

_STATED_G = (
    re.compile(r"\bg\s*=\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"\bgravity\s*(?:of|is|=)?\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE),
)


def _written_gravity(text: str) -> tuple[float, str] | None:
    """The g the user wrote and the unit written after it ("" when none is)."""
    for pattern in _STATED_G:
        match = pattern.search(text)
        if match:
            return float(match.group(1)), written_unit(text, match.end(1), "g")
    return None


def _in_m_per_s2(value: float, unit: str) -> float | None:
    from app.modules.physics.solvers.si import to_si

    try:
        return to_si(value, unit, expected_key="g")
    except SolveServiceError:
        return None


def stated_gravity(text: str) -> float | None:
    """A gravity value the user wrote, in m/s²: "g = 1.6", "gravity = 1.62", "g = 32 ft/s^2".

    The unit after it is read by the shared table: "g = 32 ft/s^2" was taken as
    32 m/s² (audit 2026-11-07). One nothing reads states no g (``gravity_unit_unread``).
    """
    written = _written_gravity(text)
    if written is None:
        return None
    value, unit = written
    return _in_m_per_s2(value, unit) if unit else value


def gravity_unit_unread(text: str) -> bool:
    """A g is written in a unit that is no acceleration the shared reader knows."""
    written = _written_gravity(text)
    return written is not None and bool(written[1]) and _in_m_per_s2(*written) is None


def detect_gravity(text: str) -> float:
    """If the user named a gravity value, use it; else the named body's, else 9.81 m/s^2."""
    stated = stated_gravity(text)
    if stated is not None:
        return stated
    lower = text.lower()
    for body in ("moon", "mars"):
        if word_index(lower, body) != -1 and not _only_set_aside(lower, body):
            return SCHOOL_GRAVITY[body]
    return EARTH_G


def _only_set_aside(lower: str, body: str) -> bool:
    """Every mention of ``body`` owns something the question sets aside: "Ignoring the Moon's
    1.6 m/s², a ball is dropped on Earth" fell under the Moon's g, 5 s for 2.02 s (review
    2026-11-07)."""
    from app.modules.physics.set_aside import set_aside_owner

    return all(
        set_aside_owner(lower, found.start()) for found in re.finditer(rf"\b{body}\b", lower)
    )
