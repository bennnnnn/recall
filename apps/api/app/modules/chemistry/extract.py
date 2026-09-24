"""Conservative text-to-``ChemistryIntent`` extraction.

Each branch requires both a chemistry cue and the complete values needed by a
solver. Incomplete or ambiguous questions remain on the model path; verified
labels are never produced from guessed values.
"""

from __future__ import annotations

import re

from app.models.schemas.chemistry import ChemistryIntent, ChemistryOp
from app.modules.chemistry.equations import balance_equation
from app.modules.chemistry.request import CHEMICAL_FORMULA, EQUATION_RE

_N = r"-?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?"
_TIME_UNIT_PATTERN = r"(?:seconds?|minutes?|hours?|days?|years?|min|h|s)"
_TIME_UNITS: dict[str, tuple[str, float]] = {
    "s": ("s", 1),
    "second": ("s", 1),
    "seconds": ("s", 1),
    "min": ("min", 60),
    "minute": ("min", 60),
    "minutes": ("min", 60),
    "h": ("h", 3600),
    "hour": ("h", 3600),
    "hours": ("h", 3600),
    "day": ("days", 86400),
    "days": ("days", 86400),
    "year": ("years", 31557600),
    "years": ("years", 31557600),
}


def _search(pattern: str, text: str, flags: int = re.IGNORECASE) -> float | None:
    match = re.search(pattern, text, flags)
    return float(match.group(1)) if match else None


