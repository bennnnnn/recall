"""Equilibria: Ksp and precipitation, the common-ion effect, Kp, Kc ↔ Kp, and ICE tables."""

from __future__ import annotations

import re

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.extractors.parsing import (
    _N,
    _equation,
    _pressure_species,
    _search,
)
from app.modules.chemistry.request import CHEMICAL_FORMULA
from app.modules.chemistry.species_facts import dissolution_equation, named_species

_ICE_ASK = re.compile(r"\bICE equilibrium\b|\bequilibrium\s+concentrations?\b", re.IGNORECASE)


_CONCENTRATION_CHAIN = re.compile(rf"((?:\[{CHEMICAL_FORMULA}\]\s*=\s*)+)({_N})")


def _extract_equilibrium(text: str) -> ChemistryIntent | None:
    qsp = _search(rf"\bQsp\s*=\s*({_N})", text, flags=0)
    ksp = _search(rf"\bKsp\s*=\s*({_N})", text, flags=0)
    if qsp is not None and ksp is not None:
        return ChemistryIntent(
            kind="equilibrium", chemistry_op="precipitation", params={"qsp": qsp, "ksp": ksp}
        )
    equation = _equation(text)
    if re.search(r"\bcommon-ion\b", text, re.IGNORECASE) and equation and ksp is not None:
        concentrations = {
            match.group(1): float(match.group(2))
            for match in re.finditer(rf"\[({CHEMICAL_FORMULA})\]\s*=\s*({_N})", text)
        }
        return ChemistryIntent(
            kind="equilibrium",
            chemistry_op="common_ion",
            equation=equation,
            params={"ksp": ksp},
            species=concentrations,
        )
    if ksp is not None and equation and re.search(r"\bsolubility\b", text, re.IGNORECASE):
        return ChemistryIntent(
            kind="equilibrium", chemistry_op="ksp", equation=equation, params={"ksp": ksp}
        )
    solubility = _search(
        rf"(?:molar\s+)?solubility\s*(?:=|of|is)?\s*({_N})\s*(?:(?-i:M)(?![A-Za-z])|mol/L)", text
    )
    if solubility is not None and equation and re.search(r"\bKsp\b", text, flags=0):
        return ChemistryIntent(
            kind="equilibrium",
            chemistry_op="ksp",
            equation=equation,
            params={"solubility": solubility},
        )
    salt = None if equation else _salt_solubility(text)
    if salt is not None:
        return salt
    if (
        re.search(r"\bKp\b", text, re.IGNORECASE)
        and equation
        and re.search(r"\bFind Kp\b", text, re.IGNORECASE)
    ):
        # "Kc = 0.5 at 500 K. Find Kp." converts the stated Kc; it has no partial pressures.
        kc = _search(rf"\bKc\s*=\s*({_N})", text, flags=0)
        temperature = _search(rf"({_N})\s*K\b", text, flags=0)
        if kc is not None and temperature is not None:
            return ChemistryIntent(
                kind="equilibrium",
                chemistry_op="kc_kp",
                equation=equation,
                params={"kc": kc, "temperature": temperature},
            )
        return ChemistryIntent(
            kind="equilibrium",
            chemistry_op="kp",
            equation=equation,
            species=_pressure_species(text, equation),
        )
    if re.search(r"\b(?:Kc to Kp|Kp to Kc)\b", text, re.IGNORECASE) and equation:
        temperature = _search(rf"\bT\s*=\s*({_N})\s*K", text, flags=0)
        kc = _search(rf"\bKc\s*=\s*({_N})", text, flags=0)
        kp = _search(rf"\bKp\s*=\s*({_N})", text, flags=0)
        params = {}
        if temperature is not None:
            params["temperature"] = temperature
        if kc is not None:
            params["kc"] = kc
        if kp is not None:
            params["kp"] = kp
        return ChemistryIntent(
            kind="equilibrium", chemistry_op="kc_kp", equation=equation, params=params
        )
    if _ICE_ASK.search(text) and equation:
        constant = _search(rf"\bK(?:c|eq)?\s*=\s*({_N})", text, flags=0)
        # "[H2] = [I2] = 1.0 M" gives both the one value.
        concentrations = {
            name: float(match.group(2))
            for match in _CONCENTRATION_CHAIN.finditer(text)
            for name in re.findall(rf"\[({CHEMICAL_FORMULA})\]", match.group(1))
        }
        if constant is not None and concentrations:
            return ChemistryIntent(
                kind="equilibrium",
                chemistry_op="ice_equilibrium",
                equation=equation,
                params={"k": constant},
                species=concentrations,
            )
    return None


_KSP_OF = re.compile(
    rf"\bKsp\s*(?:\(\s*({CHEMICAL_FORMULA})\s*\)|(?:value\s+)?(?:of|for)\s+({CHEMICAL_FORMULA}))?"
    rf"\s*(?:=|is|:)\s*({_N})"
)


_SOLUBILITY_OF = re.compile(
    rf"\bsolubility\s+(?:of\s+({CHEMICAL_FORMULA})\s+)?(?:=|is)\s*({_N})\s*"
    r"(?:(?-i:M)(?![A-Za-z])|mol\s*/\s*L)",
    re.IGNORECASE,
)


def _salt_solubility(text: str) -> ChemistryIntent | None:
    """A salt named by its formula instead of its dissolution equation.

    "The Ksp of AgCl is 1.8e-10. Find its molar solubility." The equation is the salt's ions
    (``dissolution_equation``); the other direction gives the solubility and asks for Ksp.
    """
    ksp = _KSP_OF.search(text)
    solubility = _SOLUBILITY_OF.search(text)
    if ksp is not None and solubility is None and re.search(r"\bsolubility\b", text, re.I):
        stated, params = ksp.group(1) or ksp.group(2), {"ksp": float(ksp.group(3))}
    elif solubility is not None and ksp is None and re.search(r"(?<![A-Za-z])Ksp\b", text):
        stated, params = solubility.group(1), {"solubility": float(solubility.group(2))}
    else:
        return None
    salts = [stated] if stated else [f for f in named_species(text) if dissolution_equation(f)]
    if len(salts) != 1 or (equation := dissolution_equation(salts[0])) is None:
        return None
    return ChemistryIntent(
        kind="equilibrium", chemistry_op="ksp", equation=equation, formula=salts[0], params=params
    )
