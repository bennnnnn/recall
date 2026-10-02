# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Calorimetry, Hess's law, formation enthalpy, and bond enthalpy."""

from __future__ import annotations

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.equations import balance_equation
from app.modules.chemistry.solvers.common_chem import (
    inp,
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
    working: str
    if calorimeter is not None:
        if calorimeter <= 0:
            raise SolveServiceError("calorimeter constant must be positive")
        heat = -calorimeter * delta_t
        given = (f"Ccal = {inp(calorimeter)} J/°C", f"ΔT = {inp(delta_t)} °C")
        formula = "q_rxn = −Ccal ΔT"
        working = f"q_rxn = −({inp(calorimeter)})({inp(delta_t)})"
    else:
        mass = intent.params.get("mass")
        specific = intent.params.get("specific_heat")
        if mass is None or specific is None or mass <= 0 or specific <= 0:
            raise SolveServiceError("calorimetry needs Ccal or mass and specific heat")
        heat = -mass * specific * delta_t
        given = (
            f"m = {inp(mass)} g",
            f"c = {inp(specific)} J/(g·°C)",
            f"ΔT = {inp(delta_t)} °C",
        )
        formula = "q_rxn = −mcΔT"
        working = f"q_rxn = −({inp(mass)})({inp(specific)})({inp(delta_t)})"
    shown = f"q_rxn = {num(heat)} J"
    return verified(
        "Verified calorimetry",
        given,
        "Reaction heat",
        "Calorimetry",
        formula,
        ("q_system + q_surroundings = 0, so q_rxn = −q_system", working),
        shown,
        shown,
    )


def solve_hess(intent: ChemistryIntent) -> ChemistryResult:
    total = 0.0
    given: list[str] = []
    terms: list[str] = []
    index = 1
    while f"dh{index}" in intent.params:
        enthalpy = intent.params[f"dh{index}"]
        multiplier = intent.params.get(f"m{index}")
        if multiplier is None:
            raise SolveServiceError(f"Hess step {index} needs a multiplier")
        total += multiplier * enthalpy
        given.append(f"ΔH{index} = {inp(enthalpy)} kJ, multiplied by {inp(multiplier)}")
        terms.append(f"({inp(multiplier)})({inp(enthalpy)})")
        index += 1
    if not terms:
        raise SolveServiceError("Hess's law needs at least one enthalpy step")
    shown = f"ΔH = {num(total)} kJ"
    return verified(
        "Verified Hess's law",
        given,
        "Overall enthalpy",
        "Hess's law",
        "ΔH = Σ mi ΔHi",
        (f"ΔH = {' + '.join(terms)}",),
        shown,
        shown,
    )


# Reference states: formula → phases that are the standard state (None = unlabeled).
_GASEOUS_ELEMENTS = {"H2", "N2", "O2", "F2", "Cl2", "He", "Ne", "Ar", "Kr", "Xe", "Rn"}
_SOLID_ALLOTROPES = {"S8", "P4"}
# These elements are standard as molecules (H2, Br2, I2), not as the free atom.
_MOLECULAR_ELEMENT_ATOMS = {"H", "N", "O", "F", "Cl", "Br", "I"}


def _is_standard_state(formula: str, atoms: int, phase: str | None) -> bool:
    """True for the form ΔHf = 0 refers to: O2, not O3 or O(g); Br2(l), not Br2(g)."""
    if formula in _GASEOUS_ELEMENTS:
        return phase in {None, "g"}
    if formula == "Br2":
        return phase in {None, "l"}
    if formula == "I2":
        return phase in {None, "s"}
    if formula == "Hg":
        return phase in {None, "l"}
    if formula in _SOLID_ALLOTROPES:
        return phase in {None, "s"}
    # S8 and P4 are the standard allotropes. Bare P and S are not, same as O3.
    # H, N, O, F, Cl, Br, and I are not metals: an unlabeled atom is not ΔHf = 0.
    if formula in {"P", "S"} or formula in _MOLECULAR_ELEMENT_ATOMS:
        return False
    # Metals and graphite: a monatomic solid.
    return atoms == 1 and phase in {None, "s"} and formula not in _GASEOUS_ELEMENTS


def _formation(label: str, table: dict[str, float]) -> float:
    if label in table:
        return table[label]
    species = parse_species(label, coefficient_already_removed=True)
    if species is not None and len(species.composition) == 1 and species.charge == 0:
        element, atoms = next(iter(species.composition.items()))
        if _is_standard_state(species.formula, atoms, species.phase) and element:
            return 0.0
        raise SolveServiceError(
            f"{label} is not the standard state of {element}; its formation enthalpy is needed"
        )
    raise SolveServiceError(f"missing formation enthalpy for {label}")


def solve_formation(intent: ChemistryIntent) -> ChemistryResult:
    if not intent.equation:
        raise SolveServiceError("a formation reaction is required")
    balanced = balance_equation(intent.equation)
    if not balanced.balanced:
        raise SolveServiceError(balanced.error or "equation could not be balanced")
    product_terms = [
        (coefficient, _formation(species, intent.species))
        for species, coefficient in balanced.products.items()
    ]
    reactant_terms = [
        (coefficient, _formation(species, intent.species))
        for species, coefficient in balanced.reactants.items()
    ]
    products = sum(coefficient * value for coefficient, value in product_terms)
    reactants = sum(coefficient * value for coefficient, value in reactant_terms)
    value = products - reactants

    def side(terms: list[tuple[int, float]]) -> str:
        return " + ".join(f"({coefficient})({inp(item)})" for coefficient, item in terms)

    shown = f"ΔH° = {num(value)} kJ/mol"
    return verified(
        "Verified formation enthalpy",
        (
            intent.equation,
            *(f"ΔHf({name}) = {inp(amount)} kJ/mol" for name, amount in intent.species.items()),
            "ΔHf = 0 for an element in its standard state",
        ),
        "Standard reaction enthalpy",
        "Formation enthalpies",
        "ΔH°rxn = Σ n ΔHf°(products) − Σ n ΔHf°(reactants)",
        (f"ΔH° = [{side(product_terms)}] − [{side(reactant_terms)}]",),
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
        (f"bonds broken = {inp(broken)} kJ", f"bonds formed = {inp(formed)} kJ"),
        "Reaction enthalpy",
        "Bond enthalpies",
        "ΔH ≈ Σ broken − Σ formed",
        (f"ΔH = {inp(broken)} − {inp(formed)}",),
        shown,
        shown,
    )
