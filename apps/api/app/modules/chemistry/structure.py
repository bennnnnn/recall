"""Oxidation states and a bounded Lewis / VSEPR builder.

Oxidation states follow the school assignment order and return None when more
than one element is still unknown. VSEPR is only returned when there is one
non-hydrogen central atom. Expanded octets are allowed from period 3 onward,
and only when they lower the formal-charge total.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.chemistry.elements import BY_SYMBOL, valence_electrons
from app.modules.chemistry.species import ChemicalSpecies, parse_species

_NONMETALS = frozenset(
    {"B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Ge", "As", "Se", "Br", "Sb", "Te", "I"}
)
_HALOGENS = frozenset({"Cl", "Br", "I"})
# Common polyatomic ions, tried only after the element rules leave several unknowns.
_POLYATOMIC: tuple[tuple[dict[str, int], int], ...] = (
    ({"S": 1, "O": 4}, -2),
    ({"P": 1, "O": 4}, -3),
    ({"C": 1, "O": 3}, -2),
    ({"N": 1, "O": 3}, -1),
    ({"S": 1, "O": 3}, -2),
    ({"N": 1, "O": 2}, -1),
    ({"C": 1, "N": 1}, -1),
    ({"O": 1, "H": 1}, -1),
    ({"N": 1, "H": 4}, 1),
)

_GEOMETRIES: dict[tuple[int, int], tuple[str, str]] = {
    (2, 0): ("linear", "180°"),
    (3, 0): ("trigonal planar", "120°"),
    (3, 1): ("bent", "120°"),
    (4, 0): ("tetrahedral", "109.5°"),
    (4, 1): ("trigonal pyramidal", "109.5°"),
    (4, 2): ("bent", "109.5°"),
    (5, 0): ("trigonal bipyramidal", "90° and 120°"),
    (5, 1): ("seesaw", "90° and 120°"),
    (5, 2): ("T-shaped", "90°"),
    (5, 3): ("linear", "180°"),
    (6, 0): ("octahedral", "90°"),
    (6, 1): ("square pyramidal", "90°"),
    (6, 2): ("square planar", "90°"),
}
_HYBRID = {2: "sp", 3: "sp2", 4: "sp3", 5: "sp3d", 6: "sp3d2"}


@dataclass(frozen=True)
class LewisStructure:
    """A central-atom Lewis description, not an arbitrary drawing."""

    formula: str
    central: str
    bond_orders: tuple[int, ...]
    central_lone_pairs: int
    terminal_elements: tuple[str, ...]
    geometry: str
    bond_angle: str
    polar: bool
    hybridization: str
    central_formal_charge: int
    electrons: int


def _consume(composition: dict[str, int], atoms: dict[str, int]) -> dict[str, int] | None:
    left = dict(composition)
    for element, count in atoms.items():
        if left.get(element, 0) < count:
            return None
        left[element] -= count
        if left[element] == 0:
            del left[element]
    return left


def oxidation_states(formula: str) -> dict[str, int] | None:
    """School oxidation numbers, or None when the rules do not decide."""
    species = parse_species(formula, coefficient_already_removed=True)
    if species is None or species.electron:
        return None
    composition = species.composition
    charge = species.charge
    if len(composition) == 1:
        element, count = next(iter(composition.items()))
        if count == 0 or charge % count != 0:
            return None
        return {element: charge // count}

    assigned: dict[str, int] = {}
    if "F" in composition:
        assigned["F"] = -1
    for element in composition:
        group = BY_SYMBOL[element].group
        if element != "H" and group == 1:
            assigned[element] = 1
        elif group == 2:
            assigned[element] = 2
    if "H" in composition:
        others = [element for element in composition if element != "H"]
        assigned["H"] = -1 if others and all(element not in _NONMETALS for element in others) else 1

    def unassigned() -> list[str]:
        return [element for element in composition if element not in assigned]

    if "O" in unassigned() and len(unassigned()) > 1:
        assigned["O"] = -2
    if "O" not in composition and "F" not in composition:
        for element in unassigned():
            if element in _HALOGENS and len(unassigned()) > 1:
                assigned[element] = -1
    remaining = unassigned()
    if len(remaining) > 1:
        return _polyatomic_oxidation(composition, charge)
    if len(remaining) == 1:
        element = remaining[0]
        known = sum(assigned[item] * composition[item] for item in assigned)
        rest = charge - known
        if composition[element] == 0 or rest % composition[element] != 0:
            return None
        assigned[element] = rest // composition[element]
    known = sum(assigned[element] * composition[element] for element in composition)
    if set(assigned) != set(composition) or known != charge:
        return None
    return assigned


def _polyatomic_oxidation(composition: dict[str, int], charge: int) -> dict[str, int] | None:
    """Assign a known ion, then the one element left outside it."""
    for atoms, poly_charge in _POLYATOMIC:
        if any(composition.get(element, 0) != count for element, count in atoms.items()):
            continue
        left = _consume(composition, atoms)
        if left is None or len(left) != 1:
            continue
        element, count = next(iter(left.items()))
        rest = charge - poly_charge
        if count == 0 or rest % count != 0:
            continue
        body = "".join(
            symbol if atom_count == 1 else f"{symbol}{atom_count}"
            for symbol, atom_count in atoms.items()
        )
        sign = "+" if poly_charge > 0 else "-"
        magnitude = abs(poly_charge)
        ion = f"{body}{sign}" if magnitude == 1 else f"{body}^{magnitude}{sign}"
        inner = oxidation_states(ion)
        if inner is None:
            continue
        return {element: rest // count, **inner}
    return None


def _formal_charge(element: str, lone_electrons: int, bonding_electrons: int) -> int:
    valence = valence_electrons(element)
    if valence is None:
        return 0
    return valence - lone_electrons - bonding_electrons // 2


def _central_atom(species: ChemicalSpecies) -> str | None:
    candidates = [
        element
        for element, count in species.composition.items()
        if element != "H" and count == 1 and valence_electrons(element) is not None
    ]
    if len(candidates) == 1:
        return candidates[0]
    non_hydrogen = [element for element in species.composition if element != "H"]
    if len(non_hydrogen) == 1 and valence_electrons(non_hydrogen[0]) is not None:
        return non_hydrogen[0]
    return None


def lewis_structure(formula: str) -> LewisStructure | None:
    """Build one central-atom structure, or None when the recipe does not apply."""
    species = parse_species(formula, coefficient_already_removed=True)
    if species is None or species.electron:
        return None
    central = _central_atom(species)
    if central is None:
        return None
    terminals: list[str] = []
    for element, count in species.composition.items():
        copies = count - (1 if element == central else 0)
        if copies < 0 or valence_electrons(element) is None:
            return None
        terminals.extend([element] * copies)
    if not terminals:
        return None
    electrons = sum(
        (valence_electrons(element) or 0) * count for element, count in species.composition.items()
    )
    electrons -= species.charge
    if electrons < 0 or electrons % 2:
        return None
    bond_orders = [1] * len(terminals)
    used = 2 * len(terminals)
    if used > electrons:
        return None
    remaining = electrons - used
    lone_terminals = [0] * len(terminals)
    for index, element in enumerate(terminals):
        target = 2 if element == "H" else 8
        need = target - 2 * bond_orders[index]
        if need < 0 or need > remaining:
            return None
        lone_terminals[index] = need
        remaining -= need
    central_lone = remaining
    period = BY_SYMBOL[central].period

    def central_electrons() -> int:
        return central_lone + sum(2 * order for order in bond_orders)

    def charge_total() -> int:
        total = abs(_formal_charge(central, central_lone, sum(2 * order for order in bond_orders)))
        for index, element in enumerate(terminals):
            total += abs(_formal_charge(element, lone_terminals[index], 2 * bond_orders[index]))
        return total

    def best_donor() -> int | None:
        candidates = [
            index
            for index, element in enumerate(terminals)
            if element != "H" and lone_terminals[index] >= 2
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda index: (lone_terminals[index], -bond_orders[index]))

    if central not in {"B", "Be"}:
        guard = 0
        while central_electrons() < 8 and guard < 8:
            guard += 1
            donor = best_donor()
            if donor is None:
                return None
            lone_terminals[donor] -= 2
            bond_orders[donor] += 1
    if period >= 3 and central not in {"B", "Be"}:
        guard = 0
        while guard < 8:
            guard += 1
            donor = best_donor()
            if donor is None or central_electrons() >= 12:
                break
            before = charge_total()
            lone_terminals[donor] -= 2
            bond_orders[donor] += 1
            if charge_total() >= before:
                lone_terminals[donor] += 2
                bond_orders[donor] -= 1
                break
    lone_pairs = central_lone // 2
    steric = len(terminals) + lone_pairs
    geometry = _GEOMETRIES.get((steric, lone_pairs))
    hybrid = _HYBRID.get(steric)
    if geometry is None or hybrid is None or central_lone % 2:
        return None
    identical = len(set(terminals)) == 1
    symmetric = identical and lone_pairs == 0
    if geometry[0] in {"linear", "square planar"} and identical:
        symmetric = True
    polar = not symmetric
    formal = _formal_charge(central, central_lone, sum(2 * order for order in bond_orders))
    return LewisStructure(
        formula=species.label,
        central=central,
        bond_orders=tuple(bond_orders),
        central_lone_pairs=lone_pairs,
        terminal_elements=tuple(terminals),
        geometry=geometry[0],
        bond_angle=geometry[1],
        polar=polar,
        hybridization=hybrid,
        central_formal_charge=formal,
        electrons=electrons,
    )
