# ruff: noqa: RUF002 -- textbook formulas use a proper minus sign.
"""Shared numbers and display helper for the extended chemistry solvers."""

from __future__ import annotations

import math
from itertools import pairwise

from app.modules.chemistry.solvers.types import ChemistryResult, format_number

KW = 1.0e-14
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
# Standard reduction potential and electrons for the common aqueous ion.
STANDARD_REDUCTION: dict[str, tuple[float, int]] = {
    "Na": (-2.71, 1),
    "Mg": (-2.37, 2),
    "Al": (-1.66, 3),
    "Zn": (-0.76, 2),
    "Fe": (-0.44, 2),
    "Ni": (-0.25, 2),
    "Pb": (-0.13, 2),
    "H": (0.0, 2),
    "Cu": (0.34, 2),
    "Ag": (0.80, 1),
}


def verified(
    title: str,
    given: tuple[str, ...] | list[str],
    find: str,
    formula_name: str,
    formula: str,
    substitution: tuple[str, ...] | list[str],
    answer: str,
    value: str,
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
    )


def num(value: float) -> str:
    return format_number(value)


def weak_dissociation(constant: float, concentration: float) -> float:
    """Positive root of x² + Kx − KC = 0."""
    from app.services.solving import SolveServiceError

    if constant <= 0 or concentration <= 0:
        raise SolveServiceError("weak equilibrium inputs must be positive")
    discriminant = constant * constant + 4 * constant * concentration
    return (-constant + math.sqrt(discriminant)) / 2


def water_vapor_mmhg(temperature_c: float) -> float | None:
    points = WATER_VAPOR_MMHG
    if temperature_c < points[0][0] or temperature_c > points[-1][0]:
        return None
    for (left_t, left_p), (right_t, right_p) in pairwise(points):
        if left_t <= temperature_c <= right_t:
            if right_t == left_t:
                return left_p
            span = (temperature_c - left_t) / (right_t - left_t)
            return left_p + span * (right_p - left_p)
    return None
