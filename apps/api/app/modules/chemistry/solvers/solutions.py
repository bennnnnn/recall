# ruff: noqa: RUF001, RUF002 -- textbook formulas use Unicode charge and minus notation.
"""Solution, acid–base, gas, and analytical chemistry calculations."""

from __future__ import annotations

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.quantity import convert, to_liters
from app.modules.chemistry.solvers.common_chem import (
    const,
    converted_from,
    inp,
    num,
    qty,
    verified,
)
from app.modules.chemistry.solvers.constants import GAS_R
from app.modules.chemistry.solvers.params import require
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError


def _volume_in_l(value: float, unit: str) -> float:
    try:
        return to_liters(value, unit)
    except (ValueError, TypeError) as exc:
        raise SolveServiceError(f"unsupported dilution volume unit: {unit}") from exc


def _stock_volume(intent: ChemistryIntent) -> ChemistryResult:
    """V1 = M2V2 / M1: the stock a dilution starts from, in the unit asked or V2's."""
    m1 = require(intent, "m1", positive=True)
    m2 = require(intent, "m2", positive=True)
    v2 = require(intent, "v2", positive=True)
    if m2 > m1:
        raise SolveServiceError("a dilution cannot make a solution stronger than its stock")
    v2_unit = intent.units.get("v2", "L")
    v1_unit = intent.units.get("v1", v2_unit)
    in_v2_unit = m2 * v2 / m1
    try:
        volume = convert(in_v2_unit, v2_unit, v1_unit)
    except ValueError as exc:
        raise SolveServiceError(f"unsupported dilution volume unit: {v1_unit}") from exc
    value = f"{num(volume)} {v1_unit}"
    rows = [f"V1 = ({qty(m2, 'mol/L')})({qty(v2, v2_unit)}) / {qty(m1, 'mol/L')}"]
    if v1_unit != v2_unit:
        rows.append(f"V1 = {num(in_v2_unit)} {v2_unit} = {value}")
    return verified(
        "Verified dilution",
        (f"M1 = {inp(m1)} mol/L", f"M2 = {inp(m2)} mol/L", f"V2 = {inp(v2)} {v2_unit}"),
        "Volume of the stock solution, V1",
        *stated("dilution"),
        tuple(rows),
        f"V1 = {value}",
        value,
    )


def solve_solution(intent: ChemistryIntent) -> ChemistryResult:
    op = intent.chemistry_op
    if op == "molarity":
        moles = require(intent, "moles", non_negative=True)
        volume = require(intent, "volume_l", positive=True)
        molarity = moles / volume
        value = f"{num(molarity)} mol/L"
        return verified(
            "Verified molarity",
            (f"n = {inp(moles)} mol", f"V = {inp(volume)} L"),
            "Molarity, c",
            *stated("molarity"),
            (f"c = {qty(moles, 'mol')} / {qty(volume, 'L')}",),
            f"c = {value}",
            value,
        )
    if op == "dilution" and "v1" not in intent.params:
        return _stock_volume(intent)
    if op == "dilution":
        m1 = require(intent, "m1", positive=True)
        v1 = require(intent, "v1", positive=True)
        m2 = intent.params.get("m2")
        v2 = intent.params.get("v2")
        v1_unit = intent.units.get("v1", "L")
        if (m2 is None) == (v2 is None):
            raise SolveServiceError("exactly one of M2 or V2 must be unknown")
        if v2 is None:
            if m2 is None or m2 <= 0:
                raise SolveServiceError("M2 must be positive")
            result = m1 * v1 / m2
            value = f"{num(result)} {v1_unit}"
            find = "Final volume, V2"
            substitution: tuple[str, ...] = (
                f"V2 = ({qty(m1, 'mol/L')})({qty(v1, v1_unit)}) / {qty(m2, 'mol/L')}",
            )
            answer = f"V2 = {value}"
            given = (
                f"M1 = {inp(m1)} mol/L",
                f"V1 = {inp(v1)} {v1_unit}",
                f"M2 = {inp(m2)} mol/L",
            )
        else:
            if v2 <= 0:
                raise SolveServiceError("V2 must be positive")
            v2_unit = intent.units.get("v2", v1_unit)
            v1_l = _volume_in_l(v1, v1_unit)
            v2_l = _volume_in_l(v2, v2_unit)
            result = m1 * v1_l / v2_l
            value = f"{num(result)} mol/L"
            find = "Final concentration, M2"
            # M1V1 = M2V2 holds in any one volume unit; two different ones meet in litres.
            if v1_unit == v2_unit:
                substitution = (
                    f"M2 = ({qty(m1, 'mol/L')})({qty(v1, v1_unit)}) / {qty(v2, v2_unit)}",
                )
            else:
                litres = {"V1": converted_from(v1_l, v1), "V2": converted_from(v2_l, v2)}
                in_litres = tuple(
                    f"{name} = {qty(volume, unit)} = {litres[name]} L"
                    for name, volume, unit in (("V1", v1, v1_unit), ("V2", v2, v2_unit))
                    if unit != "L"
                )
                substitution = (
                    *in_litres,
                    f"M2 = ({qty(m1, 'mol/L')})({litres['V1']} L) / {litres['V2']} L",
                )
            answer = f"M2 = {value}"
            given = (
                f"M1 = {inp(m1)} mol/L",
                f"V1 = {inp(v1)} {v1_unit}",
                f"V2 = {inp(v2)} {v2_unit}",
            )
        return verified(
            "Verified dilution",
            given,
            find,
            *stated("dilution"),
            substitution,
            answer,
            value,
        )
    if op == "molality":
        moles = require(intent, "moles", non_negative=True)
        solvent_kg = require(intent, "solvent_kg", positive=True)
        result = moles / solvent_kg
        value = f"{num(result)} mol/kg"
        return verified(
            "Verified molality",
            (
                f"solute = {inp(moles)} mol",
                f"solvent mass = {inp(solvent_kg)} kg",
            ),
            "Molality, b",
            *stated("molality"),
            (f"b = {qty(moles, 'mol')} / {qty(solvent_kg, 'kg')}",),
            f"b = {value}",
            value,
        )
    if op == "mass_percent":
        solute = require(intent, "solute_mass")
        solution = require(intent, "solution_mass", positive=True)
        if solute < 0 or solute > solution:
            raise SolveServiceError("solute mass must be between zero and solution mass")
        result = solute / solution * 100
        value = f"{num(result)}%"
        return verified(
            "Verified mass percent",
            (
                f"solute mass = {inp(solute)} g",
                f"solution mass = {inp(solution)} g",
            ),
            "Mass percent",
            *stated("mass_percent"),
            (f"mass % = ({qty(solute, 'g')} / {qty(solution, 'g')}) × 100",),
            f"Mass percent = {value}",
            value,
        )
    raise SolveServiceError(f"unsupported solution operation: {op}")


