"""Empirical, molecular, and multi-step stoichiometry extractors."""

from __future__ import annotations

import re

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.extractors.parsing import (
    _N,
    _equation,
    _find_unit,
    _gram_amounts,
    _percents,
    _search,
    _target,
)
from app.modules.chemistry.quantity import to_atm, to_kelvin, to_liters
from app.modules.chemistry.request import CHEMICAL_FORMULA


def _extract_formulas(text: str) -> ChemistryIntent | None:
    percents = _percents(text)
    if len(percents) < 2:
        return None
    if re.search(r"\bmolecular formula\b", text, re.IGNORECASE):
        molar = _search(rf"(?:molar mass|M)\s*=\s*({_N})", text)
        if molar is None:
            return None
        return ChemistryIntent(
            kind="amounts",
            chemistry_op="molecular_formula",
            params={"molar_mass": molar},
            species=percents,
        )
    if re.search(r"\bempirical formula\b", text, re.IGNORECASE):
        return ChemistryIntent(kind="amounts", chemistry_op="empirical_formula", species=percents)
    return None


def _extract_mass_chain(text: str) -> ChemistryIntent | None:
    equation = _equation(text)
    if equation is None or not re.search(
        r"\b(?:how many|how much|limiting)\b", text, re.IGNORECASE
    ):
        return None
    target = _target(text, equation)
    if target is None:
        return None
    if re.search(r"\blimiting\b", text, re.IGNORECASE):
        amounts = _gram_amounts(text)
        if len(amounts) >= 2:
            return ChemistryIntent(
                kind="stoichiometry",
                chemistry_op="limiting_mass",
                equation=equation,
                target=target,
                species=amounts,
                units={"known": "g"},
            )
        volumes = re.findall(
            rf"({CHEMICAL_FORMULA})\s*=\s*({_N})\s*L\s*\(\s*({_N})\s*M\s*\)",
            text,
            re.IGNORECASE,
        )
        if len(volumes) >= 2:
            return ChemistryIntent(
                kind="stoichiometry",
                chemistry_op="limiting_solution",
                equation=equation,
                target=target,
                species={formula: float(volume) for formula, volume, _molarity in volumes},
                params={formula: float(molarity) for formula, _volume, molarity in volumes},
            )
        return None
    grams = _gram_amounts(text)
    if len(grams) == 1:
        return ChemistryIntent(
            kind="stoichiometry",
            chemistry_op="mass_stoichiometry",
            equation=equation,
            target=target,
            species=grams,
            units={"known": "g", "find": _find_unit(text)},
        )
    solution = re.search(
        rf"({_N})\s*L\s+of\s+({_N})\s*M\s+({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    )
    if solution:
        return ChemistryIntent(
            kind="stoichiometry",
            chemistry_op="solution_stoichiometry",
            equation=equation,
            target=target,
            species={solution.group(3): float(solution.group(1))},
            params={"molarity": float(solution.group(2))},
            units={"known": "solution", "find": _find_unit(text)},
        )
    gas = re.search(
        rf"({_N})\s*(mL|L)\s+of\s+({CHEMICAL_FORMULA})(?![A-Za-z0-9])\s+at\s+"
        rf"({_N})\s*(kPa|Pa|mmHg|torr|atm|bar)\s+and\s+({_N})\s*(°C|C|K)\b",
        text,
    )
    if gas:
        return ChemistryIntent(
            kind="stoichiometry",
            chemistry_op="gas_stoichiometry",
            equation=equation,
            target=target,
            species={gas.group(3): to_liters(float(gas.group(1)), gas.group(2))},
            params={
                "pressure": to_atm(float(gas.group(4)), gas.group(5)),
                "temperature": to_kelvin(
                    float(gas.group(6)), "celsius" if gas.group(7).upper() == "C" else gas.group(7)
                ),
            },
            units={"known": "L", "find": "L"},
        )
    counted = _one_amount(
        text,
        rf"({_N})\s*mol(?:e|es)?(?:\s+of)?\s+({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
    )
    if counted is not None:
        amount, formula = counted
        return _chain(equation, target, formula, amount, "mol", _find_unit(text))
    counted = _one_amount(
        text,
        rf"({_N})\s*(?:molecules|particles|atoms)(?:\s+of)?\s+"
        rf"({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
    )
    if counted is not None:
        amount, formula = counted
        return _chain(equation, target, formula, amount, "particles", _find_unit(text))
    return None


def _one_amount(text: str, pattern: str) -> tuple[float, str] | None:
    matches = re.findall(pattern, text, re.IGNORECASE)
    if len(matches) != 1:
        return None
    amount, formula = matches[0]
    return float(amount), formula


def _chain(
    equation: str,
    target: str,
    formula: str,
    amount: float,
    known: str,
    find: str,
) -> ChemistryIntent:
    return ChemistryIntent(
        kind="stoichiometry",
        chemistry_op="mass_stoichiometry",
        equation=equation,
        target=target,
        species={formula: amount},
        units={"known": known, "find": find},
    )
