# ruff: noqa: RUF001, RUF002 -- textbook formulas use Unicode charge and minus notation.
"""Solution, acid–base, gas, and analytical chemistry calculations."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.solvers.common_chem import const, inp, num
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError

GAS_R = 0.082057366080960  # L·atm·mol⁻¹·K⁻¹
_VOLUME_TO_L = {"l": 1.0, "ml": 0.001}


def _value(intent: ChemistryIntent, key: str, *, positive: bool = False) -> float:
    try:
        value = intent.params[key]
    except KeyError as exc:
        raise SolveServiceError(f"missing chemistry parameter: {key}") from exc
    if positive and value <= 0:
        raise SolveServiceError(f"{key} must be positive")
    return value


def _volume_in_l(value: float, unit: str) -> float:
    try:
        return value * _VOLUME_TO_L[unit.lower()]
    except KeyError as exc:
        raise SolveServiceError(f"unsupported dilution volume unit: {unit}") from exc


def solve_solution(intent: ChemistryIntent) -> ChemistryResult:
    op = intent.chemistry_op
    if op == "molarity":
        moles = _value(intent, "moles")
        volume = _value(intent, "volume_l", positive=True)
        molarity = moles / volume
        value = f"{num(molarity)} mol/L"
        return ChemistryResult(
            "Verified molarity",
            (f"n = {inp(moles)} mol", f"V = {inp(volume)} L"),
            "Molarity, c",
            "Molar concentration",
            "c = n / V",
            (f"c = {inp(moles)} / {inp(volume)}",),
            f"c = {value}",
            value,
        )
    if op == "dilution":
        m1 = _value(intent, "m1", positive=True)
        v1 = _value(intent, "v1", positive=True)
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
        return ChemistryResult(
            "Verified dilution",
            given,
            find,
            "Dilution equation",
            "M1V1 = M2V2",
            (substitution,),
            answer,
            value,
        )
    if op == "molality":
        moles = _value(intent, "moles")
        solvent_kg = _value(intent, "solvent_kg", positive=True)
        result = moles / solvent_kg
        value = f"{num(result)} mol/kg"
        return ChemistryResult(
            "Verified molality",
            (
                f"solute = {inp(moles)} mol",
                f"solvent mass = {inp(solvent_kg)} kg",
            ),
            "Molality, b",
            "Molality formula",
            "b = moles of solute / kilograms of solvent",
            (f"b = {inp(moles)} / {inp(solvent_kg)}",),
            f"b = {value}",
            value,
        )
    if op == "mass_percent":
        solute = _value(intent, "solute_mass")
        solution = _value(intent, "solution_mass", positive=True)
        if solute < 0 or solute > solution:
            raise SolveServiceError("solute mass must be between zero and solution mass")
        result = solute / solution * 100
        value = f"{num(result)}%"
        return ChemistryResult(
            "Verified mass percent",
            (
                f"solute mass = {inp(solute)} g",
                f"solution mass = {inp(solution)} g",
            ),
            "Mass percent",
            "Mass-percent concentration",
            "mass % = (mass of solute / mass of solution) × 100",
            (f"mass % = ({inp(solute)} / {inp(solution)}) × 100",),
            f"Mass percent = {value}",
            value,
        )
    raise SolveServiceError(f"unsupported solution operation: {op}")


def solve_acid_base(intent: ChemistryIntent) -> ChemistryResult:
    op = intent.chemistry_op
    if op == "ph_from_h":
        concentration = _value(intent, "h", positive=True)
        ph = -math.log10(concentration)
        value = num(ph)
        return ChemistryResult(
            "Verified pH calculation",
            (f"[H+] = {inp(concentration)} mol/L",),
            "pH",
            "Definition of pH",
            "pH = −log10[H+]",
            (f"pH = −log10({inp(concentration)})",),
            f"pH = {value}",
            value,
        )
    if op == "ph_from_poh":
        poh = _value(intent, "poh")
        ph = 14 - poh
        value = num(ph)
        return ChemistryResult(
            "Verified pH calculation",
            (f"pOH = {inp(poh)}", "pKw = 14 at 25 °C"),
            "pH",
            "Water ion-product relation",
            "pH + pOH = 14",
            (f"pH = 14 − {inp(poh)}",),
            f"pH = {value}",
            value,
        )
    if op == "h_from_ph":
        ph = _value(intent, "ph")
        concentration = 10 ** (-ph)
        value = f"{num(concentration)} mol/L"
        return ChemistryResult(
            "Verified pH calculation",
            (f"pH = {inp(ph)}",),
            "[H+]",
            "Inverse pH relation",
            "[H+] = 10^(-pH)",
            (f"[H+] = 10^(-{inp(ph)})",),
            f"[H+] = {value}",
            value,
        )
    if op == "poh_from_oh":
        concentration = _value(intent, "oh", positive=True)
        poh = -math.log10(concentration)
        value = num(poh)
        return ChemistryResult(
            "Verified pOH calculation",
            (f"[OH-] = {inp(concentration)} mol/L",),
            "pOH",
            "Definition of pOH",
            "pOH = −log10[OH-]",
            (f"pOH = −log10({inp(concentration)})",),
            f"pOH = {value}",
            value,
        )
    if op == "buffer_ph":
        pka = _value(intent, "pka")
        base = _value(intent, "base", positive=True)
        acid = _value(intent, "acid", positive=True)
        ph = pka + math.log10(base / acid)
        value = num(ph)
        return ChemistryResult(
            "Verified buffer pH",
            (
                f"pKa = {inp(pka)}",
                f"[A-] = {inp(base)} mol/L",
                f"[HA] = {inp(acid)} mol/L",
            ),
            "Buffer pH",
            "Henderson–Hasselbalch equation",
            "pH = pKa + log10([A-]/[HA])",
            (f"pH = {inp(pka)} + log10({inp(base)}/{inp(acid)})",),
            f"pH = {value}",
            value,
        )
    raise SolveServiceError(f"unsupported acid-base operation: {op}")


def solve_gas(intent: ChemistryIntent) -> ChemistryResult:
    values = {
        name: intent.params.get(name) for name in ("pressure", "volume", "moles", "temperature")
    }
    missing = [name for name, value in values.items() if value is None]
    if len(missing) != 1:
        raise SolveServiceError("exactly one gas-law variable must be unknown")
    for name, value in values.items():
        if value is not None and value <= 0:
            raise SolveServiceError(f"{name} must be positive")
    unknown = missing[0]
    p = values["pressure"]
    v = values["volume"]
    n = values["moles"]
    t = values["temperature"]
    if unknown == "pressure":
        v = _value(intent, "volume", positive=True)
        n = _value(intent, "moles", positive=True)
        t = _value(intent, "temperature", positive=True)
        result = n * GAS_R * t / v
        symbol, unit, rearranged = "P", "atm", "P = nRT / V"
        substitution = f"P = ({inp(n)})({const(GAS_R)})({inp(t)}) / {inp(v)}"
    elif unknown == "volume":
        p = _value(intent, "pressure", positive=True)
        n = _value(intent, "moles", positive=True)
        t = _value(intent, "temperature", positive=True)
        result = n * GAS_R * t / p
        symbol, unit, rearranged = "V", "L", "V = nRT / P"
        substitution = f"V = ({inp(n)})({const(GAS_R)})({inp(t)}) / {inp(p)}"
    elif unknown == "moles":
        p = _value(intent, "pressure", positive=True)
        v = _value(intent, "volume", positive=True)
        t = _value(intent, "temperature", positive=True)
        result = p * v / (GAS_R * t)
        symbol, unit, rearranged = "n", "mol", "n = PV / RT"
        substitution = f"n = ({inp(p)})({inp(v)}) / [({const(GAS_R)})({inp(t)})]"
    else:
        p = _value(intent, "pressure", positive=True)
        v = _value(intent, "volume", positive=True)
        n = _value(intent, "moles", positive=True)
        result = p * v / (n * GAS_R)
        symbol, unit, rearranged = "T", "K", "T = PV / nR"
        substitution = f"T = ({inp(p)})({inp(v)}) / [({inp(n)})({const(GAS_R)})]"
    given_labels = {"pressure": "P", "volume": "V", "moles": "n", "temperature": "T"}
    given_units = {"pressure": "atm", "volume": "L", "moles": "mol", "temperature": "K"}
    given = tuple(
        f"{given_labels[name]} = {inp(value)} {given_units[name]}"
        for name, value in values.items()
        if value is not None
    )
    value_text = f"{num(result)} {unit}"
    return ChemistryResult(
        "Verified gas law",
        given,
        f"{symbol} ({unknown})",
        "Ideal gas law",
        "PV = nRT",
        (rearranged, substitution),
        f"{symbol} = {value_text}",
        value_text,
    )


def solve_beer_lambert(intent: ChemistryIntent) -> ChemistryResult:
    epsilon = intent.params.get("epsilon")
    path = intent.params.get("path")
    concentration = intent.params.get("concentration")
    absorbance = intent.params.get("absorbance")
    missing = [
        name
        for name, value in (
            ("epsilon", epsilon),
            ("path", path),
            ("concentration", concentration),
            ("absorbance", absorbance),
        )
        if value is None
    ]
    if len(missing) != 1:
        raise SolveServiceError("exactly one Beer–Lambert variable must be unknown")
    known = [value for value in (epsilon, path, concentration, absorbance) if value is not None]
    if any(value < 0 for value in known) or any(
        value == 0 for value in (epsilon, path, concentration) if value is not None
    ):
        raise SolveServiceError("Beer–Lambert inputs must be physically valid")
    unknown = missing[0]
    if unknown == "absorbance":
        epsilon = _value(intent, "epsilon", positive=True)
        path = _value(intent, "path", positive=True)
        concentration = _value(intent, "concentration", positive=True)
        result = epsilon * path * concentration
        answer, unit = "A", ""
        rearranged = "A = εbc"
        substitution = f"A = ({inp(epsilon)})({inp(path)})({inp(concentration)})"
    elif unknown == "concentration":
        absorbance = _value(intent, "absorbance")
        epsilon = _value(intent, "epsilon", positive=True)
        path = _value(intent, "path", positive=True)
        result = absorbance / (epsilon * path)
        answer, unit = "c", "mol/L"
        rearranged = "c = A / (εb)"
        substitution = f"c = {inp(absorbance)} / [({inp(epsilon)})({inp(path)})]"
    elif unknown == "epsilon":
        absorbance = _value(intent, "absorbance")
        path = _value(intent, "path", positive=True)
        concentration = _value(intent, "concentration", positive=True)
        result = absorbance / (path * concentration)
        answer, unit = "ε", "L/(mol·cm)"
        rearranged = "ε = A / (bc)"
        substitution = f"ε = {inp(absorbance)} / [({inp(path)})({inp(concentration)})]"
    else:
        absorbance = _value(intent, "absorbance")
        epsilon = _value(intent, "epsilon", positive=True)
        concentration = _value(intent, "concentration", positive=True)
        result = absorbance / (epsilon * concentration)
        answer, unit = "b", "cm"
        rearranged = "b = A / (εc)"
        substitution = f"b = {inp(absorbance)} / [({inp(epsilon)})({inp(concentration)})]"
    value = f"{num(result)}{f' {unit}' if unit else ''}"
    given_names = {
        "epsilon": "ε = {} L/(mol·cm)",
        "path": "b = {} cm",
        "concentration": "c = {} mol/L",
        "absorbance": "A = {}",
    }
    given = tuple(given_names[key].format(inp(val)) for key, val in intent.params.items())
    return ChemistryResult(
        "Verified Beer–Lambert calculation",
        given,
        answer,
        "Beer–Lambert law",
        "A = εbc",
        (rearranged, substitution),
        f"{answer} = {value}",
        value,
    )
