"""Chemical equation parsing and balancing."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HYDRATE_DOTS = frozenset({".", "\u00b7"})


@dataclass(frozen=True)
class BalancedEquation:
    """Result of balancing a chemical equation."""

    reactants: dict[str, int]  # species → coefficient
    products: dict[str, int]  # species → coefficient
    balanced: bool
    error: str | None = None


def _parse_equation_side(side: str) -> list[tuple[str, int]]:
    """Parse one side of a chemical equation into (species, count) pairs.

    e.g. "2 H2 + O2" → [("H2", 2), ("O2", 1)]
    """
    terms = []
    for part in side.split("+"):
        part = part.strip()
        if not part:
            continue
        # Match optional coefficient + formula.
        match = re.match(r"^(\d*)\s*([A-Za-z0-9\(\)\[\]\.]+)$", part)
        if match is None:
            continue
        coeff = int(match.group(1)) if match.group(1) else 1
        formula = match.group(2)
        terms.append((formula, coeff))
    return terms


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


def _parse_formula_body(s: str, multiplier: int, atoms: dict[str, int]) -> bool:
    """Walk one Hill-formula fragment. False when a leftover char cannot be parsed."""
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
            # ``(aq)`` / ``(s)`` / ``(l)`` / ``(g)`` — skip, not atoms.
            if not any(ch.isupper() for ch in inner):
                i = k
                continue
            if not _parse_formula_body(inner, multiplier * inner_mult, atoms):
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
    atoms: dict[str, int] = {}
    for fragment in _hydrate_fragments(cleaned):
        count, body = _leading_multiplier(fragment)
        if not body or not _parse_formula_body(body, count, atoms):
            return {}
    return atoms


def _atom_totals(
    terms: list[tuple[str, int]],
    coeffs: list[int],
) -> dict[str, int] | None:
    totals: dict[str, int] = {}
    for (formula, _), coeff in zip(terms, coeffs, strict=True):
        parsed = _parse_formula_atoms(formula)
        if not parsed:
            return None
        for elem, count in parsed.items():
            totals[elem] = totals.get(elem, 0) + coeff * count
    return totals


def balance_equation(equation: str) -> BalancedEquation:
    """Balance a chemical equation using SymPy linear algebra.

    e.g. "H2 + O2 -> H2O" → reactants={"H2": 2, "O2": 1}, products={"H2O": 2}
    """
    from sympy import Matrix, lcm

    if "->" not in equation and "→" not in equation:
        return BalancedEquation({}, {}, False, "no arrow in equation")
    arrow = "->" if "->" in equation else "→"
    left, right = equation.split(arrow, 1)

    reactant_terms = _parse_equation_side(left)
    product_terms = _parse_equation_side(right)

    if not reactant_terms or not product_terms:
        return BalancedEquation({}, {}, False, "empty side")

    # Collect all elements.
    all_elements: set[str] = set()
    for formula, _ in reactant_terms + product_terms:
        parsed = _parse_formula_atoms(formula)
        if not parsed:
            return BalancedEquation({}, {}, False, f"cannot parse {formula}")
        all_elements.update(parsed.keys())
    elements = sorted(all_elements)

    # Build the matrix: each row is an element, each column is a species.
    # Reactants are positive, products are negative.
    species = [f for f, _ in reactant_terms] + [f for f, _ in product_terms]
    n_reactants = len(reactant_terms)
    n_products = len(product_terms)

    rows = []
    for elem in elements:
        row = []
        for formula, _ in reactant_terms:
            atoms = _parse_formula_atoms(formula)
            row.append(atoms.get(elem, 0))
        for formula, _ in product_terms:
            atoms = _parse_formula_atoms(formula)
            row.append(-atoms.get(elem, 0))
        rows.append(row)

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

    left_atoms = _atom_totals(reactant_terms, coeffs[:n_reactants])
    right_atoms = _atom_totals(product_terms, coeffs[n_reactants:])
    if left_atoms is None or right_atoms is None or left_atoms != right_atoms:
        return BalancedEquation({}, {}, False, "atoms do not balance")

    reactant_coeffs = {species[i]: coeffs[i] for i in range(n_reactants)}
    product_coeffs = {species[n_reactants + i]: coeffs[n_reactants + i] for i in range(n_products)}

    return BalancedEquation(
        reactants=reactant_coeffs,
        products=product_coeffs,
        balanced=True,
    )
