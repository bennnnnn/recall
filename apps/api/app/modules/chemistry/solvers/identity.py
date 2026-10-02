# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Structure, organic facts, coordination names, colligative properties, and analysis."""

from __future__ import annotations

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.coordination import parse_complex_formula
from app.modules.chemistry.organic import group_pattern, isomer_relationship, organic_facts
from app.modules.chemistry.solvers.common_chem import const, inp, num, verified
from app.modules.chemistry.solvers.constants import GAS_R
from app.modules.chemistry.solvers.params import require
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
    shown = "\n".join(f"{element} = {_signed(states[element])}" for element in species.composition)
    terms = " + ".join(
        f"({_signed(states[element])})({count})" for element, count in species.composition.items()
    )
    return verified(
        "Verified oxidation states",
        (formula,),
        "Oxidation states",
        "School oxidation-number rules",
        "the signed oxidation numbers sum to the charge",
        (f"sum = {terms} = {species.charge}",),
        shown,
        shown,
    )


def solve_vsepr(intent: ChemistryIntent) -> ChemistryResult:
    formula = intent.formula or ""
    structure = lewis_structure(formula)
    if structure is None:
        raise SolveServiceError("no unique central-atom VSEPR structure")
    polarity = "polar" if structure.polar else "nonpolar"
    bonded = len(structure.terminal_elements)
    lone = structure.central_lone_pairs
    lines = [
        f"geometry: {structure.geometry}, {structure.bond_angle}",
        f"polarity: {polarity}",
        f"hybridization: {structure.hybridization}",
        f"central formal charge: {structure.central_formal_charge}",
    ]
    if (
        structure.electron_geometry != structure.geometry
        or structure.ideal_angle != structure.bond_angle
    ):
        lines.append(
            f"electron geometry: {structure.electron_geometry}, ideal angle {structure.ideal_angle}"
        )
    if structure.resonance_forms > 1:
        lines.append(f"resonance forms: {structure.resonance_forms}")
    shown = "\n".join(lines)
    return verified(
        "Verified VSEPR",
        (formula, f"valence electrons = {structure.electrons}"),
        "Geometry, polarity, and hybridization",
        "VSEPR from the central-atom Lewis structure",
        "steric number = bonded atoms + lone pairs",
        (
            f"central atom {structure.central}: {bonded} bonded atoms, {lone} lone pairs",
            f"steric number = {bonded} + {lone} = {bonded + lone}",
            f"electron geometry {structure.electron_geometry}; "
            f"molecular geometry {structure.geometry}",
        ),
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
        (
            f"valence electrons V = {inp(valence)}",
            f"nonbonding electrons N = {inp(nonbonding)}",
            f"bonding electrons B = {inp(bonding)}",
        ),
        "Formal charge",
        "Formal charge",
        "FC = V − N − B/2",
        (f"FC = {inp(valence)} − {inp(nonbonding)} − {inp(bonding)}/2",),
        shown,
        shown,
    )


def solve_functional_groups(intent: ChemistryIntent) -> ChemistryResult:
    facts = organic_facts(intent.formula or "")
    if facts is None or not facts.groups:
        raise SolveServiceError("no functional group recognized")
    shown = "\n".join(facts.groups)
    return verified(
        "Verified functional groups",
        (facts.canonical_smiles,),
        "Functional groups",
        "RDKit SMARTS groups",
        "each group is a SMARTS pattern matched atom by atom",
        tuple(f"{group}: {group_pattern(group)}" for group in facts.groups),
        shown,
        shown,
        verbatim=True,
    )


def solve_stereochemistry(intent: ChemistryIntent) -> ChemistryResult:
    facts = organic_facts(intent.formula or "")
    if facts is None:
        raise SolveServiceError("SMILES could not be read")
    parts = [*facts.chirality, *facts.double_bond_stereo]
    shown = "\n".join(parts) if parts else "no stereocenter"
    return verified(
        "Verified stereochemistry",
        (facts.canonical_smiles,),
        "CIP stereochemistry",
        "RDKit CIP labels",
        "R/S centers and E/Z double bonds",
        (
            f"{len(facts.chirality)} possible stereocenter(s) and "
            f"{len(facts.double_bond_stereo)} stereo double bond(s) in {facts.canonical_smiles}",
            "atoms are numbered from 1 in the order the SMILES is written",
        ),
        shown,
        shown,
        verbatim=True,
    )


