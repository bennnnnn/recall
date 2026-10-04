"""Electrochemistry: ΔG from E°, the Nernst equation, electrolysis, and galvanic cells."""

from __future__ import annotations

import re

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.extractors.parsing import (
    _N,
    _search,
    seconds_per,
    temperature_kelvin,
    timed,
)
from app.modules.chemistry.solvers.constants import STANDARD_REDUCTION
from app.modules.chemistry.species_facts import named_elements


def _extract_electrochem(text: str) -> ChemistryIntent | None:
    if re.search(r"\bNernst\b", text, re.IGNORECASE):
        standard = _search(rf"E(?:°|0)\s*=\s*({_N})\s*V", text)
        electrons = _search(rf"\bn\s*=\s*({_N})", text)
        quotient = _search(rf"\bQ\s*=\s*({_N})", text, flags=0)
        temperature = temperature_kelvin(text)
        if temperature is False:
            return None  # a stated temperature without a usable unit is never replaced by 25 °C
        if temperature is None:
            temperature = 298.15
        if standard is not None and electrons is not None and quotient is not None:
            return ChemistryIntent(
                kind="electrochemistry",
                chemistry_op="nernst",
                params={
                    "standard_potential": standard,
                    "electrons": electrons,
                    "quotient": quotient,
                    "temperature": temperature,
                },
            )
    # A degree sign is not a word character, so E° must not demand a trailing boundary.
    if re.search(r"\b(?:ΔG|Gibbs)\b", text, re.IGNORECASE) and re.search(
        r"\b(?:cell|electrochem)\b|\bE°", text, re.IGNORECASE
    ):
        electrons = _search(rf"\bn\s*=\s*({_N})", text)
        potential = _search(rf"E(?:cell)?(?:°|0)?\s*=\s*({_N})\s*V", text)
        if electrons is not None and potential is not None:
            return ChemistryIntent(
                kind="electrochemistry",
                chemistry_op="cell_gibbs",
                params={"electrons": electrons, "potential": potential},
            )
    if re.search(r"\b(?:electrolysis|deposited|Faraday's law)\b", text, re.IGNORECASE):
        molar = _search(rf"(?:molar mass|\bM)\s*=\s*({_N})\s*g/mol", text)
        current = _search(
            rf"(?:current|\bI)\s*(?:=|of)?\s*({_N})\s*(?:(?-i:A)(?![A-Za-z])|amps?\b)", text
        )
        elapsed = timed(text, r"(?:time|\bt)")
        time = None if elapsed is None else elapsed[0] * seconds_per(elapsed[1])
        electrons = _search(rf"\bn\s*=\s*({_N})", text)
        if molar is not None and current is not None and time is not None and electrons is not None:
            return ChemistryIntent(
                kind="electrochemistry",
                chemistry_op="electrolysis_mass",
                params={
                    "molar_mass": molar,
                    "current": current,
                    "time": time,
                    "electrons": electrons,
                },
            )
    return None


# Other metals match as tokens. Potassium is added only after a trailing "298 K"
# is removed, so kelvin is not a second electrode.
_METALS = tuple(symbol for symbol in STANDARD_REDUCTION if symbol != "K")


_KELVIN_UNIT = re.compile(r"\d\s*K\b")


def _extract_cells(text: str) -> ChemistryIntent | None:
    if re.search(r"\bcell potential\b", text, re.IGNORECASE):
        cathode = _search(rf"\bcathode\s*=\s*({_N})", text)
        anode = _search(rf"\banode\s*=\s*({_N})", text)
        if cathode is not None and anode is not None:
            return ChemistryIntent(
                kind="electrochemistry",
                chemistry_op="cell_potential",
                params={"cathode": cathode, "anode": anode},
            )
    if re.search(r"\bgalvanic cell\b", text, re.IGNORECASE):
        without_kelvin = _KELVIN_UNIT.sub(" ", text)
        found = re.findall(r"\b(" + "|".join(_METALS) + r"|K)\b", without_kelvin)
        # "a zinc-copper galvanic cell" names its metals in words.
        found += [symbol for symbol in named_elements(text) if symbol in STANDARD_REDUCTION]
        unique: list[str] = []
        for symbol in found:
            if symbol not in unique:
                unique.append(symbol)
        if len(unique) == 2:
            return ChemistryIntent(
                kind="electrochemistry",
                chemistry_op="galvanic_cell",
                formula=unique[0],
                target=unique[1],
            )
    return None
