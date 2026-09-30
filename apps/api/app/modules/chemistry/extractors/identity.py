"""Structure, organic, coordination, colligative, and analytical extractors."""

from __future__ import annotations

import re

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.extractors.parsing import (
    _N,
    _floats,
    _search,
)
from app.modules.chemistry.request import CHEMICAL_FORMULA
from app.modules.chemistry.solvers.constants import STANDARD_REDUCTION

# "K" is left out on purpose: in "298 K" it is kelvin, not potassium.
_METALS = tuple(symbol for symbol in STANDARD_REDUCTION if symbol != "K")


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
        found = re.findall(r"\b(" + "|".join(_METALS) + r")\b", text)
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


def _extract_nuclear_ext(text: str) -> ChemistryIntent | None:
    if re.search(r"\bdecay constant\b", text, re.IGNORECASE) and re.search(
        r"\bhalf[- ]life\b", text, re.IGNORECASE
    ):
        half = _search(rf"half[- ]life\s*=\s*({_N})\s*s", text)
        if half is not None:
            return ChemistryIntent(
                kind="nuclear",
                chemistry_op="decay_constant",
                params={"half_life": half},
                units={"time": "s"},
            )
    if re.search(r"\bexponential decay\b", text, re.IGNORECASE):
        initial = _search(rf"\bN0\s*=\s*({_N})", text, flags=0)
        constant = _search(rf"decay constant\s*=\s*({_N})", text)
        time = _search(rf"\bt\s*=\s*({_N})\s*s", text)
        params = _floats(initial=initial, decay_constant=constant, time=time)
        if params is not None:
            return ChemistryIntent(kind="nuclear", chemistry_op="exponential_decay", params=params)
    if re.search(r"\bnuclear activity\b", text, re.IGNORECASE):
        constant = _search(rf"decay constant\s*=\s*({_N})", text)
        particles = _search(rf"\bN\s*=\s*({_N})", text, flags=0)
        if constant is not None and particles is not None:
            return ChemistryIntent(
                kind="nuclear",
                chemistry_op="nuclear_activity",
                params={"decay_constant": constant, "particles": particles},
            )
    match = re.search(r"nuclear equation\s+(.+)$", text, re.IGNORECASE)
    if match:
        return ChemistryIntent(
            kind="nuclear", chemistry_op="nuclear_equation", equation=match.group(1).strip()
        )
    return None