def _colligative(
    intent: ChemistryIntent,
    constant_name: str,
    constant_label: str,
    symbol: str,
    title: str,
    operation: str,
) -> ChemistryResult:
    factor = intent.params.get("i")
    constant = intent.params.get(constant_name)
    molality = intent.params.get("molality")
    if factor is None or constant is None or molality is None or factor <= 0 or molality < 0:
        raise SolveServiceError("colligative inputs must be physically valid")
    value = factor * constant * molality
    shown = f"{symbol} = {num(value)} °C"
    return verified(
        title,
        (
            f"i = {inp(factor)}",
            f"{constant_label} = {inp(constant)} °C·kg/mol",
            f"m = {inp(molality)} mol/kg",
        ),
        symbol,
        *stated(operation),
        (f"{symbol} = ({inp(factor)})({inp(constant)})({inp(molality)})",),
        shown,
        shown,
    )


def solve_boiling(intent: ChemistryIntent) -> ChemistryResult:
    return _colligative(
        intent, "kb", "Kb", "ΔTb", "Verified boiling-point elevation", "boiling_elevation"
    )


def solve_freezing(intent: ChemistryIntent) -> ChemistryResult:
    return _colligative(
        intent, "kf", "Kf", "ΔTf", "Verified freezing-point depression", "freezing_depression"
    )


def solve_osmotic(intent: ChemistryIntent) -> ChemistryResult:
    factor = intent.params.get("i")
    molarity = intent.params.get("molarity")
    temperature = intent.params.get("temperature")
    if (
        factor is None
        or molarity is None
        or temperature is None
        or factor <= 0
        or molarity < 0
        or temperature <= 0
    ):
        raise SolveServiceError("osmotic pressure inputs must be physically valid")
    value = factor * molarity * GAS_R * temperature
    shown = f"Π = {num(value)} atm"
    return verified(
        "Verified osmotic pressure",
        (f"i = {inp(factor)}", f"M = {inp(molarity)} mol/L", f"T = {inp(temperature)} K"),
        "Osmotic pressure",
        *stated("osmotic_pressure"),
        (f"Π = ({inp(factor)})({inp(molarity)})({const(GAS_R)})({inp(temperature)})",),
        shown,
        shown,
    )


def solve_raoult(intent: ChemistryIntent) -> ChemistryResult:
    fraction = intent.params.get("mole_fraction")
    pure = intent.params.get("pure_pressure")
    if fraction is None or pure is None or not 0 <= fraction <= 1 or pure < 0:
        raise SolveServiceError("Raoult's law needs a mole fraction and a pure pressure")
    unit = intent.units.get("pressure", "")
    suffix = f" {unit}" if unit else ""
    shown = f"P = {num(fraction * pure)}{suffix}"
    return verified(
        "Verified Raoult's law",
        (f"X = {inp(fraction)}", f"P° = {inp(pure)}{suffix}"),
        "Vapor pressure",
        *stated("raoult"),
        (f"P = ({inp(fraction)})({inp(pure)})",),
        shown,
        shown,
    )
