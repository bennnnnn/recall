"""What a question writes and what a solve read, as quantities: a value with its SI value
and dimension when its unit is known (``verified_numbers``)."""

from __future__ import annotations

import math
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from app.services.law_binding.units import unit_dimension

# One number as written; not a name's index ("R1", "H2O") or a unit's power ("m/s^2",
# "s^-1"). Every run is bounded, and no match starts inside a run of digits.
_NUMBER = re.compile(
    r"(?<![A-Za-z\d.,^_])(?<!\^-)-?(?:\d{1,30}(?:,\d{3}){0,10}(?:\.\d{1,30})?|\.\d{1,30})"
    r"(?:[eE][+-]?\d{1,6})?(?!\d)"
)
# What a solve wrote may raise a number to a power ("3^4", "3**4"): its digits are read.
_READ_NUMBER = re.compile(
    r"(?<![A-Za-z\d.,_])-?(?:\d{1,30}(?:,\d{3}){0,10}(?:\.\d{1,30})?|\.\d{1,30})"
    r"(?:[eE][+-]?\d{1,6})?(?!\d)"
)
_TIMES_TEN = re.compile(
    r"(?<![\d.])(\d{1,30}(?:\.\d{1,30})?)\s{0,3}"
    r"(?:[x\u00d7*\u00b7]\s{0,3}10\s{0,3}(?:\^|\*\*)\s{0,3}\(?|e)(-?\d{1,8})\)?",
    re.IGNORECASE,
)
# Past this, a power of ten is no float ("1 x 10^1000"): the check fails, it never raises.
_MAX_EXPONENT = 300
_SUPERSCRIPT = str.maketrans(
    "\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079\u207b", "0123456789-"
)
_SUPERSCRIPT_RUN = re.compile("[\u2070\u00b9\u00b2\u00b3\u2074-\u2079\u207b]{1,8}")
# "Question 3", "Exercise 2.15", "Q1", a leading "4." and a year are labels, not values.
_LABEL = re.compile(
    r"\b(?:question|exercise|problem|example|part|page|chapter|section|step|figure|fig|"
    r"table|q|ex)\.?[ \t]{0,3}#?[ \t]{0,3}(\d{1,6}(?:\.\d{1,6}){0,3})[a-z]?\b",
    re.IGNORECASE,
)
_LIST_NUMBER = re.compile(r"\A\s{0,8}\(?(\d{1,3})[.)]\s")
_YEAR = re.compile(r"\b(1[89]\d\d|20\d\d)\b(?![ \t]{0,3}(?:[a-zA-Z%\u00b0\u03a9\u00b5]|/))")
# "Iodine-131", "carbon-14", "s-1": a name's number or a unit's power.
_NAMED = re.compile(r"(?<=[A-Za-z]-)(\d{1,6})")
# "I got 48 A. Is that right?": a student's claim is checked, not read.
_CLAIM = re.compile(
    r"\b(?:i\s+got|i\s+get|my\s+answer\s+(?:is|was)|i\s+calculated|i\s+think\s+it'?s)"
    r"(?:\s+[a-z]{1,20}){0,4}?\s+(-?[\d.,]{1,30}(?:\s{0,3}[x\u00d7*]\s{0,3}10\^-?\d{1,6})?)",
    re.IGNORECASE,
)
# "CuSO4·5H2O", "2H2O": a number glued to a formula is the formula's.
_IN_FORMULA = re.compile(r"(?<!\d)(\d{1,6})(?=[A-Z][a-z]?\d{0,6})")
# "[A]0", "(x)2": an index written onto a bracket.
_INDEX = re.compile(r"(?<=[\])])(\d{1,6})")
# "1/16": a fraction may be read as its value.
FRACTION = re.compile(r"(?<![\d.,/])(\d{1,9})\s{0,3}/\s{0,3}(\d{1,9})(?![\d.,/])")
# A value may be read at another metric prefix when one side writes no unit.
_PREFIX_SCALES = tuple(10.0**power for power in range(-12, 13, 3))


@dataclass(frozen=True, slots=True)
class Quantity:
    """A value as written, and in SI with its dimension when its unit is known."""

    value: float
    si: float | None = None
    dimension: str | None = None
    start: int = 0
    end: int = 0
    written: str = ""


