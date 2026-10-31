"""The units, cues and resistor lists a circuit question is read by."""

from __future__ import annotations

import re

from app.modules.physics.extractors.stated_values import ordered_values, positioned_values
from app.modules.physics.extractors.unit_patterns import AMP_PATTERN, OHM_PATTERN
from app.services.number_text import count_word_pattern, number_word_value

_CIRCUIT_CUES = (
    "ohm",
    "voltage",
    "volts",
    "resistor",
    "ampere",
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
    "time constant",
    "parallel plate",
)

_VOLT_PATTERN = r"V|volts?"

_VOLT_CUE = r"V|[Vv]olts?"

_AMP_CUE = r"A|[Aa]mp(?:s|ere|eres)?"

_OHM_CUE = r"[Oo]hms?|\u03a9"


def _circuit_pair(first: str, second: str) -> re.Pattern[str]:
    """A number in `first`'s unit within 80 chars of a number in `second`'s.

    No IGNORECASE: the bare letters below are the SI symbols, and the spelled
    out forms carry their own case classes. `_has_cue_either_case` is what
    makes this reachable from the pre-filter.
    """
    # A prefix stays the unit's: "20 mA from a 3 V supply", "a 4.7 kΩ resistor".
    prefix = "(?:k|m|M|µ|μ)?"
    return re.compile(
        rf"\d\s*{prefix}(?:{first})(?![A-Za-z0-9]).{{0,80}}?\d\s*{prefix}(?:{second})(?![A-Za-z0-9])"
    )


