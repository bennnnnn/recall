"""Chemical equation parsing and balancing."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from app.modules.chemistry.species import ReactionTerm

_HYDRATE_DOTS = frozenset({".", "\u00b7"})
_PHASES = frozenset({"aq", "s", "l", "g"})
_MAX_NESTING = 12


@dataclass(frozen=True)
class BalancedEquation:
    """Result of balancing a chemical equation."""

    reactants: dict[str, int]  # species → coefficient
    products: dict[str, int]  # species → coefficient
    balanced: bool
    error: str | None = None
    given_balanced: bool = False  # the coefficients the user wrote are already correct


def _hydrate_fragments(formula: str) -> list[str]:
    """Split ``CuSO4.5H2O`` / ``CuSO4·5H2O`` into fragments. Linear — no regex."""
    fragments: list[str] = []
    current: list[str] = []
    for ch in formula:
        if ch in _HYDRATE_DOTS:
            if current:
                fragments.append("".join(current))
                current = []
            continue
        current.append(ch)
    if current:
        fragments.append("".join(current))
    return fragments


def _leading_multiplier(fragment: str) -> tuple[int, str]:
    """``5H2O`` → (5, ``H2O``); ``H2O`` → (1, ``H2O``)."""
    i = 0
    n = len(fragment)
    while i < n and fragment[i].isdigit():
        i += 1
    if i == 0 or i == n:
        return 1, fragment
    return int(fragment[:i]), fragment[i:]


def _parse_formula_body(s: str, multiplier: int, atoms: dict[str, int], nesting: int = 0) -> bool:
    """Walk one Hill-formula fragment. False when a leftover char cannot be parsed."""
    if nesting > _MAX_NESTING:
        return False
    i = 0
    n = len(s)
    while i < n:
        if s[i].isspace():
            i += 1
            continue
        if s[i] in "([":
            opener = s[i]
            closer = ")" if opener == "(" else "]"
            depth = 1
            j = i + 1
            while j < n and depth > 0:
                if s[j] == opener:
                    depth += 1
                elif s[j] == closer:
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if depth != 0:
                return False
            inner = s[i + 1 : j]
            k = j + 1
            num_str = ""
            while k < n and s[k].isdigit():
                num_str += s[k]
                k += 1
            inner_mult = int(num_str) if num_str else 1
            if num_str and inner_mult < 1:
                return False
            # ``(aq)`` / ``(s)`` / ``(l)`` / ``(g)`` — skip, not atoms. ``H(2)`` is not a formula.
            if not any(ch.isupper() for ch in inner):
                if inner not in _PHASES:
                    return False
                i = k
                continue
            if not _parse_formula_body(inner, multiplier * inner_mult, atoms, nesting + 1):
                return False
            i = k
            continue
        if s[i].isupper():
            elem = s[i]
            j = i + 1
            while j < n and s[j].islower():
                elem += s[j]
                j += 1
            num_str = ""
            while j < n and s[j].isdigit():
                num_str += s[j]
                j += 1
            count = int(num_str) if num_str else 1
            if count < 1:
                return False
            atoms[elem] = atoms.get(elem, 0) + count * multiplier
            i = j
            continue
        return False
    return True


def _parse_formula_atoms(formula: str) -> dict[str, int]:
    """Parse a chemical formula into element → count.

    e.g. ``H2O`` → {H:2, O:1}, ``Ca(OH)2`` → {Ca:1, O:2, H:2},
    ``CuSO4.5H2O`` → {Cu:1, S:1, O:9, H:10}.
    Returns {} when the string is not a complete formula.
    """
    cleaned = formula.strip()
    if not cleaned:
        return {}
    if cleaned[0] in _HYDRATE_DOTS or cleaned[-1] in _HYDRATE_DOTS:
        return {}
    if any(a in _HYDRATE_DOTS and b in _HYDRATE_DOTS for a, b in pairwise(cleaned)):
        return {}
    atoms: dict[str, int] = {}
    for fragment in _hydrate_fragments(cleaned):
        count, body = _leading_multiplier(fragment)
        if count < 1:
            return {}
        if not body or not _parse_formula_body(body, count, atoms):
            return {}
    return atoms


def _counted(
    terms: Sequence[ReactionTerm],
    coeffs: list[int],
) -> tuple[dict[str, int], int] | None:
    """Atom and charge totals. Electrons contribute charge and no atoms."""
    totals: dict[str, int] = {}
    charge = 0
    for term, coeff in zip(terms, coeffs, strict=True):
        if not isinstance(term, ReactionTerm) or coeff < 1:
            return None
        if not term.species.electron and not term.species.composition:
            return None
        for elem, count in term.species.composition.items():
            totals[elem] = totals.get(elem, 0) + coeff * count
        charge += coeff * term.species.charge
    return totals, charge


def balance_equation(equation: str) -> BalancedEquation:
    """Balance a chemical equation using SymPy linear algebra.

    Atom rows are always required. A charge row is added only when some species
    is an ion or an electron, so uncharged equations keep the same nullspace.
    e.g. "H2 + O2 -> H2O" → reactants={"H2": 2, "O2": 1}, products={"H2O": 2}
    """
    from sympy import Matrix, lcm

    from app.modules.chemistry.species import parse_reaction, split_equation

    if split_equation(equation) is None:
        return BalancedEquation({}, {}, False, "no arrow in equation")
    reaction = parse_reaction(equation)
    if reaction is None:
        return BalancedEquation({}, {}, False, "cannot parse equation")

    reactant_terms = list(reaction.reactants)
    product_terms = list(reaction.products)
    labels = [term.species.label for term in reactant_terms + product_terms]
    if len(labels) != len(set(labels)):
        return BalancedEquation({}, {}, False, "duplicate species")

    all_elements: set[str] = set()
    for term in reactant_terms + product_terms:
        all_elements.update(term.species.composition)
    elements = sorted(all_elements)
    n_reactants = len(reactant_terms)
    n_products = len(product_terms)

    rows: list[list[int]] = []
    for elem in elements:
        row = [term.species.composition.get(elem, 0) for term in reactant_terms]
        row.extend(-term.species.composition.get(elem, 0) for term in product_terms)
        rows.append(row)
    charges = [term.species.charge for term in reactant_terms + product_terms]
    if any(charge != 0 for charge in charges):
        charge_row = charges[:n_reactants] + [-charge for charge in charges[n_reactants:]]
        rows.append(charge_row)
    if not rows:
        return BalancedEquation({}, {}, False, "no constraints")

    matrix = Matrix(rows)
    nullspace = matrix.nullspace()
    if not nullspace:
        return BalancedEquation({}, {}, False, "no solution")
    if len(nullspace) != 1:
        return BalancedEquation({}, {}, False, "underdetermined")

    vec = nullspace[0]
    denominators = [v.q for v in vec]
    common = lcm(denominators) if denominators else 1
    coeffs = [int(v * common) for v in vec]
    if any(c < 0 for c in coeffs):
        coeffs = [-c for c in coeffs]
    if any(c < 1 for c in coeffs):
        return BalancedEquation({}, {}, False, "non-positive coefficient")

    left = _counted(reactant_terms, coeffs[:n_reactants])
    right = _counted(product_terms, coeffs[n_reactants:])
    if left is None or right is None or left[0] != right[0]:
        return BalancedEquation({}, {}, False, "atoms do not balance")
    if left[1] != right[1]:
        return BalancedEquation({}, {}, False, "charge does not balance")

    reactant_coeffs = {labels[i]: coeffs[i] for i in range(n_reactants)}
    product_coeffs = {labels[n_reactants + i]: coeffs[n_reactants + i] for i in range(n_products)}
    written = [term.coefficient for term in reactant_terms + product_terms]
    return BalancedEquation(
        reactants=reactant_coeffs,
        products=product_coeffs,
        balanced=True,
        given_balanced=written == coeffs,
    )
