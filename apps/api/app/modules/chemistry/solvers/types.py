# ruff: noqa: RUF001 -- textbook chemistry uses multiplication notation.
"""Shared chemistry result type and display-safe number formatting."""

from __future__ import annotations

import math
from dataclasses import dataclass


def format_number(value: float, *, significant: int = 6) -> str:
    """Human-readable value without calculator ``e`` or trailing zero noise."""
    if value == 0:
        return "0"
    exponent = math.floor(math.log10(abs(value)))
    if exponent < -3 or exponent >= 6:
        coefficient = value / (10**exponent)
        return f"{coefficient:.{significant - 1}g} × 10^{exponent}"
    return f"{value:.{significant}g}"


@dataclass(frozen=True)
class ChemistryResult:
    """A verified calculation already separated into scan-friendly sections."""

    title: str
    given: tuple[str, ...]
    find: str
    formula_name: str
    formula: str
    substitution: tuple[str, ...]
    answer: str
    answer_value: str
