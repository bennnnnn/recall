"""Chemical equation parsing and balancing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.chemistry.smiles import _ensure_rdkit


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


def _parse_formula_atoms(formula: str) -> dict[str, int]:
    """Parse a chemical formula into element → count.

    e.g. "H2O" → {"H": 2, "O": 1}, "C6H12O6" → {"C": 6, "H": 12, "O": 6}
    Handles parentheses: "Ca(OH)2" → {"Ca": 1, "O": 2, "H": 2}
    """
    atoms: dict[str, int] = {}

    def _parse(s: str, multiplier: int = 1) -> None:
        i = 0
        while i < len(s):
            if s[i] == "(" or s[i] == "[":
                # Find matching close paren.
                depth = 1
                j = i + 1
                while j < len(s) and depth > 0:
                    if s[j] in "([":
                        depth += 1
                    elif s[j] in ")]":
                        depth -= 1
                    if depth == 0:
                        break
                    j += 1
                inner = s[i + 1 : j]
                # Check for multiplier after close paren.
                k = j + 1
                num_str = ""
                while k < len(s) and s[k].isdigit():
                    num_str += s[k]
                    k += 1
                inner_mult = int(num_str) if num_str else 1
                _parse(inner, multiplier * inner_mult)
                i = k
            elif s[i].isupper():
                # Element symbol.
                elem = s[i]
                j = i + 1
                while j < len(s) and s[j].islower():
                    elem += s[j]
                    j += 1
                # Check for count.
                num_str = ""
                while j < len(s) and s[j].isdigit():
                    num_str += s[j]
                    j += 1
                count = int(num_str) if num_str else 1
                atoms[elem] = atoms.get(elem, 0) + count * multiplier
                i = j
            else:
                i += 1

    _parse(formula)
    return atoms


def balance_equation(equation: str) -> BalancedEquation:
    """Balance a chemical equation using SymPy linear algebra.

    e.g. "H2 + O2 -> H2O" → reactants={"H2": 2, "O2": 1}, products={"H2O": 2}
    """
    _ensure_rdkit()  # not needed, but keeps the lazy-load pattern
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
        all_elements.update(_parse_formula_atoms(formula).keys())
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

    # The nullspace vector gives the coefficients.
    vec = nullspace[0]
    # Convert to integers.
    denominators = [v.q for v in vec]
    common = lcm(denominators) if denominators else 1
    coeffs = [int(v * common) for v in vec]

    # Ensure all positive.
    if any(c < 0 for c in coeffs):
        coeffs = [-c for c in coeffs]

    reactant_coeffs = {species[i]: coeffs[i] for i in range(n_reactants)}
    product_coeffs = {species[n_reactants + i]: coeffs[n_reactants + i] for i in range(n_products)}

    return BalancedEquation(
        reactants=reactant_coeffs,
        products=product_coeffs,
        balanced=True,
    )
