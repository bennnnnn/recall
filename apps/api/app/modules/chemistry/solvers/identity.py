# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Structure, organic facts, coordination names, colligative properties, and analysis."""

from __future__ import annotations

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.coordination import parse_coordination
from app.modules.chemistry.organic import isomer_relationship, organic_facts
from app.modules.chemistry.solvers.common_chem import num, verified
from app.modules.chemistry.solvers.solutions import GAS_R
from app.modules.chemistry.solvers.types import ChemistryResult
from app.modules.chemistry.species import parse_species
from app.modules.chemistry.structure import lewis_structure, oxidation_states
from app.services.solving import SolveServiceError


def _signed(value: int) -> str:
    if value > 0:
        return f"+{value}"
    return str(value)


def solve_oxidation_state(intent: ChemistryIntent) -> ChemistryResult:
    formula = intent.formula or ""
    states = oxidation_states(formula)
    species = parse_species(formula, coefficient_already_removed=True)
    if states is None or species is None:
        raise SolveServiceError("oxidation states are ambiguous")
    shown = ", ".join(f"{element} = {_signed(states[element])}" for element in species.composition)
    return verified(
        "Verified oxidation states",
        (formula,),
        "Oxidation states",
        "School oxidation-number rules",
        "the signed oxidation numbers sum to the charge",
        (shown,),
        shown,
        shown,
    )


def solve_vsepr(intent: ChemistryIntent) -> ChemistryResult:
    formula = intent.formula or ""
    structure = lewis_structure(formula)
    if structure is None:
        raise SolveServiceError("no unique central-atom VSEPR structure")
    polarity = "polar" if structure.polar else "nonpolar"
    shown = (
        f"{structure.geometry}, {structure.bond_angle}, {polarity}, "
        f"{structure.hybridization}, central formal charge {structure.central_formal_charge}"
    )
    if (
        structure.electron_geometry != structure.geometry
        or structure.ideal_angle != structure.bond_angle
    ):
        shown += (
            f"; electron geometry {structure.electron_geometry}, "
            f"ideal angle {structure.ideal_angle}"
        )
    if structure.resonance_forms > 1:
        shown += f"; {structure.resonance_forms} resonance forms"
    return verified(
        "Verified VSEPR",
        (formula, f"valence electrons = {structure.electrons}"),
        "Geometry, polarity, and hybridization",
        "VSEPR from the central-atom Lewis structure",
        "steric number = bonded atoms + lone pairs",
        (shown,),
        shown,
        shown,
    )


def solve_formal_charge(intent: ChemistryIntent) -> ChemistryResult:
    valence = intent.params.get("valence")
    nonbonding = intent.params.get("nonbonding")
    bonding = intent.params.get("bonding")
    if valence is None or nonbonding is None or bonding is None:
        raise SolveServiceError("formal charge needs valence, nonbonding, and bonding electrons")
    if bonding % 2:
        raise SolveServiceError("bonding electrons must be even")
    value = valence - nonbonding - bonding / 2
    shown = f"FC = {num(value)}"
    return verified(
        "Verified formal charge",
        (f"V = {num(valence)}", f"N = {num(nonbonding)}", f"B = {num(bonding)}"),
        "Formal charge",
        "Formal charge",
        "FC = V − N − B/2",
        (shown,),
        shown,
        shown,
    )


def solve_functional_groups(intent: ChemistryIntent) -> ChemistryResult:
    facts = organic_facts(intent.formula or "")
    if facts is None or not facts.groups:
        raise SolveServiceError("no functional group recognized")
    shown = ", ".join(facts.groups)
    return verified(
        "Verified functional groups",
        (facts.canonical_smiles,),
        "Functional groups",
        "RDKit SMARTS groups",
        "specific groups are matched before general ones",
        (shown,),
        shown,
        shown,
    )


def solve_stereochemistry(intent: ChemistryIntent) -> ChemistryResult:
    facts = organic_facts(intent.formula or "")
    if facts is None:
        raise SolveServiceError("SMILES could not be read")
    parts = [*facts.chirality, *facts.double_bond_stereo]
    shown = ", ".join(parts) if parts else "no stereocenter"
    return verified(
        "Verified stereochemistry",
        (facts.canonical_smiles,),
        "CIP stereochemistry",
        "RDKit CIP labels",
        "R/S centers and E/Z double bonds",
        (shown,),
        shown,
        shown,
    )


