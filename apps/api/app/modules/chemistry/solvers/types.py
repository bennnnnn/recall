# ruff: noqa: RUF001, RUF002 -- textbook chemistry uses multiplication notation.
"""Shared chemistry result type and display-safe number formatting."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.models.schemas.chemistry.scene import ChemistryScene


def _round_significant(value: float, digits: int) -> tuple[float, int]:
    """``value`` rounded to ``digits`` significant digits as ``(mantissa, exponent)``."""
    mantissa, exponent = f"{value:.{digits - 1}e}".split("e")
    return float(mantissa), int(exponent)


def format_number(value: float, *, significant: int = 6) -> str:
    """Human-readable value without calculator ``e`` or trailing zero noise.

    Rounds to significant digits *first*, then chooses plain or scientific form, so
    999999.7 is ``1 × 10^6`` (not ``1e+06``) and 9.999996e-4 is ``0.001`` (not
    ``10 × 10^-4``).
    """
    if value == 0:
        return "0"
    if not math.isfinite(value):
        return str(value)
    _mantissa, exponent = _round_significant(value, significant)
    if exponent < -3 or exponent >= 6:
        coefficient, exponent = _round_significant(value, significant - 1)
        return f"{coefficient:.{significant}g} × 10^{exponent}"
    return f"{float(f'{value:.{significant - 1}e}'):.{significant}g}"


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
    scene: ChemistryScene | None = None
    structure_smiles: str | None = None