def solve_isomers(intent: ChemistryIntent) -> ChemistryResult:
    left, right = intent.formula or "", intent.target or ""
    relationship = isomer_relationship(left, right)
    first, second = organic_facts(left), organic_facts(right)
    if relationship is None or first is None or second is None:
        raise SolveServiceError("both structures must be valid SMILES")
    return verified(
        "Verified isomer relationship",
        (left, right),
        "Isomer relationship",
        "Formula and canonical SMILES",
        "same formula, then isomeric versus non-isomeric SMILES",
        (
            f"formula: {first.formula} and {second.formula}",
            f"canonical SMILES: {first.canonical_smiles} and {second.canonical_smiles}",
        ),
        relationship,
        relationship,
        verbatim=True,
    )


def solve_coordination(intent: ChemistryIntent) -> ChemistryResult:
    complex_ = parse_complex_formula(intent.formula or "")
    if complex_ is None:
        raise SolveServiceError("coordination formula was not recognized")
    complex_charge = complex_.oxidation_state + complex_.ligand_charge
    shown = "\n".join(
        (
            f"name: {complex_.name}",
            f"{complex_.metal} oxidation state: {_signed(complex_.oxidation_state)}",
            f"coordination number: {complex_.coordination_number}",
        )
    )
    return verified(
        "Verified coordination complex",
        (intent.formula or "",),
        "Oxidation state, coordination number, and name",
        "Additive coordination name",
        "oxidation state = complex charge − ligand charges",
        (
            f"complex charge = {_signed(complex_charge)}",
            f"ligand charges = {_signed(complex_.ligand_charge)}",
            f"{complex_.metal} = ({_signed(complex_charge)}) − ({_signed(complex_.ligand_charge)})"
            f" = {_signed(complex_.oxidation_state)}",
            f"coordination number = donor atoms of {' + '.join(complex_.ligands)} = "
            f"{complex_.coordination_number}",
        ),
        shown,
        shown,
    )


def _colligative(
    intent: ChemistryIntent, constant_name: str, constant_label: str, symbol: str, title: str
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
        title.removeprefix("Verified ").capitalize(),
        f"{symbol} = i {constant_label} m",
        (f"{symbol} = ({inp(factor)})({inp(constant)})({inp(molality)})",),
        shown,
        shown,
    )


def solve_boiling(intent: ChemistryIntent) -> ChemistryResult:
    return _colligative(intent, "kb", "Kb", "ΔTb", "Verified boiling-point elevation")


def solve_freezing(intent: ChemistryIntent) -> ChemistryResult:
    return _colligative(intent, "kf", "Kf", "ΔTf", "Verified freezing-point depression")


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
        "van 't Hoff equation",
        "Π = iMRT",
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
        "Raoult's law",
        "P = X P°",
        (f"P = ({inp(fraction)})({inp(pure)})",),
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
        (f"slope = {inp(slope)}", f"intercept = {inp(intercept)}", f"signal = {inp(signal)}"),
        "Concentration",
        "Linear calibration",
        "c = (signal − intercept) / slope",
        (f"c = ({inp(signal)} − {inp(intercept)}) / {inp(slope)}",),
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
        (f"precipitate = {inp(mass)} g", f"factor = {inp(factor)}"),
        "Analyte mass",
        "Gravimetric factor",
        "mass = precipitate × factor",
        (f"mass = ({inp(mass)})({inp(factor)})",),
        shown,
        shown,
    )


def solve_standard_addition(intent: ChemistryIntent) -> ChemistryResult:
    message = "standard addition inputs are incomplete"
    sample = require(intent, "sample_signal", message=message)
    spiked = require(intent, "spiked_signal", message=message)
    standard = require(intent, "standard_concentration", message=message)
    standard_volume = require(intent, "standard_volume", message=message)
    sample_volume = require(intent, "sample_volume", positive=True, message=message)
    if spiked <= sample:
        raise SolveServiceError(message)
    value = (sample / (spiked - sample)) * standard * (standard_volume / sample_volume)
    shown = f"c = {num(value)}"
    return verified(
        "Verified standard addition",
        (
            f"Ix = {inp(sample)}",
            f"Ispike = {inp(spiked)}",
            f"Cstd = {inp(standard)}",
            f"Vstd = {inp(standard_volume)}",
            f"Vsample = {inp(sample_volume)}",
        ),
        "Sample concentration",
        "One-point standard addition",
        "C = (Ix / (Ispike − Ix)) × Cstd × Vstd / Vsample",
        (
            f"C = ({inp(sample)} / ({inp(spiked)} − {inp(sample)})) × {inp(standard)} × "
            f"{inp(standard_volume)} / {inp(sample_volume)}",
        ),
        shown,
        shown,
    )
