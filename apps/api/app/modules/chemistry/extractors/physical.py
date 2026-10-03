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
from app.modules.chemistry.quantity import to_atm
from app.modules.chemistry.request import CHEMICAL_FORMULA
from app.modules.chemistry.species_facts import dissolution_equation, named_species

_INTEGRATED_ORDERS: tuple[tuple[str, ChemistryOp, ChemistryOp], ...] = (
    ("zero", "zero_order", "zero_order_half_life"),
    ("second", "second_order", "second_order_half_life"),
)


_PRESSURE = re.compile(rf"({_N})\s*({_PRESSURE_UNIT})(?![A-Za-z])", re.IGNORECASE)
_LISTED_PARTIALS = re.compile(r"\bpartial\s+pressures\b", re.IGNORECASE)


def _listed_partials(text: str) -> tuple[dict[str, float], str] | None:
    """ "The partial pressures are 0.3 atm, 0.5 atm and 0.2 atm": every pressure the question
    states is one gas's, numbered in order. A stated total would be a different question."""
    if not re.search(r"\btotal\s+pressure\b", text, re.IGNORECASE):
        return None
    rows = [(float(match.group(1)), match.group(2)) for match in _PRESSURE.finditer(text)]
    if len(rows) < 2 or re.search(rf"\btotal\s+pressure\s+(?:=|is|of)\s*{_N}", text, re.I):
        return None
    units = {_CANONICAL_PRESSURE[unit.lower()] for _value, unit in rows}
    if len(units) == 1:
        unit = units.pop()
        return {str(index): value for index, (value, _) in enumerate(rows, 1)}, unit
    return {str(index): to_atm(value, unit) for index, (value, unit) in enumerate(rows, 1)}, "atm"


def _extract_gas_laws(text: str) -> ChemistryIntent | None:
    # Boyle, Charles and the combined and ideal gas laws are physics' (physics/catalog/gas_laws.py),
    # answered in L and atm when the question is written in them.
    if _LISTED_PARTIALS.search(text) and not re.search(r"\bP\(", text):
        listed = _listed_partials(text)
        if listed is not None:
            return ChemistryIntent(
                kind="gases",
                chemistry_op="dalton",
                species=listed[0],
                units={"pressure": listed[1]},
            )
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


_ICE_ASK = re.compile(r"\bICE equilibrium\b|\bequilibrium\s+concentrations?\b", re.IGNORECASE)
_CONCENTRATION_CHAIN = re.compile(rf"((?:\[{CHEMICAL_FORMULA}\]\s*=\s*)+)({_N})")


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
