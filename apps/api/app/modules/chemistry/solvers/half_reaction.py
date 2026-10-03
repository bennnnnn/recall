"""Construct one half-reaction from a written redox pair and its medium.

Water, H+ or OH-, and electrons may be added. Several species on a side are a
different equation and are not completed here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import gcd

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.equations import written_is_balanced
from app.modules.chemistry.solvers.common_chem import verified
from app.modules.chemistry.solvers.types import ChemistryResult
from app.modules.chemistry.species import ChemicalSpecies, canonical_label, parse_reaction
from app.modules.chemistry.structure import oxidation_states
from app.services.solving import SolveServiceError

_ADDED = ("H2O", "H+", "OH-", "e-")


@dataclass(frozen=True)
class _Built:
    equation: str
    element: str
    electrons: int


def solve_half_reaction(intent: ChemistryIntent) -> ChemistryResult:
    equation = intent.equation or ""
    medium = intent.target
    if medium not in {"acidic", "basic"}:
        raise SolveServiceError("a half-reaction needs an acidic or basic medium")
    pair = _pair(equation)
    if pair is None:
        raise SolveServiceError("a half-reaction needs one species on each side")
    built = _construct(*pair, medium)
    if not written_is_balanced(built.equation):
        raise SolveServiceError("the half-reaction did not balance")
    left, right = pair
    return verified(
        "Verified half-reaction",
        (
            f"Pair: {canonical_label(left)} -> {canonical_label(right)}",
            f"Medium: {medium}",
        ),
        "Balanced half-reaction",
        *stated("half_reaction"),
        (
            f"the oxidation number of {built.element} changes",
            f"add H2O, then {'OH-' if medium == 'basic' else 'H+'}, then {built.electrons} e-",
        ),
        built.equation,
        built.equation,
    )


def _pair(equation: str) -> tuple[ChemicalSpecies, ChemicalSpecies] | None:
    reaction = parse_reaction(equation)
    if reaction is None or len(reaction.reactants) != 1 or len(reaction.products) != 1:
        return None
    left = replace(reaction.reactants[0].species, phase=None)
    right = replace(reaction.products[0].species, phase=None)
    if left.electron or right.electron:
        return None
    return left, right


def _construct(left: ChemicalSpecies, right: ChemicalSpecies, medium: str) -> _Built:
    element, left_count, right_count = _redox_element(left, right)
    divisor = gcd(left_count, right_count)
    reactant_coefficient = right_count // divisor
    product_coefficient = left_count // divisor
    reactants = {canonical_label(left): reactant_coefficient}
    products = {canonical_label(right): product_coefficient}
    _balance_oxygen(left, right, reactant_coefficient, product_coefficient, reactants, products)
    _balance_hydrogen(left, right, reactant_coefficient, product_coefficient, reactants, products)
    electrons = _balance_charge(
        left, right, reactant_coefficient, product_coefficient, reactants, products
    )
    if medium == "basic":
        _to_basic(reactants, products)
    return _Built(
        f"{_side(reactants, canonical_label(left))} -> {_side(products, canonical_label(right))}",
        element,
        electrons,
    )


def _redox_element(left: ChemicalSpecies, right: ChemicalSpecies) -> tuple[str, int, int]:
    left_states = oxidation_states(canonical_label(left))
    right_states = oxidation_states(canonical_label(right))
    if left_states is None or right_states is None:
        raise SolveServiceError("oxidation states are ambiguous")
    shared = set(left.composition) & set(right.composition)
    changed = [element for element in shared if left_states[element] != right_states[element]]
    if len(changed) != 1:
        raise SolveServiceError("the pair is not one redox change")
    extras = (set(left.composition) | set(right.composition)) - shared - {"H", "O"}
    if extras:
        raise SolveServiceError("an element in the pair is not on both sides")
    element = changed[0]
    return element, left.composition[element], right.composition[element]


def _balance_oxygen(
    left: ChemicalSpecies,
    right: ChemicalSpecies,
    reactant_coefficient: int,
    product_coefficient: int,
    reactants: dict[str, int],
    products: dict[str, int],
) -> None:
    oxygen_left = reactant_coefficient * left.composition.get("O", 0)
    oxygen_right = product_coefficient * right.composition.get("O", 0)
    if oxygen_left > oxygen_right:
        products["H2O"] = oxygen_left - oxygen_right
    elif oxygen_right > oxygen_left:
        reactants["H2O"] = oxygen_right - oxygen_left


def _balance_hydrogen(
    left: ChemicalSpecies,
    right: ChemicalSpecies,
    reactant_coefficient: int,
    product_coefficient: int,
    reactants: dict[str, int],
    products: dict[str, int],
) -> None:
    hydrogen_left = reactant_coefficient * left.composition.get("H", 0) + 2 * reactants.get(
        "H2O", 0
    )
    hydrogen_right = product_coefficient * right.composition.get("H", 0) + 2 * products.get(
        "H2O", 0
    )
    if hydrogen_right > hydrogen_left:
        reactants["H+"] = hydrogen_right - hydrogen_left
    elif hydrogen_left > hydrogen_right:
        products["H+"] = hydrogen_left - hydrogen_right


def _balance_charge(
    left: ChemicalSpecies,
    right: ChemicalSpecies,
    reactant_coefficient: int,
    product_coefficient: int,
    reactants: dict[str, int],
    products: dict[str, int],
) -> int:
    charge_left = reactant_coefficient * left.charge + reactants.get("H+", 0)
    charge_right = product_coefficient * right.charge + products.get("H+", 0)
    electrons = charge_left - charge_right
    if electrons > 0:
        reactants["e-"] = electrons
    elif electrons < 0:
        products["e-"] = -electrons
    else:
        raise SolveServiceError("the pair does not transfer electrons")
    return abs(electrons)


def _to_basic(reactants: dict[str, int], products: dict[str, int]) -> None:
    """Replace H+ with water and hydroxide, then cancel water that appears twice."""
    protons_left = reactants.pop("H+", 0)
    protons_right = products.pop("H+", 0)
    if protons_left:
        reactants["H2O"] = reactants.get("H2O", 0) + protons_left
        products["OH-"] = products.get("OH-", 0) + protons_left
    elif protons_right:
        products["H2O"] = products.get("H2O", 0) + protons_right
        reactants["OH-"] = reactants.get("OH-", 0) + protons_right
    cancel = min(reactants.get("H2O", 0), products.get("H2O", 0))
    if cancel == 0:
        return
    reactants["H2O"] -= cancel
    products["H2O"] -= cancel


def _side(counts: dict[str, int], primary: str) -> str:
    labels = [primary, *(label for label in _ADDED if counts.get(label, 0) > 0)]
    return " + ".join(
        label if counts[label] == 1 else f"{counts[label]} {label}" for label in labels
    )
