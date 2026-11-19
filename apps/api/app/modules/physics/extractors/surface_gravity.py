"""The g a question means: one it states, the body it names, or Earth's."""

from __future__ import annotations

import re
from collections.abc import Iterator

from app.modules.physics.bodies import SCHOOL_GRAVITY, names_our_moon
from app.modules.physics.extractors.written_unit import written_unit
from app.services.solving import SolveServiceError
from app.services.text_match import word_index

EARTH_G = SCHOOL_GRAVITY["earth"]

_NUMBER = r"(-?\d+(?:\.\d+)?)"
# An acceleration's or a field strength's unit, as a g is written: m/s², m s^-2, N/kg, ft/s².
_G_UNIT = (
    r"(?:m|cm|ft)\s*/\s*s\s*(?:\^\s*\{?2\}?|\u00b2|2)?|(?:m|ft)\s*s\s*(?:\^\s*\{?-2\}?|\u207b\u00b2)"
    r"|N\s*/\s*kg|N\s*kg\s*(?:\^\s*\{?-1\}?|\u207b\u00b9)"
)
# A g the question states, its number the first group: "g = 1.62", "gravity of 3.7", "the
# acceleration due to gravity is 9.8", "a gravitational acceleration of 3.7", "free-fall
# acceleration of 9.8", and one named after its value: "take 10 m/s² for g", "Taking 10 m/s²
# as the acceleration due to gravity" (review of #2491).
_STATED_G = (
    # "g = 10", "g ≈ 9.8", "g: 9.81", "take g as 10 m/s²", "g is 9.8", "g of 1.62", "g to be
    # 10" (Claude on #2491: "Take g as 10 m/s²" was dropped, 19.6 N for 20 N).
    re.compile(
        rf"\bg\s*(?:=|\u2248|~|:|\bas\b|\bis\b|\bof\b|\bto\s+be\b)\s*{_NUMBER}", re.IGNORECASE
    ),
    re.compile(rf"\bgravity\s*(?:of|is|=)?\s*{_NUMBER}", re.IGNORECASE),
    re.compile(
        rf"\b(?:gravitational|free[\s-]?fall)\s+(?:acceleration|field(?:\s+strength)?)"
        rf"\s*(?:of|is|=)?\s*{_NUMBER}",
        re.IGNORECASE,
    ),
    re.compile(
        # Started where a number starts, never inside one (tried from every digit of a run,
        # the search was quadratic), and only its own unit between it and the label: "μ =
        # 0.5 (10 N/kg for g)" is 10, never the 0.5 before it (Gemini on #2491).
        rf"(?<![\d.]){_NUMBER}\s*(?:{_G_UNIT})?\s*\b(?:as|for)\s+(?:the\s+)?(?:g\b|gravity\b"
        r"|acceleration\s+due\s+to\s+gravity|gravitational\s+acceleration)",
        re.IGNORECASE,
    ),
)


# A number right before a "g": the g is its unit, grams ("a rocket of 500 g is 15 m/s²").
_AFTER_A_NUMBER = re.compile(r"\d\s*$")
_LONE_G = re.compile(r"g\b", re.IGNORECASE)


def _another_kind(unit: str) -> bool:
    """``unit`` is one the shared table reads, of a kind no g is: "gravity of 5 kg" is a
    mass. A unit nothing reads is kept, for ``gravity_unit_unread`` to decline."""
    from app.modules.physics.solvers.si import to_si

    if not unit:
        return False
    try:
        to_si(1.0, unit)
    except SolveServiceError:
        return False
    return _in_m_per_s2(1.0, unit) is None


def _stated_gs(text: str) -> Iterator[tuple[re.Match[str], str]]:
    """Every g the user wrote, its match and the unit written after its value ("" when none
    is), in the readers' order. A g is gravity's value: never the gram a mass is written in
    ("500 g is 15 m/s²" certified g = 15, 300 J for 196.2 J), never a value in a unit of
    another kind ("gravity of 5 kg") (Gemini on #2491)."""
    for pattern in _STATED_G:
        for match in pattern.finditer(text):
            if _LONE_G.match(match.group()) and _AFTER_A_NUMBER.search(
                text[max(0, match.start() - 12) : match.start()]
            ):
                continue
            unit = written_unit(text, match.end(1), "g")
            if not _another_kind(unit):
                yield match, unit


def _written_gravity(text: str) -> tuple[float, str] | None:
    """The g the user wrote and the unit written after it ("" when none is)."""
    for match, unit in _stated_gs(text):
        return float(match.group(1)), unit
    return None


def gravity_at(text: str, start: int, end: int) -> bool:
    """The value written at ``start:end`` is the g this reader reads: the one place a stated
    g is told from any other acceleration, for the binder as for ``detect_gravity``."""
    return any(start <= match.start(1) < end for match, _ in _stated_gs(text))


def stated_gravity_spans(text: str) -> list[tuple[int, int]]:
    """Where each stated g is written, its label, value and unit: one per value, for a
    reader that accounts for every number a question states (``request``)."""
    spans: dict[int, tuple[int, int]] = {}
    for match, unit in _stated_gs(text):
        unit_end = text.find(unit, match.end(1)) + len(unit) if unit else match.end()
        spans.setdefault(match.start(1), (match.start(), max(match.end(), unit_end)))
    return list(spans.values())


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
    # Only Earth's Moon has the Moon's g: "a moon of Jupiter" is another body.
    if names_our_moon(lower) and not _only_set_aside(lower, "moon"):
        return SCHOOL_GRAVITY["moon"]
    if word_index(lower, "mars") != -1 and not _only_set_aside(lower, "mars"):
        return SCHOOL_GRAVITY["mars"]
    return EARTH_G


def names_a_gravity(text: str) -> bool:
    """The question sets its scene under a gravity of its own: a g it states, the Moon or
    Mars (``detect_gravity``), or another named planet or star. A stated acceleration there
    may be its g ("on Jupiter, where the acceleration is 24.8 m/s²")."""
    from app.modules.physics.bodies import central_body

    return detect_gravity(text) != EARTH_G or central_body(text.lower()) is not None


def _only_set_aside(lower: str, body: str) -> bool:
    """Every mention of ``body`` owns something the question sets aside: "Ignoring the Moon's
    1.6 m/s², a ball is dropped on Earth" fell under the Moon's g, 5 s for 2.02 s (review
    2026-11-07)."""
    from app.modules.physics.set_aside import set_aside_owner

    return all(
        set_aside_owner(lower, found.start()) for found in re.finditer(rf"\b{body}\b", lower)
    )
