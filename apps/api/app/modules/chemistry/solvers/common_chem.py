# ruff: noqa: RUF002 -- textbook formulas use a proper minus sign.
"""Shared numbers and display helper for the extended chemistry solvers."""

from __future__ import annotations

import math
from itertools import pairwise

from app.modules.chemistry import sig_figs
from app.modules.chemistry.solvers.types import (
    INPUT_FIGURES,
    ChemistryResult,
    format_constant,
    format_molar_mass,
    format_number,
)
from app.services.solving import SolveServiceError

# Below this an ion concentration is comparable to the 1e-7 M that water supplies itself.
_DILUTE_ION = 1.0e-6
# mmHg vapor pressure of water. Values between points are linearly interpolated.
WATER_VAPOR_MMHG: tuple[tuple[float, float], ...] = (
    (0, 4.58),
    (5, 6.54),
    (10, 9.21),
    (15, 12.79),
    (20, 17.54),
    (25, 23.76),
    (30, 31.82),
    (35, 42.18),
    (40, 55.32),
    (45, 71.88),
    (50, 92.51),
    (60, 149.4),
    (70, 233.7),
    (80, 355.1),
    (90, 525.8),
    (100, 760.0),
)


def verified(
    title: str,
    given: tuple[str, ...] | list[str],
    find: str,
    formula_name: str,
    formula: str,
    substitution: tuple[str, ...] | list[str],
    answer: str,
    value: str,
    *,
    verbatim: bool = False,
) -> ChemistryResult:
    return ChemistryResult(
        title,
        tuple(given),
        find,
        formula_name,
        formula,
        tuple(substitution),
        answer,
        value,
        verbatim=verbatim,
    )


def _fixed(value: float, places: int) -> str:
    """A value to fixed decimal places, never a negative zero (−0.00)."""
    text = f"{value:.{places}f}"
    return text.removeprefix("-") if float(text) == 0 else text


def num(value: float) -> str:
    """A computed value, to the significant figures the question's data carry."""
    written = sig_figs.current()
    if written is not None and written.additive and written.decimals is not None:
        return _fixed(value, written.decimals)
    if written is not None and written.figures is not None:
        return format_number(value, significant=written.figures, keep_zeros=True)
    return format_number(value)


def p_value(value: float) -> str:
    """A pH, pOH or pK: a logarithm, so its precision is decimal places (pH 3.49)."""
    written = sig_figs.current()
    if written is not None and written.decimals is not None:
        return _fixed(value, written.decimals)
    return num(value)


def inp(value: float) -> str:
    """A value the user supplied, echoed as typed (1.10 V) or, if derived, unrounded (273.15 K)."""
    written = sig_figs.current()
    typed = None if written is None else written.written.get(repr(value))
    if typed is not None:
        return sig_figs.as_written(typed)
    return format_number(value, significant=INPUT_FIGURES)


def const(value: float) -> str:
    """A physical constant, one figure more precise than an answer."""
    return format_constant(value)


def molar_mass_text(value: float) -> str:
    """A molar mass that is the answer, to two decimals by convention (98.07 g/mol)."""
    return format_molar_mass(value)


def molar_mass_working(value: float) -> str:
    """A molar mass inside a calculation, to the element table's precision (18.015).

    Two decimals there would not reproduce the answer: 4 / 2.02 × 18.02 is 35.68 g, while
    4 g of H2 makes 35.74 g of water.
    """
    return f"{value:.3f}"


def atomic_mass(value: float) -> str:
    """A tabulated atomic mass exactly as the table gives it (1.008, 15.999, 196.967)."""
    return format_number(value, significant=6)


def weak_dissociation(constant: float, concentration: float) -> float:
    """Positive root of x² + Kx − KC = 0."""
    if constant <= 0 or concentration <= 0:
        raise SolveServiceError("weak equilibrium inputs must be positive")
    discriminant = constant * constant + 4 * constant * concentration
    amount = (-constant + math.sqrt(discriminant)) / 2
    if amount < _DILUTE_ION:
        # Water's own 1e-7 M is no longer negligible, so the quadratic is not the answer.
        raise SolveServiceError("water's contribution is required for this very weak electrolyte")
    return amount


def water_vapor_mmhg(temperature_c: float) -> float | None:
    """Vapor pressure of water. Exact at the table points, log-linear in 1/T between them.

    ln P is close to linear in 1/T (Clausius–Clapeyron), so this is accurate between
    points where a straight line in P would overshoot by 1–2 % (22 °C: 19.83 mmHg).
    """
    points = WATER_VAPOR_MMHG
    if temperature_c < points[0][0] or temperature_c > points[-1][0]:
        return None
    for (left_t, left_p), (right_t, right_p) in pairwise(points):
        if left_t <= temperature_c <= right_t:
            left_inv = 1 / (left_t + 273.15)
            right_inv = 1 / (right_t + 273.15)
            span = (1 / (temperature_c + 273.15) - left_inv) / (right_inv - left_inv)
            return math.exp(math.log(left_p) + span * (math.log(right_p) - math.log(left_p)))
    return None
