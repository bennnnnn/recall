# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Combined, Boyle, Charles, Dalton, and wet-gas solvers."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.quantity import convert
from app.modules.chemistry.solvers.common_chem import (
    num,
    verified,
    water_vapor_mmhg,
)
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import MathServiceError

_GAS_UNIT = {"p1": "atm", "p2": "atm", "v1": "L", "v2": "L", "t1": "K", "t2": "K"}
_PRESSURE_PINT = {
    "atm": "atm",
    "mmhg": "mmHg",
    "torr": "torr",
    "kpa": "kilopascal",
    "pa": "pascal",
    "bar": "bar",
}


def _missing(params: dict[str, float], keys: tuple[str, ...]) -> str:
    missing = [key for key in keys if key not in params]
    if len(missing) != 1:
        raise MathServiceError("exactly one gas variable must be unknown")
    return missing[0]


def _positive(params: dict[str, float], key: str) -> float:
    value = params[key]
    if value <= 0:
        raise MathServiceError(f"{key} must be positive")
    return value


def _gas_answer(name: str, value: float) -> str:
    return f"{name} = {num(value)} {_GAS_UNIT[name]}"


def _paired_unknown(
    known: dict[str, float], missing: str, left: set[str], right: set[str]
) -> float:
    """Solve ``product(left) = product(right)`` for the one missing name."""
    if missing in left:
        numerator = math.prod(known[key] for key in right)
        denominator = math.prod(known[key] for key in left - {missing})
    else:
        numerator = math.prod(known[key] for key in left)
        denominator = math.prod(known[key] for key in right - {missing})
    return numerator / denominator


def solve_combined_gas(intent: ChemistryIntent) -> ChemistryResult:
    keys = ("p1", "v1", "t1", "p2", "v2", "t2")
    missing = _missing(intent.params, keys)
    known = {key: _positive(intent.params, key) for key in keys if key != missing}
    value = _paired_unknown(known, missing, {"p1", "v1", "t2"}, {"p2", "v2", "t1"})
    shown = _gas_answer(missing, value)
    return verified(
        "Verified combined gas law",
        tuple(f"{key} = {num(item)} {_GAS_UNIT[key]}" for key, item in known.items()),
        missing,
        "Combined gas law",
        "P1V1 / T1 = P2V2 / T2",
        (shown,),
        shown,
        shown,
    )


def solve_boyle(intent: ChemistryIntent) -> ChemistryResult:
    keys = ("p1", "v1", "p2", "v2")
    missing = _missing(intent.params, keys)
    known = {key: _positive(intent.params, key) for key in keys if key != missing}
    value = _paired_unknown(known, missing, {"p1", "v1"}, {"p2", "v2"})
    shown = _gas_answer(missing, value)
    return verified(
        "Verified Boyle's law",
        tuple(f"{key} = {num(item)} {_GAS_UNIT[key]}" for key, item in known.items()),
        missing,
        "Boyle's law",
        "P1V1 = P2V2",
        (shown,),
        shown,
        shown,
    )


def solve_charles(intent: ChemistryIntent) -> ChemistryResult:
    keys = ("v1", "t1", "v2", "t2")
    missing = _missing(intent.params, keys)
    known = {key: _positive(intent.params, key) for key in keys if key != missing}
    value = _paired_unknown(known, missing, {"v1", "t2"}, {"v2", "t1"})
    shown = _gas_answer(missing, value)
    return verified(
        "Verified Charles's law",
        tuple(f"{key} = {num(item)} {_GAS_UNIT[key]}" for key, item in known.items()),
        missing,
        "Charles's law",
        "V1 / T1 = V2 / T2",
        (shown,),
        shown,
        shown,
    )


def solve_dalton(intent: ChemistryIntent) -> ChemistryResult:
    if len(intent.species) < 2 or any(value < 0 for value in intent.species.values()):
        raise MathServiceError("Dalton's law needs partial pressures")
    total = sum(intent.species.values())
    unit = intent.units.get("pressure", "atm")
    shown = f"Ptotal = {num(total)} {unit}"
    return verified(
        "Verified Dalton's law",
        tuple(f"P({name}) = {num(value)} {unit}" for name, value in intent.species.items()),
        "Total pressure",
        "Dalton's law",
        "Ptotal = Σ Pi",
        (shown,),
        shown,
        shown,
    )


def solve_partial_pressure(intent: ChemistryIntent) -> ChemistryResult:
    fraction = intent.params.get("mole_fraction")
    total = intent.params.get("total_pressure")
    if fraction is None or total is None or not 0 <= fraction <= 1 or total < 0:
        raise MathServiceError("partial pressure needs a mole fraction and a total pressure")
    unit = intent.units.get("pressure", "atm")
    shown = f"Pi = {num(fraction * total)} {unit}"
    return verified(
        "Verified partial pressure",
        (f"Xi = {num(fraction)}", f"Ptotal = {num(total)} {unit}"),
        "Partial pressure",
        "Mole fraction",
        "Pi = Xi Ptotal",
        (shown,),
        shown,
        shown,
    )


def solve_gas_over_water(intent: ChemistryIntent) -> ChemistryResult:
    total = intent.params.get("total_pressure")
    temperature = intent.params.get("temperature_c")
    if total is None or temperature is None or total <= 0:
        raise MathServiceError("gas over water needs total pressure and temperature")
    vapor = water_vapor_mmhg(temperature)
    if vapor is None:
        raise MathServiceError("water vapor pressure is only tabulated from 0 to 100 °C")
    unit = intent.units.get("pressure", "mmHg")
    try:
        pint = _PRESSURE_PINT[unit.strip().lower()]
    except KeyError as exc:
        raise MathServiceError(f"unsupported pressure unit {unit}") from exc
    vapor_same = convert(vapor, "mmHg", pint)
    dry = total - vapor_same
    if dry <= 0:
        raise MathServiceError("the dry-gas pressure is not positive")
    shown = f"Pdry = {num(dry)} {unit}"
    return verified(
        "Verified gas collected over water",
        (f"Ptotal = {num(total)} {unit}", f"T = {num(temperature)} °C"),
        "Dry-gas pressure",
        "Dalton's law with water vapor",
        "Pdry = Ptotal − Pwater",
        (f"Pwater = {num(vapor_same)} {unit}", shown),
        shown,
        shown,
    )
