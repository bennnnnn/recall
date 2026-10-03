# ruff: noqa: RUF001, RUF002, RUF003 -- textbook chemistry uses multiplication notation.
"""Shared chemistry result type and display-safe number formatting."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.models.schemas.chemistry.scene import ChemistryScene

# A textbook answer carries as many figures as its least precise input, and the inputs a
# student types have two to four. Four is enough to check a hand calculation without printing
# the noise of a double.
SIGNIFICANT_FIGURES = 4
# A value the user typed is echoed as typed, not rounded to answer precision.
INPUT_FIGURES = 6
# Physical constants are echoed with one more figure than an answer so they never limit it.
CONSTANT_FIGURES = 5


def _round_significant(value: float, digits: int) -> tuple[float, int]:
    """``value`` rounded to ``digits`` significant digits as ``(mantissa, exponent)``."""
    mantissa, exponent = f"{value:.{digits - 1}e}".split("e")
    return float(mantissa), int(exponent)


def _trim(text: str) -> str:
    return text.rstrip("0").rstrip(".") if "." in text else text


def format_number(
    value: float, *, significant: int = SIGNIFICANT_FIGURES, keep_zeros: bool = False
) -> str:
    """Human-readable value without calculator ``e`` or trailing zero noise.

    Rounds to significant digits *first*, then chooses plain or scientific form, so
    999999.7 is ``1 × 10^6`` (not ``1e+06``) and 9.999996e-4 is ``0.001`` (not
    ``10 × 10^-4``). Plain form is fixed-point, so 19983 stays ``19980`` instead of
    ``1.998e+04``.
    """
    if value == 0:
        return "0"
    if not math.isfinite(value):
        return str(value)
    mantissa, exponent = _round_significant(value, significant)
    # Once the answer's figures come from the data, a whole number whose digits rounding
    # replaced with zeros is written in powers of ten: 1780 to two figures is 1.8 × 10^3,
    # since 1800 would read as measured. Zeros that are the number's own digits stay plain:
    # 200 is 200, and 110.02 g to two figures is 110 g.
    rounded_to_zeros = exponent >= significant and round(mantissa * 10.0**exponent) != round(value)
    tidy = (lambda text: text) if keep_zeros else _trim
    if exponent < -3 or exponent >= 6 or (keep_zeros and rounded_to_zeros):
        return f"{tidy(f'{mantissa:.{significant - 1}f}')} × 10^{exponent}"
    decimals = max(significant - 1 - exponent, 0)
    return tidy(f"{float(f'{value:.{significant - 1}e}'):.{decimals}f}")


def format_constant(value: float) -> str:
    """A physical constant echoed in a Substitution line (R, F, Nₐ)."""
    return format_number(value, significant=CONSTANT_FIGURES)


def format_molar_mass(value: float) -> str:
    """Molar masses are quoted to two decimals by convention (180.16, not 180.2)."""
    return f"{value:.2f}"


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
    # True when the text carries SMILES or atom labels (``C1CCCCC1``, ``C2=C3: E``) whose
    # digits are not subscripts; ``notation.typeset`` must leave such a result alone.
    verbatim: bool = False
