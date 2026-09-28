"""Shared text helpers for the extended chemistry extractors."""

from __future__ import annotations

import re

from app.modules.chemistry.equations import balance_equation
from app.modules.chemistry.request import CHEMICAL_FORMULA, EQUATION_RE
from app.modules.chemistry.species import counts_in_mass_action

_N = r"-?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?"


def _search(pattern: str, text: str, flags: int = re.IGNORECASE) -> float | None:
    match = re.search(pattern, text, flags)
    return float(match.group(1)) if match else None


def _floats(**values: float | None) -> dict[str, float] | None:
    """Return the mapping only when every value was found."""
    cleaned = {key: value for key, value in values.items() if value is not None}
    if len(cleaned) != len(values):
        return None
    return cleaned


def _equation(text: str) -> str | None:
    match = EQUATION_RE.search(text)
    return match.group(1).strip() if match else None


def _target(text: str, equation: str) -> str | None:
    balanced = balance_equation(equation)
    if not balanced.balanced:
        return None
    outside = EQUATION_RE.sub(" ", text)
    mentioned = [
        product
        for product in balanced.products
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(product)}(?![A-Za-z0-9])", outside)
    ]
    if len(mentioned) == 1:
        return mentioned[0]
    if len(balanced.products) == 1:
        return next(iter(balanced.products))
    return None


def _find_unit(text: str) -> str:
    if re.search(r"\b(?:grams?|mass)\b", text, re.IGNORECASE):
        return "g"
    if re.search(r"\b(?:molecules|particles|atoms)\b", text, re.IGNORECASE):
        return "particles"
    if re.search(r"\b(?:liters?|litres?)\b", text, re.IGNORECASE):
        return "L"
    return "mol"


def _percents(text: str) -> dict[str, float]:
    return {
        match.group(2): float(match.group(1))
        for match in re.finditer(rf"({_N})%\s*([A-Z][a-z]?)", text)
    }


def _gram_amounts(text: str) -> dict[str, float]:
    return {
        match.group(2): float(match.group(1))
        for match in re.finditer(
            rf"({_N})\s*g(?:rams?)?(?:\s+of)?\s+({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
            text,
            re.IGNORECASE,
        )
    }


def _molar_formula(text: str) -> tuple[float, str] | None:
    match = re.search(rf"({_N})\s*M\s+({CHEMICAL_FORMULA})(?![A-Za-z0-9])", text)
    if match is None:
        return None
    return float(match.group(1)), match.group(2)


def _gas_state(text: str, names: tuple[str, ...]) -> dict[str, float]:
    found: dict[str, float] = {}
    for name in names:
        value = _search(rf"\b{name}\s*=\s*({_N})", text)
        if value is not None:
            found[name] = value
    return found


def _pressure_species(text: str, equation: str) -> dict[str, float]:
    raw = {
        match.group(1): float(match.group(2))
        for match in re.finditer(rf"P\(({CHEMICAL_FORMULA})\)\s*=\s*({_N})", text)
    }
    balanced = balance_equation(equation)
    if not balanced.balanced:
        return raw
    mapped: dict[str, float] = {}
    for species in (*balanced.reactants, *balanced.products):
        if not counts_in_mass_action(species):
            continue
        if species in raw:
            mapped[species] = raw[species]
            continue
        bare = species[: species.rfind("(")] if "(" in species else species
        if bare in raw:
            mapped[species] = raw[bare]
    return mapped