_CHARGE_FLOW_RE = re.compile(
    rf"\bcharge\b.{{0,60}}?\d\s*(?:{AMP_PATTERN})(?![A-Za-z0-9])"
    rf"|\d\s*(?:{AMP_PATTERN})(?![A-Za-z0-9]).{{0,60}}?\bcharge\b",
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

_COULOMB_PATTERN = (
    r"uC|µC|μC|nC|pC|mC|C|microcoulombs?|nanocoulombs?|picocoulombs?|millicoulombs?|coulombs?"
)

_FARAD_PATTERN = r"mF|uF|µF|nF|pF|F|farads?|microfarads?|nanofarads?|picofarads?"

_CIRCUIT_TIME_UNITS = r"seconds?|secs?|sec|s|minutes?|mins?|min|hours?|hrs?|hr|h"

_TERMINAL_ASK_RE = re.compile(
    r"\bterminal\b|\bacross the terminals\b|\blost volts\b|\bp\.?d\.? across\b",
    re.IGNORECASE,
)

# Everyday words first: a phone battery at 20 percent, circuit training three
# times a week, a resistance band. Each is a circuit only beside an electrical
# value; "amps" is a word, not the inside of "lamps".
_EVERYDAY_CIRCUIT_RE = re.compile(
    r"\A(?=.*\b(?:batter(?:y|ies)|circuits?|resistances?)\b)"
    rf"(?=.*\d\s*(?:k|m|M)?(?:{_VOLT_CUE}|{_AMP_CUE}|{_OHM_CUE}|W|[Ww]atts?)(?![A-Za-z0-9]))",
    re.DOTALL,
)
_AMPS_WORD_RE = re.compile(r"\bamps\b", re.IGNORECASE)

_CIRCUIT_CUE_RES: tuple[re.Pattern[str], ...] = (
    _EVERYDAY_CIRCUIT_RE,
    _AMPS_WORD_RE,
    _circuit_pair(_VOLT_CUE, rf"{_AMP_CUE}|{_OHM_CUE}"),
    _circuit_pair(rf"{_AMP_CUE}|{_OHM_CUE}", _VOLT_CUE),
    _circuit_pair(_AMP_CUE, _OHM_CUE),
    _circuit_pair(_OHM_CUE, _AMP_CUE),
    _CHARGE_FLOW_RE,
    _ELECTRICAL_ENERGY_RE,
)

_MAX_NETWORK_RESISTORS = 4

# At most one value past the limit, which is enough to refuse a longer network.
# An unbounded list made every number of a pasted CSV restart the whole scan:
# seconds of backtracking at 20,000 characters.
_RESISTOR_LIST_RE = re.compile(
    r"((?<!\d)\d+(?:\.\d+)?(?:\s*(?:,|and)\s*\d+(?:\.\d+)?)"
    rf"{{1,{_MAX_NETWORK_RESISTORS}}})\s*(?:ohms?|\u03a9)",
    re.IGNORECASE,
)


# "three 9 Ω resistors", "two identical 10 ohm resistors": one value, stated once.
_COUNTED_RESISTORS_RE = re.compile(
    rf"\b({count_word_pattern(low=2, high=6)})\s+(?:identical\s+|equal\s+)?"
    r"(\d+(?:\.\d+)?)\s*(?:ohms?|Ω)\s+resistors\b",
    re.IGNORECASE,
)
_MAX_COUNTED_RESISTORS = 6


def counted_resistors(text: str) -> tuple[int, float] | None:
    """(count, value) of identical resistors named by a count word, or None."""
    found = list(_COUNTED_RESISTORS_RE.finditer(text))
    if len(found) != 1:
        return None
    # The pattern reads only count words, so the value is always there.
    return number_word_value(found[0].group(1)) or 0, float(found[0].group(2))


def resistor_values(text: str) -> list[float]:
    """Every resistance in a network, however the units are distributed.

    A count word repeats its value: "three 9 Ω resistors" are 9, 9 and 9 Ω.
    Read as one 9 Ω resistor, a parallel bank across 6 V drew 0.667 A, not 2 A.
    """
    counted = counted_resistors(text)
    if counted is not None:
        count, value = counted
        others = ordered_values(text, OHM_PATTERN)
        if len(others) != 1:
            # Other resistors beside the counted ones: a network this does not read.
            return []
        return [value] * count
    listed = _RESISTOR_LIST_RE.search(text)
    if listed is not None:
        return [float(n) for n in re.findall(r"\d+(?:\.\d+)?", listed.group(1))]
    if _UNKNOWN_RESISTOR_RE.search(text) and not _VALUED_R_RE.search(text):
        # "a 3 Ω resistor and a resistor R": the network's total is not the known ones'.
        return []
    return _stated_resistances(text)


# A resistor the question has not valued: "a resistor R", "an unknown resistor"; not "a
# resistor R of 6 Ω" or "R = 4 Ω".
_UNKNOWN_RESISTOR_RE = re.compile(r"\b[Rr]esistors?\s+R\b(?!\s*[=_\d])|\bunknown\s+resist")
_VALUED_R_RE = re.compile(r"\bR\s*(?:=|is\b|of\b)")
# "the potential difference across the 50 Ω resistor": a resistor named again. "In
# parallel with the 6 Ω resistor" may be another one.
_NAMED_AGAIN_RE = re.compile(
    r"\b(?:across|through|in|by|on|over|of)\s+(?:the|that|this)\s+(?:[^.;?]{0,40}\band\s+the\s+)?$",
    re.IGNORECASE,
)


def _stated_resistances(text: str) -> list[float]:
    """Each resistance stated, once: "the 50 Ω resistor" after "a 50 Ω resistor" is the
    same resistor. Counted twice, a 50 Ω and 100 Ω series pair was certified 200 Ω, and a
    3 Ω resistor beside an unknown R 6 Ω (2026-10-30, a Grade 10 physics book)."""
    found = positioned_values(text, OHM_PATTERN)
    values = [value for _, value, _ in found]
    return [
        value
        for start, value, _ in found
        if not (
            values.count(value) > 1 and _NAMED_AGAIN_RE.search(text[max(0, start - 72) : start])
        )
    ]


# "R1 = 10 Ω", "R_2=20Ω": a resistor's name before its value, a given and not algebra.
_NAMED_RESISTOR_RE = re.compile(r"\bR_?\{?(\d{1,2})\}?\s*=\s*(?=\d)")


def without_resistor_names(text: str) -> str | None:
    """The question with its "R1 =" labels taken off, so the network reads as the same
    sentence written without them ("10 Ω is in series with 20 Ω").

    None when a name is used again ("R1 and R2 are in parallel", "the current through
    R2"): a network wired, or a value asked, by name, which this reader does not map.
    """
    labels = [match.group(1) for match in _NAMED_RESISTOR_RE.finditer(text)]
    if not labels:
        return text
    if len(set(labels)) != len(labels):
        return None
    for label in labels:
        if len(re.findall(rf"\bR_?\{{?{label}\}}?(?!\d)", text)) != 1:
            return None
    return _NAMED_RESISTOR_RE.sub("", text)
