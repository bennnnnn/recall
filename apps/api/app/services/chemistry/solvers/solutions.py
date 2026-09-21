# ruff: noqa: RUF001, RUF002 -- textbook formulas use Unicode charge and minus notation.
"""Solution, acid–base, gas, and analytical chemistry calculations."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.services.chemistry.solvers.types import ChemistryResult, format_number
from app.services.solving import MathServiceError

GAS_R = 0.082057366080960  # L·atm·mol⁻¹·K⁻¹


def _value(intent: ChemistryIntent, key: str, *, positive: bool = False) -> float:
    try:
        value = intent.params[key]
    except KeyError as exc:
        raise MathServiceError(f"missing chemistry parameter: {key}") from exc
    if positive and value <= 0:
        raise MathServiceError(f"{key} must be positive")
    return value


def solve_solution(intent: ChemistryIntent) -> ChemistryResult:
    op = intent.chemistry_op
    if op == "molarity":
        moles = _value(intent, "moles")
        volume = _value(intent, "volume_l", positive=True)
        molarity = moles / volume
        value = f"{format_number(molarity)} mol/L"
        return ChemistryResult(
            "Verified molarity",
            (f"n = {format_number(moles)} mol", f"V = {format_number(volume)} L"),
            "Molarity, c",
            "Molar concentration",
            "c = n / V",
            (f"c = {format_number(moles)} / {format_number(volume)}",),
            f"c = {value}",
            value,
        )
    if op == "dilution":
        m1 = _value(intent, "m1", positive=True)
        v1 = _value(intent, "v1", positive=True)
        m2 = intent.params.get("m2")
        v2 = intent.params.get("v2")
        unit = intent.units.get("v1", intent.units.get("v2", "L"))
        if (m2 is None) == (v2 is None):
            raise MathServiceError("exactly one of M2 or V2 must be unknown")
        if v2 is None:
            if m2 is None or m2 <= 0:
                raise MathServiceError("M2 must be positive")
            result = m1 * v1 / m2
            value = f"{format_number(result)} {unit}"
            find = "Final volume, V2"
            substitution = f"V2 = ({format_number(m1)})({format_number(v1)}) / {format_number(m2)}"
            answer = f"V2 = {value}"
            given = (
                f"M1 = {format_number(m1)} mol/L",
                f"V1 = {format_number(v1)} {unit}",
                f"M2 = {format_number(m2)} mol/L",
            )
        else:
            if v2 <= 0:
                raise MathServiceError("V2 must be positive")
            result = m1 * v1 / v2
            value = f"{format_number(result)} mol/L"
            find = "Final concentration, M2"
            substitution = f"M2 = ({format_number(m1)})({format_number(v1)}) / {format_number(v2)}"
            answer = f"M2 = {value}"
            given = (
                f"M1 = {format_number(m1)} mol/L",
                f"V1 = {format_number(v1)} {unit}",
                f"V2 = {format_number(v2)} {unit}",
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
        value = f"{format_number(result)} mol/kg"
        return ChemistryResult(
            "Verified molality",
            (
                f"solute = {format_number(moles)} mol",
                f"solvent mass = {format_number(solvent_kg)} kg",
            ),
            "Molality, b",
            "Molality formula",
            "b = moles of solute / kilograms of solvent",
            (f"b = {format_number(moles)} / {format_number(solvent_kg)}",),
            f"b = {value}",
            value,
        )
    if op == "mass_percent":
        solute = _value(intent, "solute_mass")
        solution = _value(intent, "solution_mass", positive=True)
        if solute < 0 or solute > solution:
            raise MathServiceError("solute mass must be between zero and solution mass")
        result = solute / solution * 100
        value = f"{format_number(result)}%"
        return ChemistryResult(
            "Verified mass percent",
            (
                f"solute mass = {format_number(solute)} g",
                f"solution mass = {format_number(solution)} g",
            ),
            "Mass percent",
            "Mass-percent concentration",
            "mass % = (mass of solute / mass of solution) × 100",
            (f"mass % = ({format_number(solute)} / {format_number(solution)}) × 100",),
            f"Mass percent = {value}",
            value,
        )
    raise MathServiceError(f"unsupported solution operation: {op}")


def solve_acid_base(intent: ChemistryIntent) -> ChemistryResult:
    op = intent.chemistry_op
    if op == "ph_from_h":
        concentration = _value(intent, "h", positive=True)
        ph = -math.log10(concentration)
        value = format_number(ph)
        return ChemistryResult(
            "Verified pH calculation",
            (f"[H⁺] = {format_number(concentration)} mol/L",),
            "pH",
            "Definition of pH",
            "pH = −log₁₀[H⁺]",
            (f"pH = −log₁₀({format_number(concentration)})",),
            f"pH = {value}",
            value,
        )
    if op == "ph_from_poh":
        poh = _value(intent, "poh")
        ph = 14 - poh
        value = format_number(ph)
        return ChemistryResult(
            "Verified pH calculation",
            (f"pOH = {format_number(poh)}", "pKᴡ = 14 at 25 °C"),
            "pH",
            "Water ion-product relation",
            "pH + pOH = 14",
            (f"pH = 14 − {format_number(poh)}",),
            f"pH = {value}",
            value,
        )
    if op == "h_from_ph":
        ph = _value(intent, "ph")
        concentration = 10 ** (-ph)
        value = f"{format_number(concentration)} mol/L"
        return ChemistryResult(
            "Verified pH calculation",
            (f"pH = {format_number(ph)}",),
            "[H⁺]",
            "Inverse pH relation",
            "[H⁺] = 10⁻ᵖᴴ",
            (f"[H⁺] = 10^(−{format_number(ph)})",),
            f"[H⁺] = {value}",
            value,
        )
    if op == "poh_from_oh":
        concentration = _value(intent, "oh", positive=True)
        poh = -math.log10(concentration)
        value = format_number(poh)
        return ChemistryResult(
            "Verified pOH calculation",
            (f"[OH⁻] = {format_number(concentration)} mol/L",),
            "pOH",
            "Definition of pOH",
            "pOH = −log₁₀[OH⁻]",
            (f"pOH = −log₁₀({format_number(concentration)})",),
            f"pOH = {value}",
            value,
        )
    if op == "buffer_ph":
        pka = _value(intent, "pka")
        base = _value(intent, "base", positive=True)
        acid = _value(intent, "acid", positive=True)
        ph = pka + math.log10(base / acid)
        value = format_number(ph)
        return ChemistryResult(
            "Verified buffer pH",
            (
                f"pKₐ = {format_number(pka)}",
                f"[A⁻] = {format_number(base)} mol/L",
                f"[HA] = {format_number(acid)} mol/L",
            ),
            "Buffer pH",
            "Henderson–Hasselbalch equation",
            "pH = pKₐ + log₁₀([A⁻]/[HA])",
            (f"pH = {format_number(pka)} + log₁₀({format_number(base)}/{format_number(acid)})",),
            f"pH = {value}",
            value,
        )
    raise MathServiceError(f"unsupported acid-base operation: {op}")


def solve_gas(intent: ChemistryIntent) -> ChemistryResult:
    values = {
        name: intent.params.get(name) for name in ("pressure", "volume", "moles", "temperature")
    }
    missing = [name for name, value in values.items() if value is None]
    if len(missing) != 1:
        raise MathServiceError("exactly one gas-law variable must be unknown")
    for name, value in values.items():
        if value is not None and value <= 0:
            raise MathServiceError(f"{name} must be positive")
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
        substitution = (
            f"P = ({format_number(n)})({format_number(GAS_R)})"
            f"({format_number(t)}) / {format_number(v)}"
        )
    elif unknown == "volume":
        p = _value(intent, "pressure", positive=True)
        n = _value(intent, "moles", positive=True)
        t = _value(intent, "temperature", positive=True)
        result = n * GAS_R * t / p
        symbol, unit, rearranged = "V", "L", "V = nRT / P"
        substitution = (
            f"V = ({format_number(n)})({format_number(GAS_R)})"
            f"({format_number(t)}) / {format_number(p)}"
        )
    elif unknown == "moles":
        p = _value(intent, "pressure", positive=True)
        v = _value(intent, "volume", positive=True)
        t = _value(intent, "temperature", positive=True)
        result = p * v / (GAS_R * t)
        symbol, unit, rearranged = "n", "mol", "n = PV / RT"
        substitution = (
            f"n = ({format_number(p)})({format_number(v)}) / "
            f"[({format_number(GAS_R)})({format_number(t)})]"
        )
    else:
        p = _value(intent, "pressure", positive=True)
        v = _value(intent, "volume", positive=True)
        n = _value(intent, "moles", positive=True)
        result = p * v / (n * GAS_R)
        symbol, unit, rearranged = "T", "K", "T = PV / nR"
        substitution = (
            f"T = ({format_number(p)})({format_number(v)}) / "
            f"[({format_number(n)})({format_number(GAS_R)})]"
        )
    given_labels = {"pressure": "P", "volume": "V", "moles": "n", "temperature": "T"}
    given_units = {"pressure": "atm", "volume": "L", "moles": "mol", "temperature": "K"}
    given = tuple(
        f"{given_labels[name]} = {format_number(value)} {given_units[name]}"
        for name, value in values.items()
        if value is not None
    )
    value_text = f"{format_number(result)} {unit}"
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
        raise MathServiceError("exactly one Beer–Lambert variable must be unknown")
    known = [value for value in (epsilon, path, concentration, absorbance) if value is not None]
    if any(value < 0 for value in known) or any(
        value == 0 for value in (epsilon, path, concentration) if value is not None
    ):
        raise MathServiceError("Beer–Lambert inputs must be physically valid")
    unknown = missing[0]
    if unknown == "absorbance":
        epsilon = _value(intent, "epsilon", positive=True)
        path = _value(intent, "path", positive=True)
        concentration = _value(intent, "concentration", positive=True)
        result = epsilon * path * concentration
        answer, unit = "A", ""
        rearranged = "A = εbc"
        substitution = (
            f"A = ({format_number(epsilon)})({format_number(path)})({format_number(concentration)})"
        )
    elif unknown == "concentration":
        absorbance = _value(intent, "absorbance")
        epsilon = _value(intent, "epsilon", positive=True)
        path = _value(intent, "path", positive=True)
        result = absorbance / (epsilon * path)
        answer, unit = "c", "mol/L"
        rearranged = "c = A / (εb)"
        substitution = (
            f"c = {format_number(absorbance)} / [({format_number(epsilon)})({format_number(path)})]"
        )
    else:
        raise MathServiceError("this Beer–Lambert rearrangement is not exposed yet")
    value = f"{format_number(result)}{f' {unit}' if unit else ''}"
    given_names = {"epsilon": "ε", "path": "b", "concentration": "c", "absorbance": "A"}
    given = tuple(
        f"{given_names[key]} = {format_number(val)}" for key, val in intent.params.items()
    )
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
