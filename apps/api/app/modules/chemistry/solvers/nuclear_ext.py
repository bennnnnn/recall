# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Decay constant, exponential decay, activity, and nuclear equations."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.nuclear import (
    balance_nuclear,
    conservation_lines,
    decay_equation,
    format_nuclear,
    parse_nuclide,
)
from app.modules.chemistry.solvers.common_chem import (
    inp,
    num,
    verified,
)
from app.modules.chemistry.solvers.params import require
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError


def solve_decay_constant(intent: ChemistryIntent) -> ChemistryResult:
    half_life = intent.params.get("half_life")
    if half_life is None or half_life <= 0:
        raise SolveServiceError("half-life must be positive")
    unit = intent.units.get("time", "s")
    shown = f"λ = {num(math.log(2) / half_life)} {unit}⁻¹"
    return verified(
        "Verified decay constant",
        (f"t₁/₂ = {inp(half_life)} {unit}",),
        "Decay constant",
        "Decay constant",
        "λ = ln(2) / t₁/₂",
        (f"λ = {num(math.log(2))} / {inp(half_life)}",),
        shown,
        shown,
    )


def _three(intent: ChemistryIntent, a: str, b: str, c: str) -> tuple[float, float, float]:
    message = "decay inputs are missing or negative"
    return (
        require(intent, a, non_negative=True, message=message),
        require(intent, b, non_negative=True, message=message),
        require(intent, c, non_negative=True, message=message),
    )


def solve_exponential_decay(intent: ChemistryIntent) -> ChemistryResult:
    initial, constant, time = _three(intent, "initial", "decay_constant", "time")
    shown = f"N = {num(initial * math.exp(-constant * time))}"
    return verified(
        "Verified exponential decay",
        (f"N₀ = {inp(initial)}", f"λ = {inp(constant)}", f"t = {inp(time)}"),
        "Amount remaining",
        "Exponential decay",
        "N = N₀e^(−λt)",
        (f"N = ({inp(initial)})e^(−({inp(constant)})({inp(time)}))",),
        shown,
        shown,
    )


def solve_nuclear_activity(intent: ChemistryIntent) -> ChemistryResult:
    constant = intent.params.get("decay_constant")
    particles = intent.params.get("particles")
    if constant is None or particles is None or constant < 0 or particles < 0:
        raise SolveServiceError("activity needs λ and N")
    shown = f"A = {num(constant * particles)}"
    return verified(
        "Verified nuclear activity",
        (f"λ = {inp(constant)}", f"N = {inp(particles)}"),
        "Activity",
        "Activity",
        "A = λN",
        (f"A = ({inp(constant)})({inp(particles)})",),
        shown,
        shown,
    )


def solve_nuclear_equation(intent: ChemistryIntent) -> ChemistryResult:
    if intent.equation:
        balanced = balance_nuclear(intent.equation)
        if not balanced.balanced:
            raise SolveServiceError(balanced.error or "nuclear equation does not balance")
    else:
        parent = parse_nuclide(intent.formula or "")
        if parent is None or parent.is_particle:
            raise SolveServiceError("nuclear decay needs a nuclide such as 238U")
        decayed = decay_equation(parent.mass_number, parent.symbol, intent.target or "")
        if decayed is None:
            raise SolveServiceError("that decay mode is not determined")
        balanced = decayed
    shown = format_nuclear(balanced)
    return verified(
        "Verified nuclear equation",
        (intent.equation or f"{intent.formula} {intent.target}",),
        "Balanced nuclear equation",
        "Nucleon and charge balance",
        "sum of A and sum of Z are equal on both sides",
        conservation_lines(balanced),
        shown,
        shown,
    )
