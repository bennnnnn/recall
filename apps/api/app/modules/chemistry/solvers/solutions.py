# ruff: noqa: RUF001, RUF002 -- textbook formulas use Unicode charge and minus notation.
"""Solution, acid–base, gas, and analytical chemistry calculations."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.quantity import to_liters
from app.modules.chemistry.solvers.common_chem import inp, num, p_value, verified
from app.modules.chemistry.solvers.constants import PKW
from app.modules.chemistry.solvers.params import require
from app.modules.chemistry.solvers.relation import solve_paired
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError


def _volume_in_l(value: float, unit: str) -> float:
    try:
        return to_liters(value, unit)
    except (ValueError, TypeError) as exc:
        raise SolveServiceError(f"unsupported dilution volume unit: {unit}") from exc


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
            (f"c = {inp(moles)} / {inp(volume)}",),
            f"c = {value}",
            value,
        )
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
            substitution = f"V2 = ({inp(m1)})({inp(v1)}) / {inp(m2)}"
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
            substitution = f"M2 = ({inp(m1)})({inp(v1_l)} L) / ({inp(v2_l)} L)"
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
            (substitution,),
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
            (f"b = {inp(moles)} / {inp(solvent_kg)}",),
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
            (f"mass % = ({inp(solute)} / {inp(solution)}) × 100",),
            f"Mass percent = {value}",
            value,
        )
    raise SolveServiceError(f"unsupported solution operation: {op}")


def solve_acid_base(intent: ChemistryIntent) -> ChemistryResult:
    op = intent.chemistry_op
    if op == "ph_from_h":
        concentration = require(intent, "h", positive=True)
        ph = -math.log10(concentration)
        value = p_value(ph)
        return verified(
            "Verified pH calculation",
            (f"[H+] = {inp(concentration)} mol/L",),
            "pH",
            *stated("ph_from_h"),
            (f"pH = −log10({inp(concentration)})",),
            f"pH = {value}",
            value,
        )
    if op == "ph_from_poh":
        poh = require(intent, "poh")
        ph = PKW - poh
        value = p_value(ph)
        return verified(
            "Verified pH calculation",
            (f"pOH = {inp(poh)}", f"pKw = {PKW} at 25 °C"),
            "pH",
            *stated("ph_from_poh"),
            (f"pH = {PKW} − {inp(poh)}",),
            f"pH = {value}",
            value,
        )
    if op == "h_from_ph":
        ph = require(intent, "ph")
        concentration = 10 ** (-ph)
        value = f"{num(concentration)} mol/L"
        return verified(
            "Verified pH calculation",
            (f"pH = {inp(ph)}",),
            "[H+]",
            *stated("h_from_ph"),
            (f"[H+] = 10^(-{inp(ph)})",),
            f"[H+] = {value}",
            value,
        )
    if op == "poh_from_oh":
        concentration = require(intent, "oh", positive=True)
        poh = -math.log10(concentration)
        value = p_value(poh)
        return verified(
            "Verified pOH calculation",
            (f"[OH-] = {inp(concentration)} mol/L",),
            "pOH",
            *stated("poh_from_oh"),
            (f"pOH = −log10({inp(concentration)})",),
            f"pOH = {value}",
            value,
        )
    if op == "buffer_ph":
        pka = require(intent, "pka")
        base = require(intent, "base", positive=True)
        acid = require(intent, "acid", positive=True)
        ph = pka + math.log10(base / acid)
        value = p_value(ph)
        return verified(
            "Verified buffer pH",
            (
                f"pKa = {inp(pka)}",
                f"[A-] = {inp(base)} mol/L",
                f"[HA] = {inp(acid)} mol/L",
            ),
            "Buffer pH",
            *stated("buffer_ph"),
            (f"pH = {inp(pka)} + log10({inp(base)}/{inp(acid)})",),
            f"pH = {value}",
            value,
        )
    raise SolveServiceError(f"unsupported acid-base operation: {op}")


_BEER = {
    "absorbance": ("A", "", "A = {}"),
    "epsilon": ("ε", "L/(mol·cm)", "ε = {} L/(mol·cm)"),
    "path": ("b", "cm", "b = {} cm"),
    "concentration": ("c", "mol/L", "c = {} mol/L"),
}


def solve_beer_lambert(intent: ChemistryIntent) -> ChemistryResult:
    values = {name: intent.params.get(name) for name in _BEER}
    missing = [name for name, value in values.items() if value is None]
    if len(missing) != 1:
        raise SolveServiceError("exactly one Beer–Lambert variable must be unknown")
    known_values = [value for value in values.values() if value is not None]
    if any(value < 0 for value in known_values) or any(
        values[name] == 0 for name in ("epsilon", "path", "concentration")
    ):
        raise SolveServiceError("Beer–Lambert inputs must be physically valid")
    unknown = missing[0]
    symbol, unit, _ = _BEER[unknown]
    known = {_BEER[name][0]: value for name, value in values.items() if value is not None}
    result, rearranged, substitution = solve_paired(known, symbol, ["A"], ["ε", "b", "c"])
    value = f"{num(result)}{f' {unit}' if unit else ''}"
    given = tuple(
        _BEER[name][2].format(inp(amount)) for name, amount in values.items() if amount is not None
    )
    return verified(
        "Verified Beer–Lambert calculation",
        given,
        symbol,
        *stated("beer_lambert"),
        (rearranged, substitution),
        f"{symbol} = {value}",
        value,
    )