def solve_isomers(intent: ChemistryIntent) -> ChemistryResult:
    relationship = isomer_relationship(intent.formula or "", intent.target or "")
    if relationship is None:
        raise SolveServiceError("both structures must be valid SMILES")
    return verified(
        "Verified isomer relationship",
        (intent.formula or "", intent.target or ""),
        "Isomer relationship",
        "Formula and canonical SMILES",
        "same formula, then isomeric versus non-isomeric SMILES",
        (relationship,),
        relationship,
        relationship,
    )


def solve_coordination(intent: ChemistryIntent) -> ChemistryResult:
    complex_ = parse_coordination(intent.formula or "")
    if complex_ is None:
        raise SolveServiceError("coordination formula was not recognized")
    shown = (
        f"{complex_.metal} oxidation state {_signed(complex_.oxidation_state)}, "
        f"coordination number {complex_.coordination_number}, {complex_.name}"
    )
    return verified(
        "Verified coordination complex",
        (intent.formula or "",),
        "Oxidation state, coordination number, and name",
        "Additive coordination name",
        "oxidation state = complex charge − ligand charges",
        (shown,),
        shown,
        shown,
    )


def _colligative(
    intent: ChemistryIntent, constant_name: str, symbol: str, title: str
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
        (f"i = {num(factor)}", f"K = {num(constant)}", f"m = {num(molality)} mol/kg"),
        symbol,
        title.removeprefix("Verified "),
        f"{symbol} = i K m",
        (shown,),
        shown,
        shown,
    )


def solve_boiling(intent: ChemistryIntent) -> ChemistryResult:
    return _colligative(intent, "kb", "ΔTb", "Verified boiling-point elevation")


def solve_freezing(intent: ChemistryIntent) -> ChemistryResult:
    return _colligative(intent, "kf", "ΔTf", "Verified freezing-point depression")


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
        (f"i = {num(factor)}", f"M = {num(molarity)} mol/L", f"T = {num(temperature)} K"),
        "Osmotic pressure",
        "van 't Hoff equation",
        "Π = iMRT",
        (shown,),
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
        (f"X = {num(fraction)}", f"P° = {num(pure)}{suffix}"),
        "Vapor pressure",
        "Raoult's law",
        "P = X P°",
        (shown,),
        shown,
        shown,
    )


def solve_calibration(intent: ChemistryIntent) -> ChemistryResult:
    slope = intent.params.get("slope")
    intercept = intent.params.get("intercept")
    signal = intent.params.get("signal")
    if slope is None or intercept is None or signal is None or slope == 0:
        raise SolveServiceError("calibration needs a nonzero slope, intercept, and signal")
    value = (signal - intercept) / slope
    shown = f"c = {num(value)}"
    return verified(
        "Verified calibration",
        (f"slope = {num(slope)}", f"intercept = {num(intercept)}", f"signal = {num(signal)}"),
        "Concentration",
        "Linear calibration",
        "c = (signal − intercept) / slope",
        (shown,),
        shown,
        shown,
    )


def solve_gravimetric(intent: ChemistryIntent) -> ChemistryResult:
    mass = intent.params.get("precipitate_mass")
    factor = intent.params.get("factor")
    if mass is None or factor is None or mass < 0 or factor <= 0:
        raise SolveServiceError("gravimetric analysis needs a precipitate mass and a factor")
    shown = f"mass = {num(mass * factor)} g"
    return verified(
        "Verified gravimetric analysis",
        (f"precipitate = {num(mass)} g", f"factor = {num(factor)}"),
        "Analyte mass",
        "Gravimetric factor",
        "mass = precipitate × factor",
        (shown,),
        shown,
        shown,
    )


def solve_standard_addition(intent: ChemistryIntent) -> ChemistryResult:
    sample = intent.params.get("sample_signal")
    spiked = intent.params.get("spiked_signal")
    standard = intent.params.get("standard_concentration")
    standard_volume = intent.params.get("standard_volume")
    sample_volume = intent.params.get("sample_volume")
    if (
        None in {sample, spiked, standard, standard_volume, sample_volume}
        or spiked == sample
        or (sample_volume or 0) <= 0
    ):
        raise SolveServiceError("standard addition inputs are incomplete")
    value = (
        ((sample or 0) / ((spiked or 0) - (sample or 0)))
        * (standard or 0)
        * ((standard_volume or 0) / (sample_volume or 1))
    )
    shown = f"c = {num(value)}"
    return verified(
        "Verified standard addition",
        (
            f"Ix = {num(sample or 0)}",
            f"Ispike = {num(spiked or 0)}",
            f"Cstd = {num(standard or 0)}",
        ),
        "Sample concentration",
        "One-point standard addition",
        "C = (Ix / (Ispike − Ix)) × Cstd × Vstd / Vsample",
        (shown,),
        shown,
        shown,
    )
