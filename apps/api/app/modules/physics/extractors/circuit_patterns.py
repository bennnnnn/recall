"""The units, cues and resistor lists a circuit question is read by."""

from __future__ import annotations

import re

from app.modules.physics.extractors.common import _ordered_values

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

_AMP_PATTERN = r"A|amps?|amperes?"

_OHM_PATTERN = r"ohms?|\u03a9"

_VOLT_CUE = r"V|[Vv]olts?"

_AMP_CUE = r"A|[Aa]mp(?:s|ere|eres)?"

_OHM_CUE = r"[Oo]hms?|\u03a9"


def _circuit_pair(first: str, second: str) -> re.Pattern[str]:
    """A number in `first`'s unit within 80 chars of a number in `second`'s.

    No IGNORECASE: the bare letters below are the SI symbols, and the spelled
    out forms carry their own case classes. `_has_cue_either_case` is what
    makes this reachable from the pre-filter.
    """
    return re.compile(rf"\d\s*(?:{first})(?![A-Za-z0-9]).{{0,80}}?\d\s*(?:{second})(?![A-Za-z0-9])")


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

_COULOMB_PATTERN = r"uC|µC|C|microcoulombs?|coulombs?"

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


def _resistor_values(text: str) -> list[float]:
    """Every resistance in a network, however the units are distributed."""
    listed = _RESISTOR_LIST_RE.search(text)
    if listed is not None:
        return [float(n) for n in re.findall(r"\d+(?:\.\d+)?", listed.group(1))]
    return [value for value, _ in _ordered_values(text, _OHM_PATTERN)]
