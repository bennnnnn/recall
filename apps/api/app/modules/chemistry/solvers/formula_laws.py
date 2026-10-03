# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Graham's law, a two-point Clausius-Clapeyron solve, and Henry's law."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.solvers.common_chem import const, inp, num, verified
from app.modules.chemistry.solvers.constants import GAS_R_J
from app.modules.chemistry.solvers.params import require
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError

_GRAHAM = ("rate1", "rate2", "molar1", "molar2")
_GRAHAM_MESSAGE = "Graham's law needs exactly three positive rates or molar masses"


def solve_graham(intent: ChemistryIntent) -> ChemistryResult:
    present = [key for key in _GRAHAM if intent.params.get(key) is not None]
    if len(present) != 3:
        raise SolveServiceError(_GRAHAM_MESSAGE)
    values = {key: require(intent, key, positive=True, message=_GRAHAM_MESSAGE) for key in present}
    missing = next(key for key in _GRAHAM if key not in values)
    rate1, rate2, molar1, molar2, shown, working = _graham_unknown(missing, values)
    return verified(
        "Verified Graham's law",
        (
            f"rate1 = {inp(rate1)}",
            f"rate2 = {inp(rate2)}",
            f"M1 = {inp(molar1)}",
            f"M2 = {inp(molar2)}",
        ),
        "Graham's law",
        *stated("graham"),
        (working,),
        shown,
        shown,
    )


def _graham_unknown(
    missing: str, values: dict[str, float]
) -> tuple[float, float, float, float, str, str]:
    if missing == "rate2":
        rate2 = values["rate1"] * math.sqrt(values["molar1"] / values["molar2"])
        working = (
            f"rate2 = {inp(values['rate1'])} × √({inp(values['molar1'])} / "
            f"{inp(values['molar2'])}) = {num(rate2)}"
        )
        return (
            values["rate1"],
            rate2,
            values["molar1"],
            values["molar2"],
            f"rate2 = {num(rate2)}",
            working,
        )
    if missing == "rate1":
        rate1 = values["rate2"] * math.sqrt(values["molar2"] / values["molar1"])
        working = (
            f"rate1 = {inp(values['rate2'])} × √({inp(values['molar2'])} / "
            f"{inp(values['molar1'])}) = {num(rate1)}"
        )
        return (
            rate1,
            values["rate2"],
            values["molar1"],
            values["molar2"],
            f"rate1 = {num(rate1)}",
            working,
        )
    if missing == "molar1":
        molar1 = values["molar2"] * (values["rate2"] / values["rate1"]) ** 2
        working = (
            f"M1 = {inp(values['molar2'])} × ({inp(values['rate2'])} / "
            f"{inp(values['rate1'])})^2 = {num(molar1)}"
        )
        return (
            values["rate1"],
            values["rate2"],
            molar1,
            values["molar2"],
            f"M1 = {num(molar1)}",
            working,
        )
    molar2 = values["molar1"] * (values["rate1"] / values["rate2"]) ** 2
    working = (
        f"M2 = {inp(values['molar1'])} × ({inp(values['rate1'])} / "
        f"{inp(values['rate2'])})^2 = {num(molar2)}"
    )
    return (
        values["rate1"],
        values["rate2"],
        values["molar1"],
        molar2,
        f"M2 = {num(molar2)}",
        working,
    )


def solve_clausius(intent: ChemistryIntent) -> ChemistryResult:
    message = (
        "two-point Clausius-Clapeyron needs two temperatures and either both "
        "pressures or one pressure with the enthalpy"
    )
    temperatures = (
        require(intent, "t1", positive=True, message=message),
        require(intent, "t2", positive=True, message=message),
    )
    if temperatures[0] == temperatures[1]:
        raise SolveServiceError(message)
    has_p1 = intent.params.get("p1") is not None
    has_p2 = intent.params.get("p2") is not None
    has_enthalpy = intent.params.get("delta_h") is not None
    if has_p1 and has_p2 and not has_enthalpy:
        return _clausius_enthalpy(intent, message)
    if has_enthalpy and has_p1 != has_p2:
        return _clausius_pressure(intent, message, unknown="p2" if has_p1 else "p1")
    raise SolveServiceError(message)


