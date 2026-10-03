# ruff: noqa: RUF001
"""Gas mixtures: Dalton's law, partial pressures, and a gas collected over water."""

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
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError

_SUBSCRIPT = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def _partial(name: str) -> str:
    """P(N2) for a named gas; P₁, P₂ for gases a question only numbers by their order."""
    return f"P{name.translate(_SUBSCRIPT)}" if name.isdigit() else f"P({name})"


def solve_dalton(intent: ChemistryIntent) -> ChemistryResult:
    if len(intent.species) < 2 or any(value < 0 for value in intent.species.values()):
        raise SolveServiceError("Dalton's law needs partial pressures")
    total = sum(intent.species.values())
    unit = intent.units.get("pressure", "atm")
    shown = f"Ptotal = {num(total)} {unit}"
    terms = " + ".join(inp(value) for value in intent.species.values())
    return verified(
        "Verified Dalton's law",
        tuple(f"{_partial(name)} = {inp(value)} {unit}" for name, value in intent.species.items()),
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
