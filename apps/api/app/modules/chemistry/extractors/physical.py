"""Gas, thermochemistry, equilibrium, and kinetics extractors."""

from __future__ import annotations

import re

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.extractors.parsing import (
    _N,
    _equation,
    _floats,
    _gas_state,
    _pressure_species,
    _search,
)
from app.modules.chemistry.request import CHEMICAL_FORMULA


def _extract_gas_laws(text: str) -> ChemistryIntent | None:
    if re.search(r"\bcombined gas\b", text, re.IGNORECASE):
        return ChemistryIntent(
            kind="gases",
            chemistry_op="combined_gas",
            params=_gas_state(text, ("p1", "v1", "t1", "p2", "v2", "t2")),
        )
    if re.search(r"\bBoyle\b", text):
        return ChemistryIntent(
            kind="gases", chemistry_op="boyle", params=_gas_state(text, ("p1", "v1", "p2", "v2"))
        )
    if re.search(r"\bCharles\b", text):
        return ChemistryIntent(
            kind="gases", chemistry_op="charles", params=_gas_state(text, ("v1", "t1", "v2", "t2"))
        )
    if re.search(r"\bDalton\b", text):
        partials = {
            match.group(1): float(match.group(2))
            for match in re.finditer(rf"P\(({CHEMICAL_FORMULA})\)\s*=\s*({_N})", text)
        }
        if len(partials) >= 2:
            return ChemistryIntent(
                kind="gases", chemistry_op="dalton", species=partials, units={"pressure": "atm"}
            )
    if re.search(r"\bpartial pressure\b", text, re.IGNORECASE):
        fraction = _search(rf"mole fraction\s*=\s*({_N})", text)
        total = _search(rf"total pressure\s*=\s*({_N})", text)
        if fraction is not None and total is not None:
            return ChemistryIntent(
                kind="gases",
                chemistry_op="partial_pressure",
                params={"mole_fraction": fraction, "total_pressure": total},
                units={"pressure": "atm"},
            )
    if re.search(r"\bover water\b", text, re.IGNORECASE):
        total = _search(rf"total pressure\s*=\s*({_N})\s*(mmHg|atm|torr|kPa|bar)", text)
        unit = re.search(r"total pressure\s*=\s*" + _N + r"\s*(mmHg|atm|torr|kPa|bar)", text)
        temperature = _search(rf"({_N})\s*C\b", text)
        if total is not None and temperature is not None and unit is not None:
            return ChemistryIntent(
                kind="gases",
                chemistry_op="gas_over_water",
                params={"total_pressure": total, "temperature_c": temperature},
                units={"pressure": unit.group(1)},
            )
    return None


def _extract_thermo_ext(text: str) -> ChemistryIntent | None:
    if re.search(r"\b(?:calorimeter constant|Ccal)\b", text, re.IGNORECASE):
        constant = _search(rf"(?:Ccal|calorimeter constant)\s*=\s*({_N})", text)
        delta = _search(rf"(?:ΔT|delta\s*T)\s*=\s*({_N})", text)
        if constant is not None and delta is not None:
            return ChemistryIntent(
                kind="thermochemistry",
                chemistry_op="calorimetry",
                params={"c_cal": constant, "delta_t": delta},
            )
    if re.search(r"\bHess\b", text):
        params: dict[str, float] = {}
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
            for match in re.finditer(rf"ΔHf\(({CHEMICAL_FORMULA})\)\s*=\s*({_N})", text)
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


def _extract_equilibrium_ext(text: str) -> ChemistryIntent | None:
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
    if re.search(r"\bKp\b", text, flags=0) and equation and re.search(r"\bFind Kp\b", text):
        return ChemistryIntent(
            kind="equilibrium",
            chemistry_op="kp",
            equation=equation,
            species=_pressure_species(text, equation),
        )
    if re.search(r"\b(?:Kc to Kp|Kp to Kc)\b", text) and equation:
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
    if re.search(r"\bICE equilibrium\b", text) and equation:
        constant = _search(rf"\bK\s*=\s*({_N})", text, flags=0)
        concentrations = {
            match.group(1): float(match.group(2))
            for match in re.finditer(rf"\[({CHEMICAL_FORMULA})\]\s*=\s*({_N})", text)
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


def _extract_kinetics_ext(text: str) -> ChemistryIntent | None:
    if re.search(r"\bzero[- ]order\b", text, re.IGNORECASE):
        initial = _search(rf"\[A\]0\s*=\s*({_N})", text, flags=0)
        rate = _search(rf"\bk\s*=\s*({_N})", text)
        if (
            initial is not None
            and rate is not None
            and re.search(r"half[- ]life", text, re.IGNORECASE)
        ):
            return ChemistryIntent(
                kind="kinetics",
                chemistry_op="zero_order_half_life",
                params={"initial": initial, "rate_constant": rate},
            )
        time = _search(rf"\bt\s*=\s*({_N})\s*s", text)
        if initial is not None and rate is not None and time is not None:
            return ChemistryIntent(
                kind="kinetics",
                chemistry_op="zero_order",
                params={"initial": initial, "rate_constant": rate, "time": time},
            )
    if re.search(r"\bsecond[- ]order\b", text, re.IGNORECASE):
        initial = _search(rf"\[A\]0\s*=\s*({_N})", text, flags=0)
        rate = _search(rf"\bk\s*=\s*({_N})", text)
        if (
            initial is not None
            and rate is not None
            and re.search(r"half[- ]life", text, re.IGNORECASE)
        ):
            return ChemistryIntent(
                kind="kinetics",
                chemistry_op="second_order_half_life",
                params={"initial": initial, "rate_constant": rate},
            )
        time = _search(rf"\bt\s*=\s*({_N})\s*s", text)
        if initial is not None and rate is not None and time is not None:
            return ChemistryIntent(
                kind="kinetics",
                chemistry_op="second_order",
                params={"initial": initial, "rate_constant": rate, "time": time},
            )
    if re.search(r"\brate law\b", text, re.IGNORECASE):
        a1 = _search(rf"\ba1\s*=\s*({_N})", text)
        rate1 = _search(rf"\brate1\s*=\s*({_N})", text)
        a2 = _search(rf"\ba2\s*=\s*({_N})", text)
        rate2 = _search(rf"\brate2\s*=\s*({_N})", text)
        params = _floats(a1=a1, rate1=rate1, a2=a2, rate2=rate2)
        if params is not None:
            return ChemistryIntent(kind="kinetics", chemistry_op="rate_law", params=params)
    if re.search(r"\btwo-temperature Arrhenius\b", text, re.IGNORECASE):
        params = _floats(
            k1=_search(rf"\bk1\s*=\s*({_N})", text),
            t1=_search(rf"\bt1\s*=\s*({_N})", text),
            k2=_search(rf"\bk2\s*=\s*({_N})", text),
            t2=_search(rf"\bt2\s*=\s*({_N})", text),
        )
        if params is not None:
            return ChemistryIntent(
                kind="kinetics", chemistry_op="arrhenius_two_point", params=params
            )
    return None
