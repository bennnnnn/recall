"""Thermochemistry: Gibbs energy, calorimetry, Hess's law, formation and bond enthalpies."""

from __future__ import annotations

import re

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.extractors.parsing import (
    _N,
    _equation,
    _labeled,
    _search,
)
from app.modules.chemistry.request import CHEMICAL_FORMULA


def _extract_gibbs(text: str) -> ChemistryIntent | None:
    if re.search(r"\b(?:Gibbs|\u0394G|delta\s*G)\b", text, re.IGNORECASE):
        delta_h = _search(rf"(?:ΔH|delta\s*H)\s*=\s*({_N})\s*kJ", text)
        delta_s = _search(rf"(?:ΔS|delta\s*S)\s*=\s*({_N})\s*(k?J)", text)
        entropy_unit = re.search(r"(?:ΔS|delta\s*S)\s*=\s*" + _N + r"\s*(k?J)", text, re.IGNORECASE)
        temperature = _search(rf"(?:\bT|temperature)\s*(?:=|of)?\s*({_N})\s*K\b", text)
        if delta_h is not None and delta_s is not None and temperature is not None:
            if entropy_unit and entropy_unit.group(1).lower() == "j":
                delta_s /= 1000
            return ChemistryIntent(
                kind="thermochemistry",
                chemistry_op="gibbs",
                params={"delta_h": delta_h, "delta_s": delta_s, "temperature": temperature},
            )
    return None


def _extract_clausius(text: str) -> ChemistryIntent | None:
    if not re.search(r"\bClausius\b", text, re.IGNORECASE):
        return None
    found = _labeled(
        text,
        (
            ("p1", rf"\bP1\s*=\s*({_N})"),
            ("t1", rf"\bT1\s*=\s*({_N})"),
            ("p2", rf"\bP2\s*=\s*({_N})"),
            ("t2", rf"\bT2\s*=\s*({_N})"),
            ("delta_h", rf"\bdH\s*=\s*({_N})"),
        ),
    )
    points = {"p1", "t1", "p2", "t2"}
    pressure = {"p1", "t1", "t2", "delta_h"} <= set(found) or {"p2", "t1", "t2", "delta_h"} <= set(
        found
    )
    complete = set(found) == points or (pressure and "delta_h" in found and len(found) == 4)
    if complete:
        return ChemistryIntent(
            kind="thermochemistry", chemistry_op="clausius_clapeyron", params=found
        )
    return None


def _extract_enthalpy(text: str) -> ChemistryIntent | None:
    clausius = _extract_clausius(text)
    if clausius is not None:
        return clausius
    if re.search(r"\b(?:calorimeter constant|Ccal)\b", text, re.IGNORECASE):
        match = re.search(
            rf"(?:Ccal|calorimeter constant)\s*=\s*({_N})\s*(k?J)\s*/\s*(?:°\s*C|C|K)\b",
            text,
            re.IGNORECASE,
        )
        constant = None
        if match is not None:
            constant = float(match.group(1)) * (1000 if match.group(2).lower() == "kj" else 1)
        delta = _search(rf"(?:ΔT|delta\s*T)\s*=\s*({_N})", text)
        if constant is not None and delta is not None:
            return ChemistryIntent(
                kind="thermochemistry",
                chemistry_op="calorimetry",
                params={"c_cal": constant, "delta_t": delta},
            )
    if re.search(r"\bHess\b", text, re.IGNORECASE):
        params: dict[str, float] = {}
        steps = set(re.findall(r"ΔH(\d+)\s*=", text))
        multipliers = set(re.findall(r"multiplier(\d+)\s*=", text))
        if (
            not steps
            or len(steps) > 4
            or steps != multipliers
            or steps != {str(n) for n in range(1, len(steps) + 1)}
        ):
            return None  # a step without its multiplier would give a partial sum
        for index in range(1, 5):
            enthalpy = _search(rf"ΔH{index}\s*=\s*({_N})", text)
            multiplier = _search(rf"multiplier{index}\s*=\s*({_N})", text)
            if enthalpy is None or multiplier is None:
                break
            params[f"dh{index}"] = enthalpy
            params[f"m{index}"] = multiplier
        if params:
            return ChemistryIntent(kind="thermochemistry", chemistry_op="hess", params=params)
    if re.search(r"\bformation enthalpy\b", text, re.IGNORECASE):
        equation = _equation(text)
        values = {
            match.group(1): float(match.group(2))
            for match in re.finditer(rf"ΔH(?:°f|f°?)\(({CHEMICAL_FORMULA})\)\s*=\s*({_N})", text)
        }
        if equation and values:
            return ChemistryIntent(
                kind="thermochemistry",
                chemistry_op="formation_enthalpy",
                equation=equation,
                species=values,
            )
    if re.search(r"\bbond enthalpy\b", text, re.IGNORECASE):
        broken = _search(rf"bonds broken\s*=\s*({_N})", text)
        formed = _search(rf"bonds formed\s*=\s*({_N})", text)
        if broken is not None and formed is not None:
            return ChemistryIntent(
                kind="thermochemistry",
                chemistry_op="bond_enthalpy",
                params={"broken": broken, "formed": formed},
            )
    return None
