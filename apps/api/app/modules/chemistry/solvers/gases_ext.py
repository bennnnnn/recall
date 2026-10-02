# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Combined, Boyle, Charles, Dalton, and wet-gas solvers."""

from __future__ import annotations

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.quantity import convert
from app.modules.chemistry.solvers.common_chem import (
    inp,
    num,
    verified,
    water_vapor_mmhg,
)
from app.modules.chemistry.solvers.params import require
from app.modules.chemistry.solvers.relation import solve_paired
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError

_GAS_UNIT = {"p1": "atm", "p2": "atm", "v1": "L", "v2": "L", "t1": "K", "t2": "K"}


def _missing(params: dict[str, float], keys: tuple[str, ...]) -> str:
    missing = [key for key in keys if key not in params]
    if len(missing) != 1:
        raise SolveServiceError("exactly one gas variable must be unknown")
    return missing[0]


def _order(symbol: str) -> tuple[int, str]:
    """Pressure, volume, then temperature: P1V1T2, not T2P1V1."""
    return "PVT".index(symbol[0]), symbol[1:]


def _gas_answer(name: str, value: float) -> str:
    return f"{name.upper()} = {num(value)} {_GAS_UNIT[name]}"


def _gas_given(known: dict[str, float]) -> tuple[str, ...]:
    return tuple(f"{key.upper()} = {inp(item)} {_GAS_UNIT[key]}" for key, item in known.items())


def _solve_pair(
    intent: ChemistryIntent,
    keys: tuple[str, ...],
    left: set[str],
    right: set[str],
    title: str,
    name: str,
    formula: str,
) -> ChemistryResult:
    missing = _missing(intent.params, keys)
    known = {key: require(intent, key, positive=True) for key in keys if key != missing}
    symbols = {key: key.upper() for key in keys}
    value, *working = solve_paired(
        {symbols[key]: amount for key, amount in known.items()},
        symbols[missing],
        sorted((symbols[key] for key in left), key=_order),
        sorted((symbols[key] for key in right), key=_order),
    )
    shown = _gas_answer(missing, value)
    return verified(title, _gas_given(known), missing.upper(), name, formula, working, shown, shown)


def solve_combined_gas(intent: ChemistryIntent) -> ChemistryResult:
    return _solve_pair(
        intent,
        ("p1", "v1", "t1", "p2", "v2", "t2"),
        {"p1", "v1", "t2"},
        {"p2", "v2", "t1"},
        "Verified combined gas law",
        *stated("combined_gas"),
    )


def solve_boyle(intent: ChemistryIntent) -> ChemistryResult:
    return _solve_pair(
        intent,
        ("p1", "v1", "p2", "v2"),
        {"p1", "v1"},
        {"p2", "v2"},
        "Verified Boyle's law",
        *stated("boyle"),
    )


def solve_charles(intent: ChemistryIntent) -> ChemistryResult:
    return _solve_pair(
        intent,
        ("v1", "t1", "v2", "t2"),
        {"v1", "t2"},
        {"v2", "t1"},
        "Verified Charles's law",
        *stated("charles"),
    )


def solve_dalton(intent: ChemistryIntent) -> ChemistryResult:
    if len(intent.species) < 2 or any(value < 0 for value in intent.species.values()):
        raise SolveServiceError("Dalton's law needs partial pressures")
    total = sum(intent.species.values())
    unit = intent.units.get("pressure", "atm")
    shown = f"Ptotal = {num(total)} {unit}"
    terms = " + ".join(inp(value) for value in intent.species.values())
    return verified(
        "Verified Dalton's law",
        tuple(f"P({name}) = {inp(value)} {unit}" for name, value in intent.species.items()),
        "Total pressure",
        *stated("dalton"),
        (f"Ptotal = {terms}",),
        shown,
        shown,
    )


def solve_partial_pressure(intent: ChemistryIntent) -> ChemistryResult:
    fraction = intent.params.get("mole_fraction")
    total = intent.params.get("total_pressure")
    if fraction is None or total is None or not 0 <= fraction <= 1 or total < 0:
        raise SolveServiceError("partial pressure needs a mole fraction and a total pressure")
    unit = intent.units.get("pressure", "atm")
    shown = f"Pi = {num(fraction * total)} {unit}"
    return verified(
        "Verified partial pressure",
        (f"Xi = {inp(fraction)}", f"Ptotal = {inp(total)} {unit}"),
        "Partial pressure",
        *stated("partial_pressure"),
        (f"Pi = ({inp(fraction)})({inp(total)})",),
        shown,
        shown,
    )


def solve_gas_over_water(intent: ChemistryIntent) -> ChemistryResult:
    total = intent.params.get("total_pressure")
    temperature = intent.params.get("temperature_c")
    if total is None or temperature is None or total <= 0:
        raise SolveServiceError("gas over water needs total pressure and temperature")
    vapor = water_vapor_mmhg(temperature)
    if vapor is None:
        raise SolveServiceError("water vapor pressure is only tabulated from 0 to 100 °C")
    unit = intent.units.get("pressure", "mmHg")
    try:
        vapor_same = convert(vapor, "mmHg", unit)
    except (ValueError, TypeError) as exc:
        raise SolveServiceError(f"unsupported pressure unit {unit}") from exc
    dry = total - vapor_same
    if dry <= 0:
        raise SolveServiceError("the dry-gas pressure is not positive")
    shown = f"Pdry = {num(dry)} {unit}"
    return verified(
        "Verified gas collected over water",
        (f"Ptotal = {inp(total)} {unit}", f"T = {inp(temperature)} °C"),
        "Dry-gas pressure",
        *stated("gas_over_water"),
        (
            f"Pwater = {num(vapor_same)} {unit} at {inp(temperature)} °C",
            f"Pdry = {inp(total)} − {num(vapor_same)}",
        ),
        shown,
        shown,
    )
