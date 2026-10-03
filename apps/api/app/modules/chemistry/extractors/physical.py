"""Gas, thermochemistry, equilibrium, and kinetics extractors."""

from __future__ import annotations

import re

from app.models.schemas.chemistry import ChemistryIntent, ChemistryOp
from app.modules.chemistry.extractors.parsing import (
    _CANONICAL_PRESSURE,
    _N,
    _PRESSURE_UNIT,
    _equation,
    _floats,
    _partial_pressures,
    _pressure_species,
    _search,
    k_time_unit_conflict,
    timed,
)
from app.modules.chemistry.request import CHEMICAL_FORMULA

_INTEGRATED_ORDERS: tuple[tuple[str, ChemistryOp, ChemistryOp], ...] = (
    ("zero", "zero_order", "zero_order_half_life"),
    ("second", "second_order", "second_order_half_life"),
)


def _labeled(text: str, labels: tuple[tuple[str, str], ...]) -> dict[str, float]:
    found: dict[str, float] = {}
    for key, pattern in labels:
        value = _search(pattern, text)
        if value is not None:
            found[key] = value
    return found


def _extract_graham(text: str) -> ChemistryIntent | None:
    if not re.search(r"\bGraham\b", text, re.IGNORECASE):
        return None
    found = _labeled(
        text,
        (
            ("rate1", rf"\br1\s*=\s*({_N})"),
            ("rate2", rf"\br2\s*=\s*({_N})"),
            ("molar1", rf"\bM1\s*=\s*({_N})"),
            ("molar2", rf"\bM2\s*=\s*({_N})"),
        ),
    )
    if len(found) != 3:
        return None
    return ChemistryIntent(kind="gases", chemistry_op="graham", params=found)


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


def _extract_henry(text: str) -> ChemistryIntent | None:
    if not re.search(r"\bHenry'?s?\s+law\b", text, re.IGNORECASE):
        return None
    found = _labeled(
        text,
        (
            ("concentration", rf"\bC\s*=\s*({_N})"),
            ("henry_constant", rf"\bkH\s*=\s*({_N})"),
            ("pressure", rf"\bP\s*=\s*({_N})"),
        ),
    )
    if len(found) != 2:
        return None
    return ChemistryIntent(kind="solutions", chemistry_op="henry", params=found)


def _extract_gas_laws(text: str) -> ChemistryIntent | None:
    graham = _extract_graham(text)
    if graham is not None:
        return graham
    # Boyle, Charles and the combined and ideal gas laws are physics' (physics/catalog/gas_laws.py),
    # answered in L and atm when the question is written in them.
    if re.search(r"\bDalton\b", text, re.IGNORECASE):
        partials = _partial_pressures(text)
        if partials is not None and len(partials[0]) >= 2:
            return ChemistryIntent(
                kind="gases",
                chemistry_op="dalton",
                species=partials[0],
                units={"pressure": partials[1]},
            )
        return None
    if re.search(r"\bpartial pressure\b", text, re.IGNORECASE):
        fraction = _search(rf"mole fraction\s*=\s*({_N})", text)
        total = re.search(
            rf"total pressure\s*=\s*({_N})\s*({_PRESSURE_UNIT})(?![A-Za-z])", text, re.IGNORECASE
        )
        if fraction is not None and total is not None:
            return ChemistryIntent(
                kind="gases",
                chemistry_op="partial_pressure",
                params={"mole_fraction": fraction, "total_pressure": float(total.group(1))},
                units={"pressure": _CANONICAL_PRESSURE[total.group(2).lower()]},
            )
    if re.search(r"\bover water\b", text, re.IGNORECASE):
        wet = _search(rf"total pressure\s*=\s*({_N})\s*(mmHg|atm|torr|kPa|bar)", text)
        unit = re.search(r"total pressure\s*=\s*" + _N + r"\s*(mmHg|atm|torr|kPa|bar)", text)
        temperature = _search(rf"({_N})\s*(?:°\s*)?C\b", text)
        if wet is not None and temperature is not None and unit is not None:
            return ChemistryIntent(
                kind="gases",
                chemistry_op="gas_over_water",
                params={"total_pressure": wet, "temperature_c": temperature},
                units={"pressure": unit.group(1)},
            )
    return None


def _extract_thermo_ext(text: str) -> ChemistryIntent | None:
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
    if re.search(r"\bICE equilibrium\b", text, re.IGNORECASE) and equation:
        constant = _search(rf"\bK(?:c|eq)?\s*=\s*({_N})", text, flags=0)
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
    for order, name, half_life_name in _INTEGRATED_ORDERS:
        if not re.search(rf"\b{order}[- ]order\b", text, re.IGNORECASE):
            continue
        initial = _search(rf"\[A\](?:0|₀)\s*=\s*({_N})", text, flags=0)
        rate = _search(rf"\bk\s*=\s*({_N})", text)
        if k_time_unit_conflict(text):
            return None  # k per minute with t in seconds cannot be combined unchecked
        if (
            initial is not None
            and rate is not None
            and re.search(r"half[- ]life", text, re.IGNORECASE)
        ):
            return ChemistryIntent(
                kind="kinetics",
                chemistry_op=half_life_name,
                params={"initial": initial, "rate_constant": rate},
            )
        elapsed = timed(text, r"\bt")
        if initial is not None and rate is not None and elapsed is not None and elapsed[1] == "s":
            return ChemistryIntent(
                kind="kinetics",
                chemistry_op=name,
                params={"initial": initial, "rate_constant": rate, "time": elapsed[0]},
                units={"time": "s"},
            )
    if re.search(r"\brate law\b", text, re.IGNORECASE):
        a1 = _search(rf"\ba1\s*=\s*({_N})", text)
        rate1 = _search(rf"\brate1\s*=\s*({_N})", text)
        a2 = _search(rf"\ba2\s*=\s*({_N})", text)
        rate2 = _search(rf"\brate2\s*=\s*({_N})", text)
        params = _floats(a1=a1, rate1=rate1, a2=a2, rate2=rate2)
        second = _floats(
            b1=_search(rf"\bb1\s*=\s*({_N})", text), b2=_search(rf"\bb2\s*=\s*({_N})", text)
        )
        if params is not None:
            return ChemistryIntent(
                kind="kinetics", chemistry_op="rate_law", params={**params, **(second or {})}
            )
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
