"""A question about a written equation: balance it, its K or Q, or the moles it relates."""

from __future__ import annotations

import re

from app.models.schemas.chemistry import ChemistryIntent, ChemistryOp
from app.modules.chemistry.equations import balance_equation
from app.modules.chemistry.extractors.parsing import (
    _N,
    _target,
)
from app.modules.chemistry.request import CHEMICAL_FORMULA, EQUATION_RE


def _amounts(text: str) -> dict[str, float]:
    return {
        match.group(2): float(match.group(1))
        for match in re.finditer(
            rf"({_N})\s*mol(?:e|es)?(?:\s+of)?\s+({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
            text,
            re.IGNORECASE,
        )
    }


def _extract_equations(text: str) -> ChemistryIntent | None:
    match = EQUATION_RE.search(text)
    if match is None or re.search(r"\bnuclear\b", text, re.IGNORECASE):
        return None
    equation = match.group(1).strip()
    if re.search(r"\b(?:is|are|check|verify)\b[^?]{0,80}\bbalanced\b", text, re.IGNORECASE):
        return ChemistryIntent(
            kind="equations", chemistry_op="balance", equation=equation, target="check"
        )
    if re.search(r"\b(?:balance|balanced|coefficient)\b", text, re.IGNORECASE):
        return ChemistryIntent(kind="equations", chemistry_op="balance", equation=equation)
    if re.search(r"\b(?:Kc|equilibrium constant|reaction quotient|Qc)\b", text, re.IGNORECASE):
        concentrations = {
            species: float(value)
            for species, value in re.findall(
                rf"\[({CHEMICAL_FORMULA})\]\s*=\s*({_N})\s*(?:M|mol/L)?",
                text,
                re.IGNORECASE,
            )
        }
        balanced = balance_equation(equation)
        from app.modules.chemistry.species import counts_in_mass_action

        normalized: dict[str, float] = {}
        if balanced.balanced:
            for species in (*balanced.reactants, *balanced.products):
                if not counts_in_mass_action(species):
                    continue
                value = concentrations.get(species)
                if value is None and "(" in species:
                    value = concentrations.get(species[: species.rfind("(")])
                if value is None:
                    normalized = {}
                    break
                normalized[species] = value
        if normalized:
            op: ChemistryOp = (
                "reaction_quotient"
                if re.search(r"\b(?:reaction quotient|Qc)\b", text, re.IGNORECASE)
                else "equilibrium_constant"
            )
            return ChemistryIntent(
                kind="equilibrium", chemistry_op=op, equation=equation, species=normalized
            )
    if re.search(
        r"\b(?:how much|how many|moles? of|limiting reagent|stoichiometr)\b", text, re.IGNORECASE
    ):
        amounts = _amounts(text)
        target = _target(text, equation)
        if target and "limiting" in text.lower() and len(amounts) >= 2:
            return ChemistryIntent(
                kind="stoichiometry",
                chemistry_op="limiting_reagent",
                equation=equation,
                target=target,
                species=amounts,
            )
        reactants = balance_equation(equation).reactants
        known = {formula: amount for formula, amount in amounts.items() if formula in reactants}
        if (
            target
            and len(known) == 1
            and not re.search(
                r"\b(?:grams?|molecules|particles|atoms|liters?|litres?)\b",
                text,
                re.IGNORECASE,
            )
        ):
            return ChemistryIntent(
                kind="stoichiometry",
                chemistry_op="stoichiometry",
                equation=equation,
                target=target,
                species=known,
            )
    return None
