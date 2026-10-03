"""Every number a question states, with its unit and dimension.

A subject's extractors bind values by keyword. This scan is the independent record of what
the question actually supplied, so a request boundary can check that a verified solve did
not skip a stated quantity of the kind it used, and the binder can fill a law from it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.law_binding.units import UnitTable, unit_dimension
from app.services.number_text import numeric_spans

# Not quantities: "to 3 s.f.", "2 decimal places", "the 2nd ball", "m/s^2".
_NOT_A_GIVEN_AFTER = re.compile(
    # "s.f." must end there: "in 5 s. Find" is five seconds, then a sentence.
    r"\s*(?:s\.?\s?f\.?(?![a-z])|sig(?:nificant)?\.?\s*fig(?:ure)?s?|d\.?\s?p\.?\b"
    r"|decimal\s+places?"
    r"|(?:st|nd|rd|th)\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Given:
    """One stated number. ``dimension`` is None when it carries no known unit."""

    start: int
    end: int
    value: float
    unit: str
    dimension: str | None
    si: float | None


def scan_givens(text: str, units: UnitTable) -> list[Given]:
    """Every stated number in normalized solver input, in written order."""
    givens: list[Given] = []
    for start, end in numeric_spans(text):
        if text[max(0, start - 1) : start] == "^" or text[max(0, start - 2) : start] == "**":
            continue
        if _NOT_A_GIVEN_AFTER.match(text, end):
            continue
        try:
            value = float(text[start:end])
        except ValueError:
            continue
        unit = units.at(text, end)
        if unit is None:
            givens.append(Given(start, end, value, "", None, None))
            continue
        spelling, expression = unit
        reading = unit_dimension(expression)
        if reading is None:
            givens.append(Given(start, end, value, spelling, None, None))
            continue
        dimension, scale, offset = reading
        givens.append(Given(start, end, value, spelling, dimension, value * scale + offset))
    return givens
