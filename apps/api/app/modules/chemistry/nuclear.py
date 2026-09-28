"""Nuclear equations from mass number and atomic number.

Mass defect and binding energy stay unverified. A missing product is filled
only when the missing (A, Z) is a known particle or a single nuclide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.chemistry.elements import BY_NUMBER, BY_SYMBOL

_NUCLIDE_RE = re.compile(r"^(\d+)([A-Z][a-z]?)$")
_PARTICLES = {
    (4, 2): "4He",
    (1, 0): "1n",
    (1, 1): "1H",
    (0, -1): "e-",
    (0, 1): "e+",
}


@dataclass(frozen=True)
class Nuclide:
    mass_number: int
    symbol: str
    protons: int
    coefficient: int = 1

    @property
    def label(self) -> str:
        return f"{self.mass_number}{self.symbol}"


@dataclass(frozen=True)
class NuclearEquation:
    reactants: tuple[Nuclide, ...]
    products: tuple[Nuclide, ...]
    balanced: bool
    error: str | None = None


def _parse_nuclide(token: str) -> Nuclide | None:
    text = token.strip()
    coefficient = 1
    match = re.match(r"^(\d+)\s+(.+)$", text)
    if match and not _NUCLIDE_RE.match(text):
        coefficient = int(match.group(1))
        text = match.group(2)
    if text in {"e-", "β-", "beta"}:
        return Nuclide(0, "e-", -1, coefficient)
    if text in {"e+", "β+", "positron"}:
        return Nuclide(0, "e+", 1, coefficient)
    if text in {"n", "1n", "neutron"}:
        return Nuclide(1, "n", 0, coefficient)
    parsed = _NUCLIDE_RE.match(text)
    if parsed is None:
        hyphen = re.match(r"^([A-Z][a-z]?)-(\d+)$", text)
        if hyphen is None:
            return None
        symbol, mass = hyphen.group(1), int(hyphen.group(2))
    else:
        mass, symbol = int(parsed.group(1)), parsed.group(2)
    element = BY_SYMBOL.get(symbol)
    if element is None:
        return None
    return Nuclide(mass, symbol, element.number, coefficient)


def _split_side(side: str) -> list[Nuclide] | None:
    pieces = [part.strip() for part in side.split("+")]
    nuclides = []
    for piece in pieces:
        if not piece or piece == "?":
            return None
        nuclide = _parse_nuclide(piece)
        if nuclide is None:
            return None
        nuclides.append(nuclide)
    return nuclides


def _totals(nuclides: list[Nuclide]) -> tuple[int, int]:
    mass = sum(item.coefficient * item.mass_number for item in nuclides)
    protons = sum(item.coefficient * item.protons for item in nuclides)
    return mass, protons


def _format(nuclides: tuple[Nuclide, ...]) -> str:
    parts = []
    for nuclide in nuclides:
        label = nuclide.label if nuclide.symbol not in {"e-", "e+", "n"} else nuclide.symbol
        if nuclide.symbol == "n":
            label = "1n"
        parts.append(f"{nuclide.coefficient} {label}" if nuclide.coefficient != 1 else label)
    return " + ".join(parts)


def balance_nuclear(equation: str) -> NuclearEquation:
    """Balance nucleons, or complete one ``?`` product."""
    arrow = "->" if "->" in equation else "→" if "→" in equation else ""
    if not arrow:
        return NuclearEquation((), (), False, "no arrow in equation")
    left, right = equation.split(arrow, 1)
    reactants = _split_side(left)
    if reactants is None:
        return NuclearEquation((), (), False, "cannot parse nuclear equation")
    raw_products = [part.strip() for part in right.split("+")]
    raw_products = [part for part in raw_products if part]
    if raw_products.count("?") > 1:
        return NuclearEquation((), (), False, "more than one missing nuclide")
    products: list[Nuclide] = []
    missing = False
    for part in raw_products:
        if part == "?":
            missing = True
            continue
        nuclide = _parse_nuclide(part)
        if nuclide is None:
            return NuclearEquation((), (), False, "cannot parse nuclear equation")
        products.append(nuclide)
    if missing:
        delta_mass, delta_z = _totals(reactants)
        have_mass, have_z = _totals(products)
        delta = (delta_mass - have_mass, delta_z - have_z)
        label = _PARTICLES.get(delta)
        if label is None:
            element = BY_NUMBER.get(delta[1])
            if element is None or delta[0] < 1:
                return NuclearEquation((), (), False, "missing nuclide is not unique")
            label = f"{delta[0]}{element.symbol}"
        extra = _parse_nuclide(label)
        if extra is None:
            return NuclearEquation((), (), False, "missing nuclide is not unique")
        products.append(extra)
    if _totals(reactants) != _totals(products):
        return NuclearEquation(tuple(reactants), tuple(products), False, "nucleons do not balance")
    return NuclearEquation(tuple(reactants), tuple(products), True)


def format_nuclear(equation: NuclearEquation) -> str:
    return f"{_format(equation.reactants)} → {_format(equation.products)}"


def decay_product(mass_number: int, symbol: str, mode: str) -> str | None:
    """Alpha, beta, positron, or electron-capture daughter equation."""
    element = BY_SYMBOL.get(symbol)
    if element is None:
        return None
    parent = f"{mass_number}{symbol}"
    if mode == "alpha":
        daughter = BY_NUMBER.get(element.number - 2)
        if daughter is None or mass_number <= 4:
            return None
        equation = f"{parent} -> {mass_number - 4}{daughter.symbol} + ?"
    elif mode == "beta":
        daughter = BY_NUMBER.get(element.number + 1)
        if daughter is None:
            return None
        equation = f"{parent} -> {mass_number}{daughter.symbol} + ?"
    elif mode == "positron":
        daughter = BY_NUMBER.get(element.number - 1)
        if daughter is None:
            return None
        equation = f"{parent} -> {mass_number}{daughter.symbol} + ?"
    elif mode == "electron capture":
        daughter = BY_NUMBER.get(element.number - 1)
        if daughter is None:
            return None
        return f"{parent} → {mass_number}{daughter.symbol}"
    else:
        return None
    balanced = balance_nuclear(equation)
    if not balanced.balanced:
        return None
    return format_nuclear(balanced)
