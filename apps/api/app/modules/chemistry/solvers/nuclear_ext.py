# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Decay constant, exponential decay, activity, and nuclear equations."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.nuclear import balance_nuclear, decay_product, format_nuclear
from app.modules.chemistry.solvers.common_chem import (
    num,
    verified,
)
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import MathServiceError


def solve_decay_constant(intent: ChemistryIntent) -> ChemistryResult:
    half_life = intent.params.get("half_life")
    if half_life is None or half_life <= 0:
        raise MathServiceError("half-life must be positive")
    unit = intent.units.get("time", "s")
    shown = f"λ = {num(math.log(2) / half_life)} {unit}⁻¹"
    return verified(
        "Verified decay constant",
        (f"t₁/₂ = {num(half_life)} {unit}",),
        "Decay constant",
        "Decay constant",
        "λ = ln(2) / t₁/₂",
        (shown,),
        shown,
        shown,
    )


def _three(intent: ChemistryIntent, a: str, b: str, c: str) -> tuple[float, float, float]:
    values = [intent.params.get(a), intent.params.get(b), intent.params.get(c)]
    if any(value is None or value < 0 for value in values):
        raise MathServiceError("decay inputs cannot be negative")
    return float(values[0] or 0), float(values[1] or 0), float(values[2] or 0)


def solve_exponential_decay(intent: ChemistryIntent) -> ChemistryResult:
    initial, constant, time = _three(intent, "initial", "decay_constant", "time")
    shown = f"N = {num(initial * math.exp(-constant * time))}"
    return verified(
        "Verified exponential decay",
        (f"N₀ = {num(initial)}", f"λ = {num(constant)}", f"t = {num(time)}"),
        "Amount remaining",
        "Exponential decay",
        "N = N₀e^(−λt)",
        (shown,),
        shown,
        shown,
    )


def solve_nuclear_activity(intent: ChemistryIntent) -> ChemistryResult:
    constant = intent.params.get("decay_constant")
    particles = intent.params.get("particles")
    if constant is None or particles is None or constant < 0 or particles < 0:
        raise MathServiceError("activity needs λ and N")
    shown = f"A = {num(constant * particles)}"
    return verified(
        "Verified nuclear activity",
        (f"λ = {num(constant)}", f"N = {num(particles)}"),
        "Activity",
        "Activity",
        "A = λN",
        (shown,),
        shown,
        shown,
    )


def solve_nuclear_equation(intent: ChemistryIntent) -> ChemistryResult:
    if intent.equation:
        balanced = balance_nuclear(intent.equation)
        if not balanced.balanced:
            raise MathServiceError(balanced.error or "nuclear equation does not balance")
        shown = format_nuclear(balanced)
    else:
        formula = intent.formula or ""
        mode = intent.target or ""
        mass_text = ""
        symbol = formula
        digits = ""
        for char in formula:
            if char.isdigit():
                digits += char
            else:
                symbol = formula[len(digits) :]
                break
        mass_text = digits
        mass = int(mass_text) if mass_text else int(intent.params.get("mass") or 0)
        shown_value = decay_product(mass, symbol, mode)
        if not shown_value:
            raise MathServiceError("that decay mode is not determined")
        shown = shown_value
    return verified(
        "Verified nuclear equation",
        (intent.equation or f"{intent.formula} {intent.target}",),
        "Balanced nuclear equation",
        "Nucleon and charge balance",
        "ΔA = 0 and ΔZ = 0",
        (shown,),
        shown,
        shown,
    )
