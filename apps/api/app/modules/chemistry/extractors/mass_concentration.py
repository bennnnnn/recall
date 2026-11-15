"""A molarity from a solute's mass concentration: "5.85 g/L NaCl", "20 g/L of NaOH".

A mass concentration is the solute's grams in each litre of solution, so c = (g/L) / M. A density
is not one: a solution's 1.07 g/mL is the mass of solution, solute and water together, in each
millilitre. Read by the law binder, "The density of a NaCl solution is 1.07 g/mL" was answered
18.3 mol/L, verified, three times NaCl's solubility (review 2026-11-13). So the value is read
only where the question writes it as the named solute's grams per litre, beside that solute;
a question that names a density, or writes grams per millilitre or per cubic centimetre,
declines, and so does grams of "dissolved salts" asked as one salt's molarity.
"""

from __future__ import annotations

import re

from app.modules.chemistry.request import FORMULA_END, SAMPLE_FORMULA
from app.modules.chemistry.schemas import ChemistryIntent
from app.modules.chemistry.species_facts import is_formula, without_formulas
from app.modules.chemistry.stoichiometry import molar_mass
from app.services.number_text import TEXT_NUMBER

_N = TEXT_NUMBER

# Grams in each litre of solution, never per millilitre or cubic centimetre.
_PER_LITRE = (
    r"(?:g\s*/\s*L|g\s+per\s+(?:L|liter|litre)|grams?\s+per\s+(?:liter|litre))"
    r"(?![A-Za-z])(?:\s+of\s+solution)?"
)
# "5.85 g/L NaCl", "20 g/L of NaOH", "35 g per litre of dissolved NaCl".
_VALUE_OF_SOLUTE = re.compile(
    rf"(?<![\w.])(?P<value>{_N})\s*{_PER_LITRE}\s+(?:of\s+)?(?:dissolved\s+)?"
    rf"(?P<solute>{SAMPLE_FORMULA}){FORMULA_END}"
)
# "NaCl at 5.85 g/L", "an NaOH solution of 20 g/L", "NaCl with a concentration of 5.85 g/L".
_SOLUTE_AT_VALUE = re.compile(
    rf"(?<![A-Za-z0-9])(?P<solute>{SAMPLE_FORMULA}){FORMULA_END}\s+(?:solution\s+)?"
    r"(?:at|of|is|with\s+a\s+(?:mass\s+)?concentration\s+of|(?:mass\s+)?concentration\s+(?:of|is))"
    rf"\s+(?P<value>{_N})\s*{_PER_LITRE}"
)
_MOLARITY_ASK = re.compile(
    r"\bmolarity\b|\bmolar\s+concentration\b|\bconcentration\s+in\s+(?:mol/L|M)(?![A-Za-z])",
    re.IGNORECASE,
)
# A density by name or by unit: a solution's mass per volume, never its solute's.
_DENSITY = re.compile(r"\bdens(?:e|ity|ities)\b|\bg\s*/\s*(?:mL|cm)", re.IGNORECASE)
_NUMBER = re.compile(rf"(?<![\w.]){_N}")


def extract_mass_concentration(text: str) -> ChemistryIntent | None:
    if _MOLARITY_ASK.search(text) is None or _DENSITY.search(text) is not None:
        return None
    found = [*_VALUE_OF_SOLUTE.finditer(text), *_SOLUTE_AT_VALUE.finditer(text)]
    # One stated value, the solute's: a second number is a volume, a density or a second
    # solute this law does not take.
    if len(found) != 1 or len(_NUMBER.findall(without_formulas(text))) != 1:
        return None
    solute = found[0].group("solute")
    if not is_formula(solute):
        return None
    return ChemistryIntent(
        kind="solutions",
        chemistry_op="molarity_from_mass_concentration",
        formula=solute,
        params={
            "mass_concentration": float(found[0].group("value")),
            "molar_mass": molar_mass(solute),
        },
        units={"mass_concentration": "g/L"},
    )