def to_plain(text: str) -> str:
    return _SUPERSCRIPT_RUN.sub(lambda run: "^" + run.group(0).translate(_SUPERSCRIPT), text)


def _power(mantissa: str, exponent: str) -> float | None:
    """``mantissa`` x 10^``exponent``, or None when no float holds it."""
    if abs(int(exponent)) > _MAX_EXPONENT:
        return None
    value = float(mantissa) * 10.0 ** int(exponent)
    return value if math.isfinite(value) else None


def _number(written: str) -> float | None:
    value = float(written.replace(",", ""))
    return value if math.isfinite(value) else None


def close(first: float, second: float) -> bool:
    return math.isclose(first, second, rel_tol=1e-6, abs_tol=1e-12)


def numbers_in(text: str) -> Iterator[float]:
    """Every number ``text`` writes, a power of ten as one."""
    plain = to_plain(text)
    for match in _TIMES_TEN.finditer(plain):
        value = _power(match.group(1), match.group(2))
        if value is not None:
            yield value
    for match in _READ_NUMBER.finditer(_TIMES_TEN.sub(" ", plain)):
        value = _number(match.group(0))
        if value is not None:
            yield value


def leaves(data: Any) -> Iterator[Any]:
    """Every number and string in dumped data."""
    if isinstance(data, bool) or data is None:
        return
    if isinstance(data, int | float | str):
        yield data
    elif isinstance(data, dict):
        for item in data.values():
            yield from leaves(item)
    elif isinstance(data, list | tuple):
        for item in data:
            yield from leaves(item)


def measured(value: float, unit: str) -> Quantity:
    """A bound value with its unit, the unit read as the question's are ("deg", "J/kg·K")."""
    from app.modules.physics.givens import unit_expression

    reading = unit_dimension(unit_expression(unit) or unit) if unit else None
    if reading is None:
        return Quantity(value)
    dimension, scale, offset = reading
    return Quantity(value, value * scale + offset, dimension)


def _label_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern in (_LABEL, _YEAR, _NAMED, _CLAIM, _INDEX, _IN_FORMULA):
        spans += [match.span(1) for match in pattern.finditer(text)]
    listed = _LIST_NUMBER.match(text)
    if listed is not None:
        spans.append(listed.span(1))
    return spans


def stated_quantities(plain: str) -> tuple[list[Quantity], list[str]]:
    """Each value the question states that is no label, with its unit as the shared
    scanner reads it; and the numbers no float holds."""
    from app.modules.physics.givens import scan_givens

    labels = _label_spans(plain)
    units = {given.start: given for given in scan_givens(plain) if given.dimension is not None}
    found: list[Quantity] = []
    unheld: list[str] = []
    powers = [match.span() for match in _TIMES_TEN.finditer(plain)]
    for match in _TIMES_TEN.finditer(plain):
        if any(start <= match.start() < end for start, end in labels):
            continue
        value = _power(match.group(1), match.group(2))
        if value is None:
            unheld.append("number")
            continue
        given = units.get(match.start())
        if given is not None and given.si is not None and close(given.value, value):
            found.append(Quantity(value, given.si, given.dimension, *match.span(), "power"))
        else:
            found.append(Quantity(value, None, None, *match.span(), "power"))
    for match in _NUMBER.finditer(plain):
        if any(start <= match.start() < end for start, end in [*labels, *powers]):
            continue
        value = _number(match.group(0))
        if value is None:
            unheld.append("number")
            continue
        given = units.get(match.start())
        dimension, si = (given.dimension, given.si) if given else (None, None)
        found.append(Quantity(value, si, dimension, *match.span(), match.group(0)))
    return sorted(found, key=lambda item: item.start), unheld


def is_read(stated: Quantity, read: list[Quantity]) -> bool:
    """A stated quantity is read: the same kind at the same SI value or as written ("30°"
    against a bound 30 degrees), or, where one side writes no unit, the same number at
    some metric prefix. A sign the law gives it (a throw downward) is no difference."""
    for other in read:
        same_kind = stated.dimension and stated.dimension == other.dimension
        if same_kind and close(abs(stated.si or 0.0), abs(other.si or 0.0)):
            return True
        if any(close(abs(stated.value) * scale, abs(other.value)) for scale in _PREFIX_SCALES):
            return True
    return False
