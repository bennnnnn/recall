# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Calorimetry, Hess's law, formation enthalpy, and bond enthalpy."""

from __future__ import annotations

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.equations import balance_equation
from app.modules.chemistry.solvers.common_chem import (
    num,
    verified,
)
from app.modules.chemistry.solvers.types import ChemistryResult
from app.modules.chemistry.species import parse_species
from app.services.solving import SolveServiceError


def solve_calorimetry(intent: ChemistryIntent) -> ChemistryResult:
    delta_t = intent.params.get("delta_t")
    if delta_t is None:
        raise SolveServiceError("calorimetry needs ΔT")
    calorimeter = intent.params.get("c_cal")
    given: tuple[str, ...]
    formula: str
    if calorimeter is not None:
        if calorimeter <= 0:
            raise SolveServiceError("calorimeter constant must be positive")
        heat = -calorimeter * delta_t
        given = (f"Ccal = {num(calorimeter)} J/°C", f"ΔT = {num(delta_t)} °C")
        formula = "q_rxn = −Ccal ΔT"
    else:
        mass = intent.params.get("mass")
        specific = intent.params.get("specific_heat")
        if mass is None or specific is None or mass <= 0 or specific <= 0:
            raise SolveServiceError("calorimetry needs Ccal or mass and specific heat")
        heat = -mass * specific * delta_t
        given = (
            f"m = {num(mass)} g",
            f"c = {num(specific)} J/(g·°C)",
            f"ΔT = {num(delta_t)} °C",
        )
        formula = "q_rxn = −mcΔT"
    shown = f"q_rxn = {num(heat)} J"
    return verified(
        "Verified calorimetry",
        given,
        "Reaction heat",
        "Calorimetry",
        formula,
        ("q_system + q_surroundings = 0", shown),
        shown,
        shown,
    )


def solve_hess(intent: ChemistryIntent) -> ChemistryResult:
    total = 0.0
    lines: list[str] = []
    index = 1
    while f"dh{index}" in intent.params:
        enthalpy = intent.params[f"dh{index}"]
        multiplier = intent.params.get(f"m{index}")
        if multiplier is None:
            raise SolveServiceError(f"Hess step {index} needs a multiplier")
        total += multiplier * enthalpy
        lines.append(f"{num(multiplier)} × {num(enthalpy)}")
        index += 1
    if not lines:
        raise SolveServiceError("Hess's law needs at least one enthalpy step")
    shown = f"ΔH = {num(total)} kJ"
    return verified(
        "Verified Hess's law",
        tuple(lines),
        "Overall enthalpy",
        "Hess's law",
        "ΔH = Σ mi ΔHi",
        (shown,),
        shown,
        shown,
    )


def _formation(label: str, table: dict[str, float]) -> float:
    if label in table:
        return table[label]
    species = parse_species(label, coefficient_already_removed=True)
    if species is not None and len(species.composition) == 1 and species.charge == 0:
        return 0.0
    raise SolveServiceError(f"missing formation enthalpy for {label}")


def solve_formation(intent: ChemistryIntent) -> ChemistryResult:
    if not intent.equation:
        raise SolveServiceError("a formation reaction is required")
    balanced = balance_equation(intent.equation)
    if not balanced.balanced:
        raise SolveServiceError(balanced.error or "equation could not be balanced")
    products = sum(
        coefficient * _formation(species, intent.species)
        for species, coefficient in balanced.products.items()
    )
    reactants = sum(
        coefficient * _formation(species, intent.species)
        for species, coefficient in balanced.reactants.items()
    )
    value = products - reactants
    shown = f"ΔH° = {num(value)} kJ/mol"
    return verified(
        "Verified formation enthalpy",
        (
            intent.equation,
            *(f"ΔHf({name}) = {num(amount)}" for name, amount in intent.species.items()),
        ),
        "Standard reaction enthalpy",
        "Formation enthalpies",
        "ΔH°rxn = Σ n ΔHf°(products) − Σ n ΔHf°(reactants)",
        (shown,),
        shown,
        shown,
    )


def solve_bond_enthalpy(intent: ChemistryIntent) -> ChemistryResult:
    broken = intent.params.get("broken")
    formed = intent.params.get("formed")
    if broken is None or formed is None:
        raise SolveServiceError("bond enthalpy needs bonds broken and bonds formed")
    value = broken - formed
    shown = f"ΔH = {num(value)} kJ"
    return verified(
        "Verified bond enthalpy",
        (f"bonds broken = {num(broken)} kJ", f"bonds formed = {num(formed)} kJ"),
        "Reaction enthalpy",
        "Bond enthalpies",
        "ΔH ≈ Σ broken − Σ formed",
        (shown,),
        shown,
        shown,
    )