def _labeled_volume(text: str, label: str) -> tuple[float, str | None] | None:
    match = re.search(
        rf"\b{label}\s*=\s*({_N})(?:\s*(mL|L)\b)?",
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    matched_unit = match.group(2)
    unit = None if matched_unit is None else ("mL" if matched_unit.lower() == "ml" else "L")
    return float(match.group(1)), unit


def _amounts(text: str) -> dict[str, float]:
    return {
        match.group(2): float(match.group(1))
        for match in re.finditer(
            rf"({_N})\s*mol(?:e|es)?(?:\s+of)?\s+({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
            text,
            re.IGNORECASE,
        )
    }


def _target_product(text: str, equation: str) -> str | None:
    balanced = balance_equation(equation)
    if not balanced.balanced:
        return None
    outside = EQUATION_RE.sub(" ", text)
    mentioned = [
        product
        for product in balanced.products
        if re.search(
            rf"(?<![A-Za-z0-9]){re.escape(product)}(?![A-Za-z0-9])", outside, re.IGNORECASE
        )
    ]
    if len(mentioned) == 1:
        return mentioned[0]
    if len(balanced.products) == 1:
        return next(iter(balanced.products))
    return None


def _extract_equations(text: str) -> ChemistryIntent | None:
    match = EQUATION_RE.search(text)
    if match is None:
        return None
    equation = match.group(1).strip()
    if re.search(r"\b(?:balance|balanced|coefficient)\b", text, re.IGNORECASE):
        return ChemistryIntent(kind="equations", chemistry_op="balance", equation=equation)
    if re.search(r"\b(?:Kc|equilibrium constant|reaction quotient|Qc)\b", text, re.IGNORECASE):
        concentrations = {
            species: float(value)
            for species, value in re.findall(
                rf"\[({CHEMICAL_FORMULA})\]\s*=\s*({_N})\s*(?:M|mol/L)?",
                text,
                re.IGNORECASE,
            )
        }
        balanced = balance_equation(equation)
        required = set(balanced.reactants) | set(balanced.products) if balanced.balanced else set()
        if required and required <= concentrations.keys():
            op: ChemistryOp = (
                "reaction_quotient"
                if re.search(r"\b(?:reaction quotient|Qc)\b", text, re.IGNORECASE)
                else "equilibrium_constant"
            )
            return ChemistryIntent(
                kind="equilibrium", chemistry_op=op, equation=equation, species=concentrations
            )
    if re.search(
        r"\b(?:how much|how many|moles? of|limiting reagent|stoichiometr)\b", text, re.IGNORECASE
    ):
        amounts = _amounts(text)
        target = _target_product(text, equation)
        if target and "limiting" in text.lower() and len(amounts) >= 2:
            return ChemistryIntent(
                kind="stoichiometry",
                chemistry_op="limiting_reagent",
                equation=equation,
                target=target,
                species=amounts,
            )
        reactants = balance_equation(equation).reactants
        known = {formula: amount for formula, amount in amounts.items() if formula in reactants}
        if target and len(known) == 1:
            return ChemistryIntent(
                kind="stoichiometry",
                chemistry_op="stoichiometry",
                equation=equation,
                target=target,
                species=known,
            )
    return None


def _extract_amounts(text: str) -> ChemistryIntent | None:
    mass_formula = re.search(
        rf"(?:molar\s+mass|molecular\s+weight)\s+(?:of\s+)?({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    )
    if mass_formula:
        return ChemistryIntent(
            kind="amounts", chemistry_op="molar_mass", formula=mass_formula.group(1)
        )

    percent_composition = re.search(
        rf"percent(?:age)?\s+(?:composition|by mass)\s+(?:of\s+)?"
        rf"([A-Z][a-z]?)\s+(?:in|of)\s+({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    )
    if percent_composition:
        return ChemistryIntent(
            kind="amounts",
            chemistry_op="percent_composition",
            target=percent_composition.group(1).capitalize(),
            formula=percent_composition.group(2),
        )

    if re.search(r"\bpercent yield\b", text, re.IGNORECASE):
        actual = _search(rf"actual(?:\s+yield)?\s*(?:=|of)?\s*({_N})\s*g", text)
        theoretical = _search(rf"theoretical(?:\s+yield)?\s*(?:=|of)?\s*({_N})\s*g", text)
        if actual is not None and theoretical is not None:
            return ChemistryIntent(
                kind="amounts",
                chemistry_op="percent_yield",
                params={"actual": actual, "theoretical": theoretical},
            )

    mass_to_moles = re.search(
        rf"(?:how many|calculate|find|determine)?\s*(?:the\s+)?moles?\s+"
        rf"(?:are\s+)?(?:in|from|of)?\s*({_N})\s*g(?:rams?)?\s+(?:of\s+)?"
        rf"({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    )
    if mass_to_moles:
        return ChemistryIntent(
            kind="amounts",
            chemistry_op="mass_to_moles",
            params={"mass": float(mass_to_moles.group(1))},
            units={"mass": "g"},
            formula=mass_to_moles.group(2),
        )

    moles_to_mass = re.search(
        rf"(?:mass|grams?)\s+(?:of\s+)?({_N})\s*mol(?:e|es)?\s+(?:of\s+)?({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    )
    if moles_to_mass:
        return ChemistryIntent(
            kind="amounts",
            chemistry_op="moles_to_mass",
            params={"moles": float(moles_to_mass.group(1))},
            units={"moles": "mol"},
            formula=moles_to_mass.group(2),
        )

    moles_to_particles = re.search(
        rf"(?:how many|calculate|find)?\s*(?:molecules|particles|atoms|formula units)\s+"
        rf"(?:are\s+)?(?:in|from)?\s*({_N})\s*mol(?:e|es)?\s+(?:of\s+)?"
        rf"({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    )
    if moles_to_particles:
        return ChemistryIntent(
            kind="amounts",
            chemistry_op="moles_to_particles",
            params={"moles": float(moles_to_particles.group(1))},
            formula=moles_to_particles.group(2),
        )

    particles_to_moles = re.search(
        rf"(?:how many|calculate|find)?\s*moles?\s+(?:are\s+)?(?:in|from)?\s*"
        rf"({_N})\s*(?:molecules|particles|atoms|formula units)\s+(?:of\s+)?"
        rf"({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    )
    if particles_to_moles:
        return ChemistryIntent(
            kind="amounts",
            chemistry_op="particles_to_moles",
            params={"particles": float(particles_to_moles.group(1))},
            formula=particles_to_moles.group(2),
        )
    return None


def _extract_acid_base(text: str) -> ChemistryIntent | None:
    h = _search(rf"\[H\+?\]\s*=\s*({_N})", text, flags=0)
    if h is not None and re.search(r"\bpH\b", text):
        return ChemistryIntent(kind="acid_base", chemistry_op="ph_from_h", params={"h": h})
    oh = _search(rf"\[OH-?\]\s*=\s*({_N})", text, flags=0)
    if oh is not None and re.search(r"\bpOH\b", text):
        return ChemistryIntent(kind="acid_base", chemistry_op="poh_from_oh", params={"oh": oh})
    poh = _search(rf"\bpOH\s*=\s*({_N})", text)
    if poh is not None and re.search(r"\bpH\b", text):
        return ChemistryIntent(kind="acid_base", chemistry_op="ph_from_poh", params={"poh": poh})
    ph = _search(rf"\bpH\s*=\s*({_N})", text)
    if ph is not None and re.search(r"\[H\+?\]|hydrogen ion", text, re.IGNORECASE):
        return ChemistryIntent(kind="acid_base", chemistry_op="h_from_ph", params={"ph": ph})
    if re.search(r"\b(?:buffer|Henderson)\b", text, re.IGNORECASE):
        pka = _search(rf"\bpK(?:a|ₐ)\s*=\s*({_N})", text)
        base = _search(rf"\[(?:A-|A⁻|base)\]\s*=\s*({_N})", text)
        acid = _search(rf"\[(?:HA|acid)\]\s*=\s*({_N})", text)
        if pka is not None and base is not None and acid is not None:
            return ChemistryIntent(
                kind="acid_base",
                chemistry_op="buffer_ph",
                params={"pka": pka, "base": base, "acid": acid},
            )
    return None


def _extract_solutions(text: str) -> ChemistryIntent | None:
    if re.search(r"\b(?:dilut|M1V1)\w*", text, re.IGNORECASE):
        m1 = _search(rf"\bM1\s*=\s*({_N})", text)
        m2 = _search(rf"\bM2\s*=\s*({_N})", text)
        v1 = _labeled_volume(text, "V1")
        v2 = _labeled_volume(text, "V2")
        if m1 is not None and v1 is not None and ((m2 is None) != (v2 is None)):
            v1_unit = v1[1] or (v2[1] if v2 is not None else None) or "L"
            params = {"m1": m1, "v1": v1[0]}
            units = {"v1": v1_unit}
            if m2 is not None:
                params["m2"] = m2
            if v2 is not None:
                params["v2"] = v2[0]
                units["v2"] = v2[1] or v1_unit
            return ChemistryIntent(
                kind="solutions",
                chemistry_op="dilution",
                params=params,
                units=units,
            )
    if re.search(r"\bmolality\b", text, re.IGNORECASE):
        moles = _search(rf"({_N})\s*mol(?:e|es)?(?:\s+of\s+solute)?", text)
        solvent = _search(rf"({_N})\s*kg(?:\s+of\s+solvent)?", text)
        if moles is not None and solvent is not None:
            return ChemistryIntent(
                kind="solutions",
                chemistry_op="molality",
                params={"moles": moles, "solvent_kg": solvent},
            )
    if re.search(r"\bmass percent\b|%\s*(?:by mass|w/w)", text, re.IGNORECASE):
        solute = _search(rf"({_N})\s*g(?:rams?)?\s+(?:of\s+)?solute", text)
        solution = _search(rf"({_N})\s*g(?:rams?)?\s+(?:of\s+)?solution", text)
        if solute is not None and solution is not None:
            return ChemistryIntent(
                kind="solutions",
                chemistry_op="mass_percent",
                params={"solute_mass": solute, "solution_mass": solution},
            )
    if re.search(r"\bmolarity\b|\bconcentration\s+of\s+(?:the\s+)?solution", text, re.IGNORECASE):
        moles = _search(rf"({_N})\s*mol(?:e|es)?", text)
        volume = _search(rf"({_N})\s*(?:L|liters?|litres?)\b", text)
        if moles is not None and volume is not None:
            return ChemistryIntent(
                kind="solutions",
                chemistry_op="molarity",
                params={"moles": moles, "volume_l": volume},
            )
    return None


def _extract_gas(text: str) -> ChemistryIntent | None:
    if not re.search(r"\b(?:PV\s*=\s*nRT|ideal gas|gas law)\b", text, re.IGNORECASE):
        return None
    values = {
        "pressure": _search(rf"({_N})\s*atm\b", text),
        "volume": _search(rf"({_N})\s*(?:L|liters?|litres?)\b", text),
        "moles": _search(rf"({_N})\s*mol(?:e|es)?\b", text),
        "temperature": _search(rf"({_N})\s*K\b", text, flags=0),
    }
    if sum(value is None for value in values.values()) != 1:
        return None
    return ChemistryIntent(
        kind="gases",
        chemistry_op="ideal_gas",
        params={key: value for key, value in values.items() if value is not None},
    )


def _extract_thermo(text: str) -> ChemistryIntent | None:
    if re.search(
        r"\b(?:specific heat|q\s*=\s*mc|heat transferred|calorimetr)\b", text, re.IGNORECASE
    ):
        mass = _search(rf"(?:mass|m)\s*(?:=|of)?\s*({_N})\s*g\b", text)
        specific = _search(rf"(?:specific heat|c)\s*(?:=|of)?\s*({_N})\s*J\s*/?\s*\(?g", text)
        delta_t = _search(
            rf"(?:ΔT|delta\s*T|temperature change)\s*(?:=|of)?\s*({_N})\s*(?:°?C|K)", text
        )
        if mass is not None and specific is not None and delta_t is not None:
            return ChemistryIntent(
                kind="thermochemistry",
                chemistry_op="heat",
                params={"mass": mass, "specific_heat": specific, "delta_t": delta_t},
            )
    if re.search(r"\b(?:Gibbs|\u0394G|delta\s*G)\b", text, re.IGNORECASE):
        delta_h = _search(rf"(?:ΔH|delta\s*H)\s*=\s*({_N})\s*kJ", text)
        delta_s = _search(rf"(?:ΔS|delta\s*S)\s*=\s*({_N})\s*(k?J)", text)
        entropy_unit = re.search(r"(?:ΔS|delta\s*S)\s*=\s*" + _N + r"\s*(k?J)", text, re.IGNORECASE)
        temperature = _search(rf"(?:\bT|temperature)\s*(?:=|of)?\s*({_N})\s*K\b", text)
        if delta_h is not None and delta_s is not None and temperature is not None:
            if entropy_unit and entropy_unit.group(1).lower() == "j":
                delta_s /= 1000
            return ChemistryIntent(
                kind="thermochemistry",
                chemistry_op="gibbs",
                params={"delta_h": delta_h, "delta_s": delta_s, "temperature": temperature},
            )
    return None


def _extract_kinetics(text: str) -> ChemistryIntent | None:
    if re.search(r"\bfirst[- ]order\b", text, re.IGNORECASE) and re.search(
        r"half[- ]life", text, re.IGNORECASE
    ):
        rate = _search(rf"\bk\s*=\s*({_N})\s*(?:s\^-?1|s⁻¹|/s)?", text)
        if rate is not None:
            return ChemistryIntent(
                kind="kinetics",
                chemistry_op="first_order_half_life",
                params={"rate_constant": rate},
                units={"rate_constant_time": "s"},
            )
    if re.search(r"\bfirst[- ]order\b", text, re.IGNORECASE):
        initial = _search(rf"\[A\](?:0|₀)\s*=\s*({_N})", text, flags=0)
        rate = _search(rf"\bk\s*=\s*({_N})", text)
        time = _search(rf"\bt\s*=\s*({_N})\s*s\b", text)
        if initial is not None and rate is not None and time is not None:
            return ChemistryIntent(
                kind="kinetics",
                chemistry_op="first_order_concentration",
                params={"initial": initial, "rate_constant": rate, "time": time},
            )
    if re.search(r"\bArrhenius\b", text, re.IGNORECASE):
        factor = _search(rf"\bA\s*=\s*({_N})", text, flags=0)
        energy = _search(rf"(?:Ea|Eₐ|activation energy)\s*(?:=|of)?\s*({_N})\s*(k?J)", text)
        energy_unit = re.search(
            r"(?:Ea|Eₐ|activation energy)\s*(?:=|of)?\s*" + _N + r"\s*(k?J)", text, re.IGNORECASE
        )
        temperature = _search(rf"(?:\bT|temperature)\s*(?:=|of)?\s*({_N})\s*K", text)
        if factor is not None and energy is not None and temperature is not None:
            if energy_unit and energy_unit.group(1).lower() == "kj":
                energy *= 1000
            return ChemistryIntent(
                kind="kinetics",
                chemistry_op="arrhenius",
                params={
                    "pre_exponential": factor,
                    "activation_energy": energy,
                    "temperature": temperature,
                },
            )
    return None


def _extract_electrochem(text: str) -> ChemistryIntent | None:
    if re.search(r"\bNernst\b", text, re.IGNORECASE):
        standard = _search(rf"E(?:°|0)\s*=\s*({_N})\s*V", text)
        electrons = _search(rf"\bn\s*=\s*({_N})", text)
        quotient = _search(rf"\bQ\s*=\s*({_N})", text, flags=0)
        temperature = _search(rf"\bT\s*=\s*({_N})\s*K", text, flags=0)
        if temperature is None:
            temperature = 298.15
        if standard is not None and electrons is not None and quotient is not None:
            return ChemistryIntent(
                kind="electrochemistry",
                chemistry_op="nernst",
                params={
                    "standard_potential": standard,
                    "electrons": electrons,
                    "quotient": quotient,
                    "temperature": temperature,
                },
            )
    if re.search(r"\b(?:ΔG|Gibbs)\b", text, re.IGNORECASE) and re.search(
        r"\b(?:cell|electrochem|E°)\b", text, re.IGNORECASE
    ):
        electrons = _search(rf"\bn\s*=\s*({_N})", text)
        potential = _search(rf"E(?:cell)?(?:°|0)?\s*=\s*({_N})\s*V", text)
        if electrons is not None and potential is not None:
            return ChemistryIntent(
                kind="electrochemistry",
                chemistry_op="cell_gibbs",
                params={"electrons": electrons, "potential": potential},
            )
    if re.search(r"\b(?:electrolysis|deposited|Faraday's law)\b", text, re.IGNORECASE):
        molar = _search(rf"(?:molar mass|\bM)\s*=\s*({_N})\s*g/mol", text)
        current = _search(rf"(?:current|\bI)\s*(?:=|of)?\s*({_N})\s*A", text)
        time = _search(rf"(?:time|\bt)\s*(?:=|of)?\s*({_N})\s*s", text)
        electrons = _search(rf"\bn\s*=\s*({_N})", text)
        if molar is not None and current is not None and time is not None and electrons is not None:
            return ChemistryIntent(
                kind="electrochemistry",
                chemistry_op="electrolysis_mass",
                params={
                    "molar_mass": molar,
                    "current": current,
                    "time": time,
                    "electrons": electrons,
                },
            )
    return None


def _extract_nuclear(text: str) -> ChemistryIntent | None:
    if not re.search(r"\b(?:radioactive|nuclear|half[- ]life|decay)\b", text, re.IGNORECASE):
        return None
    initial_match = re.search(
        rf"(?:initial(?: amount| mass)?|N0|N₀)\s*(?:=|of)?\s*({_N})\s*(g|mg|kg|mol|atoms?)?",
        text,
        re.IGNORECASE,
    )
    elapsed_match = re.search(
        rf"(?:elapsed(?: time)?|after|\bt\s*=)\s*({_N})\s*({_TIME_UNIT_PATTERN})\b",
        text,
        re.IGNORECASE,
    )
    half_match = re.search(
        rf"half[- ]life\s*(?:=|of|is)?\s*({_N})\s*({_TIME_UNIT_PATTERN})\b",
        text,
        re.IGNORECASE,
    )
    if not initial_match or not elapsed_match or not half_match:
        return None
    elapsed_unit, elapsed_scale = _TIME_UNITS[elapsed_match.group(2).lower()]
    _half_unit, half_scale = _TIME_UNITS[half_match.group(2).lower()]
    half_life = float(half_match.group(1)) * half_scale / elapsed_scale
    return ChemistryIntent(
        kind="nuclear",
        chemistry_op="radioactive_decay",
        params={
            "initial": float(initial_match.group(1)),
            "elapsed": float(elapsed_match.group(1)),
            "half_life": half_life,
        },
        units={"initial": initial_match.group(2) or "", "time": elapsed_unit},
    )


def _extract_spectroscopy(text: str) -> ChemistryIntent | None:
    if not re.search(r"\b(?:Beer[- ]Lambert|absorbance)\b", text, re.IGNORECASE):
        return None
    absorbance = _search(rf"(?:absorbance|\bA)\s*=\s*({_N})", text)
    epsilon = _search(rf"(?:ε|epsilon|molar absorptivity)\s*=\s*({_N})", text)
    path = _search(rf"(?:path length|\bb)\s*=\s*({_N})\s*cm", text)
    concentration = _search(rf"(?:concentration|\bc)\s*=\s*({_N})\s*(?:M|mol/L)", text)
    values = {
        "absorbance": absorbance,
        "epsilon": epsilon,
        "path": path,
        "concentration": concentration,
    }
    if sum(value is None for value in values.values()) != 1:
        return None
    if values["absorbance"] is None or values["concentration"] is None:
        return ChemistryIntent(
            kind="spectroscopy",
            chemistry_op="beer_lambert",
            params={key: value for key, value in values.items() if value is not None},
        )
    return None


EXTRACTORS = (
    _extract_equations,
    _extract_acid_base,
    _extract_thermo,
    _extract_kinetics,
    _extract_electrochem,
    _extract_nuclear,
    _extract_spectroscopy,
    _extract_solutions,
    _extract_gas,
    _extract_amounts,
)


def extract_chemistry_intent(text: str) -> ChemistryIntent | None:
    """Return the first complete supported calculation, otherwise ``None``."""
    if not text.strip() or len(text) > 4000:
        return None
    for extractor in EXTRACTORS:
        intent = extractor(text)
        if intent is not None:
            return intent
    return None