def _clausius_enthalpy(intent: ChemistryIntent, message: str) -> ChemistryResult:
    p1 = require(intent, "p1", positive=True, message=message)
    t1 = require(intent, "t1", positive=True, message=message)
    p2 = require(intent, "p2", positive=True, message=message)
    t2 = require(intent, "t2", positive=True, message=message)
    enthalpy = -GAS_R_J * math.log(p2 / p1) / (1 / t2 - 1 / t1)
    shown = f"ΔHvap = {num(enthalpy / 1000)} kJ/mol"
    return verified(
        "Verified two-point Clausius-Clapeyron",
        (f"P1 = {inp(p1)}", f"T1 = {inp(t1)} K", f"P2 = {inp(p2)}", f"T2 = {inp(t2)} K"),
        "Enthalpy of vaporization",
        *stated("clausius_clapeyron"),
        (
            f"ΔHvap = −({const(GAS_R_J)})ln({inp(p2)} / {inp(p1)}) / "
            f"(1/{inp(t2)} − 1/{inp(t1)}) = {num(enthalpy)} J/mol",
        ),
        shown,
        shown,
    )


def _clausius_pressure(intent: ChemistryIntent, message: str, *, unknown: str) -> ChemistryResult:
    known = "p1" if unknown == "p2" else "p2"
    pressure = require(intent, known, positive=True, message=message)
    t1 = require(intent, "t1", positive=True, message=message)
    t2 = require(intent, "t2", positive=True, message=message)
    enthalpy = require(intent, "delta_h", positive=True, message=message)
    exponent = -enthalpy / GAS_R_J * (1 / t2 - 1 / t1)
    solved = pressure * math.exp(exponent if unknown == "p2" else -exponent)
    label = "P2" if unknown == "p2" else "P1"
    other = "P1" if unknown == "p2" else "P2"
    shown = f"{label} = {num(solved)}"
    factor = (
        f"exp[−({inp(enthalpy)}) / ({const(GAS_R_J)}) × (1/{inp(t2)} − 1/{inp(t1)})]"
    )
    relation = "×" if unknown == "p2" else "/"
    return verified(
        "Verified two-point Clausius-Clapeyron",
        (
            f"{other} = {inp(pressure)}",
            f"T1 = {inp(t1)} K",
            f"T2 = {inp(t2)} K",
            f"ΔHvap = {inp(enthalpy)} J/mol",
        ),
        label,
        *stated("clausius_clapeyron"),
        (f"{label} = {inp(pressure)} {relation} {factor} = {num(solved)}",),
        shown,
        shown,
    )


def solve_henry(intent: ChemistryIntent) -> ChemistryResult:
    message = "Henry's law needs exactly two of concentration, kH, and pressure"
    keys = ("concentration", "henry_constant", "pressure")
    present = [key for key in keys if intent.params.get(key) is not None]
    if len(present) != 2:
        raise SolveServiceError(message)
    values = {key: require(intent, key, positive=True, message=message) for key in present}
    missing = next(key for key in keys if key not in values)
    concentration, constant, pressure, shown, working = _henry_unknown(missing, values)
    return verified(
        "Verified Henry's law",
        (
            f"C = {inp(concentration)}",
            f"kH = {inp(constant)}",
            f"P = {inp(pressure)}",
        ),
        "Henry's law",
        *stated("henry"),
        (working,),
        shown,
        shown,
    )


def _henry_unknown(
    missing: str, values: dict[str, float]
) -> tuple[float, float, float, str, str]:
    if missing == "concentration":
        concentration = values["henry_constant"] * values["pressure"]
        working = (
            f"C = {inp(values['henry_constant'])} × {inp(values['pressure'])}"
            f" = {num(concentration)}"
        )
        return (
            concentration,
            values["henry_constant"],
            values["pressure"],
            f"C = {num(concentration)}",
            working,
        )
    if missing == "pressure":
        pressure = values["concentration"] / values["henry_constant"]
        working = (
            f"P = {inp(values['concentration'])} / {inp(values['henry_constant'])}"
            f" = {num(pressure)}"
        )
        return (
            values["concentration"],
            values["henry_constant"],
            pressure,
            f"P = {num(pressure)}",
            working,
        )
    constant = values["concentration"] / values["pressure"]
    working = f"kH = {inp(values['concentration'])} / {inp(values['pressure'])} = {num(constant)}"
    return values["concentration"], constant, values["pressure"], f"kH = {num(constant)}", working
