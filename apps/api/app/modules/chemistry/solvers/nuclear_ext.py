# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Decay constant, exponential decay, activity, and nuclear equations."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.nuclear import balance_nuclear, conservation_lines, format_nuclear
from app.modules.chemistry.solvers.common_chem import (
    inp,
    num,
    verified,
)
from app.modules.chemistry.solvers.params import require_all
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
        *stated("decay_constant"),
        (f"λ = {num(math.log(2))} / {inp(half_life)}",),
        shown,
        shown,
    )


def solve_exponential_decay(intent: ChemistryIntent) -> ChemistryResult:
    initial, constant, time = require_all(
        intent,
        "initial",
        "decay_constant",
        "time",
        non_negative=True,
        message="decay inputs are missing or negative",
    )
    shown = f"N = {num(initial * math.exp(-constant * time))}"
    return verified(
        "Verified exponential decay",
        (f"N₀ = {inp(initial)}", f"λ = {inp(constant)}", f"t = {inp(time)}"),
        "Amount remaining",
        *stated("exponential_decay"),
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
        *stated("nuclear_activity"),
        (f"A = ({inp(constant)})({inp(particles)})",),
        shown,
        shown,
    )


def solve_nuclear_equation(intent: ChemistryIntent) -> ChemistryResult:
    if not intent.equation:
        raise SolveServiceError("a nuclear equation is required")
    balanced = balance_nuclear(intent.equation)
    if not balanced.balanced:
        raise SolveServiceError(balanced.error or "nuclear equation does not balance")
    shown = format_nuclear(balanced)
    return verified(
        "Verified nuclear equation",
        (intent.equation,),
        "Balanced nuclear equation",
        *stated("nuclear_equation"),
        conservation_lines(balanced),
        shown,
        shown,
    )