def _extract_identity(text: str) -> ChemistryIntent | None:
    oxidation = re.search(
        rf"oxidation state(?:s)?(?: of each element)? in ({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    )
    if oxidation:
        return ChemistryIntent(
            kind="structure", chemistry_op="oxidation_state", formula=oxidation.group(1)
        )
    vsepr = re.search(
        rf"\bVSEPR\b(?: shape)? of ({CHEMICAL_FORMULA})(?![A-Za-z0-9])", text, re.IGNORECASE
    )
    if vsepr:
        return ChemistryIntent(kind="structure", chemistry_op="vsepr", formula=vsepr.group(1))
    if re.search(r"\bformal charge\b", text, re.IGNORECASE):
        valence = _search(rf"\bvalence\s*=\s*({_N})", text)
        nonbonding = _search(rf"\bnonbonding\s*=\s*({_N})", text)
        bonding = _search(rf"\bbonding\s*=\s*({_N})", text)
        params = _floats(valence=valence, nonbonding=nonbonding, bonding=bonding)
        if params is not None:
            return ChemistryIntent(kind="structure", chemistry_op="formal_charge", params=params)
    if re.search(r"\bfunctional groups\b", text, re.IGNORECASE):
        smiles = re.search(r"\bSMILES\s+(\S+)", text, re.IGNORECASE)
        if smiles:
            return ChemistryIntent(
                kind="organic", chemistry_op="functional_groups", formula=smiles.group(1)
            )
    if re.search(r"\bstereochemistry\b", text, re.IGNORECASE):
        smiles = re.search(r"\bSMILES\s+(\S+)", text, re.IGNORECASE)
        if smiles:
            return ChemistryIntent(
                kind="organic", chemistry_op="stereochemistry", formula=smiles.group(1)
            )
    if re.search(r"\bisomer\b", text, re.IGNORECASE):
        pair = re.search(r"\bSMILES\s+(\S+)\s+and\s+(\S+)", text, re.IGNORECASE)
        if pair:
            return ChemistryIntent(
                kind="organic",
                chemistry_op="isomers",
                formula=pair.group(1),
                target=pair.group(2).rstrip("?"),
            )
    complex_match = re.search(r"coordination complex\s+(\S+)", text, re.IGNORECASE)
    if complex_match:
        return ChemistryIntent(
            kind="inorganic",
            chemistry_op="coordination_complex",
            formula=complex_match.group(1).rstrip("?.,;"),
        )
    return None


def _extract_colligative(text: str) -> ChemistryIntent | None:
    factor = _search(rf"\bi\s*=\s*({_N})", text)
    molality = _search(rf"\bmolality\s*=\s*({_N})", text)
    if re.search(r"\bboiling point elevation\b", text, re.IGNORECASE):
        constant = _search(rf"\bKb\s*=\s*({_N})", text, flags=0)
        params = _floats(i=factor, kb=constant, molality=molality)
        if params is not None:
            return ChemistryIntent(
                kind="solutions", chemistry_op="boiling_elevation", params=params
            )
    if re.search(r"\bfreezing point depression\b", text, re.IGNORECASE):
        constant = _search(rf"\bKf\s*=\s*({_N})", text, flags=0)
        params = _floats(i=factor, kf=constant, molality=molality)
        if params is not None:
            return ChemistryIntent(
                kind="solutions", chemistry_op="freezing_depression", params=params
            )
    if re.search(r"\bosmotic pressure\b", text, re.IGNORECASE):
        molarity = _search(rf"\bmolarity\s*=\s*({_N})", text)
        temperature = _search(rf"\bT\s*=\s*({_N})\s*K", text, flags=0)
        params = _floats(i=factor, molarity=molarity, temperature=temperature)
        if params is not None:
            return ChemistryIntent(kind="solutions", chemistry_op="osmotic_pressure", params=params)
    if re.search(r"\bRaoult\b", text):
        fraction = _search(rf"mole fraction\s*=\s*({_N})", text)
        pure = _search(rf"pure pressure\s*=\s*({_N})", text)
        if fraction is not None and pure is not None:
            return ChemistryIntent(
                kind="solutions",
                chemistry_op="raoult",
                params={"mole_fraction": fraction, "pure_pressure": pure},
            )
    return None


def _extract_analytical(text: str) -> ChemistryIntent | None:
    if re.search(r"\bcalibration curve\b", text, re.IGNORECASE):
        slope = _search(rf"\bslope\s*=\s*({_N})", text)
        intercept = _search(rf"\bintercept\s*=\s*({_N})", text)
        signal = _search(rf"\bsignal\s*=\s*({_N})", text)
        params = _floats(slope=slope, intercept=intercept, signal=signal)
        if params is not None:
            return ChemistryIntent(kind="analytical", chemistry_op="calibration", params=params)
    if re.search(r"\bGravimetric\b", text):
        mass = _search(rf"precipitate mass\s*=\s*({_N})", text)
        factor = _search(rf"\bfactor\s*=\s*({_N})", text)
        if mass is not None and factor is not None:
            return ChemistryIntent(
                kind="analytical",
                chemistry_op="gravimetric",
                params={"precipitate_mass": mass, "factor": factor},
            )
    if re.search(r"\bStandard addition\b", text):
        params = _floats(
            sample_signal=_search(rf"sample signal\s*=\s*({_N})", text),
            spiked_signal=_search(rf"spiked signal\s*=\s*({_N})", text),
            standard_concentration=_search(rf"standard concentration\s*=\s*({_N})", text),
            standard_volume=_search(rf"standard volume\s*=\s*({_N})", text),
            sample_volume=_search(rf"sample volume\s*=\s*({_N})", text),
        )
        if params is not None:
            return ChemistryIntent(
                kind="analytical", chemistry_op="standard_addition", params=params
            )
    return None
