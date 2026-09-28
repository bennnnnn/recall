"""Broad regression matrix for the typed chemistry pipeline."""

from __future__ import annotations

import math
from typing import get_args

import pytest
from pydantic import ValidationError

from app.models.schemas.chemistry import ChemistryIntent, ChemistryOp
from app.modules.chemistry.block import build_verified_chemistry
from app.modules.chemistry.direct import (
    format_direct_chemistry_reply,
    maybe_direct_chemistry_reply,
)
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.request import is_chemistry_question
from app.modules.chemistry.solvers import solve_chemistry
from app.modules.chemistry.solvers.types import format_number
from app.services.solving import MathServiceError

PIPELINE_CASES: list[tuple[str, ChemistryOp, str]] = [
    ("Balance H2 + O2 -> H2O", "balance", "2 H2 + O2 → 2 H2O"),
    ("What is the molar mass of H2O?", "molar_mass", "M(H2O) = 18.02 g/mol"),
    (
        "How many moles are in 36 g of H2O?",
        "mass_to_moles",
        "n(H2O) = 1.99778 mol",
    ),
    ("Find the mass of 2 mol of H2O", "moles_to_mass", "m(H2O) = 36.04 g"),
    (
        "How many molecules are in 2 mol of H2O?",
        "moles_to_particles",
        "N(H2O) = 1.2044 × 10^24 particles",
    ),
    (
        "How many moles are in 6.022e23 molecules of H2O?",
        "particles_to_moles",
        "n(H2O) = 0.999977 mol",
    ),
    (
        "Find percent composition of O in H2O",
        "percent_composition",
        "O in H2O = 88.7847%",
    ),
    (
        "Find percent yield if actual yield = 8 g and theoretical yield = 10 g",
        "percent_yield",
        "Percent yield = 80%",
    ),
    (
        "How many moles of H2O from 4 mol H2 in H2 + O2 -> H2O?",
        "stoichiometry",
        "n(H2O) = 4 mol H2O",
    ),
    (
        "Find the limiting reagent and moles of H2O from 4 mol H2 and 1 mol O2 in H2 + O2 -> H2O",
        "limiting_reagent",
        "Limiting reagent = O2; 2 mol H2O",
    ),
    (
        "Find molarity of 0.5 mol in 2 L solution",
        "molarity",
        "c = 0.25 mol/L",
    ),
    (
        "Dilution using M1V1: M1=2, V1=50 mL, M2=0.5, find V2",
        "dilution",
        "V2 = 200 mL",
    ),
    (
        "Find molality for 2 mol solute in 4 kg solvent",
        "molality",
        "b = 0.5 mol/kg",
    ),
    (
        "Find mass percent for 5 g solute in 20 g solution",
        "mass_percent",
        "Mass percent = 25%",
    ),
    ("Find pH when [H+] = 0.001", "ph_from_h", "pH = 3"),
    ("Find pH when pOH = 3", "ph_from_poh", "pH = 11"),
    ("Find [H+] when pH = 4", "h_from_ph", "[H⁺] = 1 × 10^-4 mol/L"),
    ("Find pOH when [OH-] = 0.01", "poh_from_oh", "pOH = 2"),
    (
        "Find buffer pH with pKa=4.76, [A-]=0.2 and [HA]=0.1",
        "buffer_ph",
        "pH = 5.06103",
    ),
    (
        "Use ideal gas law PV=nRT: P=2 atm, n=1 mol, T=300 K, find volume",
        "ideal_gas",
        "V = 12.3086 L",
    ),
    (
        "Find heat transferred using q=mcΔT: mass=10 g, specific heat=4.18 J/(g C), ΔT=5 C",
        "heat",
        "q = 209 J",
    ),
    (
        "Find Gibbs ΔG when ΔH=-40 kJ, ΔS=-100 J and T=300 K",
        "gibbs",
        "ΔG = -10 kJ/mol",
    ),
    (
        "Find Kc for H2 + I2 -> HI when [H2]=0.2 M, [I2]=0.2 M, [HI]=0.8 M",
        "equilibrium_constant",
        "Kc = 16",
    ),
    (
        "Find reaction quotient Qc for H2 + I2 -> HI when [H2]=0.2 M, [I2]=0.2 M, [HI]=0.8 M",
        "reaction_quotient",
        "Qc = 16",
    ),
    (
        "Find first-order half-life when k=0.2 s^-1",
        "first_order_half_life",
        "t₁/₂ = 3.46574 s",
    ),
    (
        "For a first-order reaction [A]0=1, k=0.1, t=10 s, find [A]",
        "first_order_concentration",
        "[A]ₜ = 0.367879 mol/L",
    ),
    (
        "Use Arrhenius equation with A=1e10, Ea=50 kJ, T=300 K",
        "arrhenius",
        "k = 19.6968 s⁻¹",
    ),
    (
        "Find electrochemical Gibbs ΔG for a cell with n=2 and E°=1.1 V",
        "cell_gibbs",
        "ΔG° = -212.268 kJ/mol",
    ),
    (
        "Use Nernst equation with E°=1.1 V, n=2, Q=10, T=298 K",
        "nernst",
        "E = 1.07044 V",
    ),
    (
        "Find mass deposited by electrolysis when molar mass=63.55 g/mol, "
        "current=2 A, time=3600 s, n=2",
        "electrolysis_mass",
        "m = 2.37114 g",
    ),
    (
        "A radioactive sample has initial mass=100 g, half-life=5 years, "
        "after 10 years find remaining amount",
        "radioactive_decay",
        "N = 25 g",
    ),
    (
        "Use Beer-Lambert law: epsilon=100, path length=1 cm, "
        "concentration=0.02 M, find absorbance",
        "beer_lambert",
        "A = 2",
    ),
    (
        "Find the empirical formula from 40.0% C, 6.7% H, and 53.3% O",
        "empirical_formula",
        "CH2O",
    ),
    (
        "Find the molecular formula from 40.0% C, 6.7% H, and 53.3% O when molar mass=180",
        "molecular_formula",
        "C6H12O6",
    ),
    (
        "10 g of H2 reacts with excess O2 in H2 + O2 -> H2O. How many grams of H2O form?",
        "mass_stoichiometry",
        "H2O = 89.2079 g",
    ),
    (
        "0.50 L of 0.20 M HCl reacts with excess NaOH in HCl + NaOH -> NaCl + H2O. "
        "How many moles of NaCl form?",
        "solution_stoichiometry",
        "NaCl = 0.1 mol",
    ),
    (
        "Chemistry: 2.0 L of H2 at 1 atm and 273.15 K reacts with excess O2 in "
        "H2 + O2 -> H2O. How many liters of H2O gas form?",
        "gas_stoichiometry",
        "H2O = 2 L",
    ),
    (
        "Find the limiting reagent from masses 10 g H2 and 10 g O2 in H2 + O2 -> H2O",
        "limiting_mass",
        "Limiting reagent = O2; 11.2625 g H2O",
    ),
    (
        "Find the limiting solution reagent and grams of NaCl: HCl=0.050 L (0.10 M) and "
        "NaOH=0.020 L (0.10 M) in HCl + NaOH -> NaCl + H2O",
        "limiting_solution",
        "Limiting reagent = NaOH; 0.11688 g NaCl",
    ),
    ("Find the strong acid pH of 0.010 M HCl", "strong_acid_ph", "pH = 2"),
    ("Find the strong base pH of 0.010 M NaOH", "strong_base_ph", "pH = 12"),
    (
        "Find the weak acid pH of 0.10 M HA when Ka=1.8e-5",
        "weak_acid_ph",
        "pH = 2.87528",
    ),
    (
        "Find the weak base pH of 0.10 M B when Kb=1.8e-5",
        "weak_base_ph",
        "pH = 11.1247",
    ),
    ("Find Kb from Ka=1.8e-5", "ka_kb", "Kb = 5.5556 × 10^-10"),
    (
        "Strong acid strong base titration: Ma=0.10, Va=0.050 L, Mb=0.10, Vb=0.020 L, find pH",
        "titration_strong",
        "pH = 1.36798",
    ),
    (
        "Weak acid strong base titration: Ma=0.10, Va=0.050 L, Mb=0.10, Vb=0.025 L, "
        "Ka=1.8e-5, find pH",
        "titration_weak",
        "pH = 4.74473",
    ),
    (
        "Buffer after adding acid: pKa=4.76, HA=0.10 mol, A-=0.10 mol, added=0.02 mol acid",
        "buffer_addition",
        "pH = 4.58391",
    ),
    (
        "Find the polyprotic pH of 0.10 M HA when Ka1=4.3e-7",
        "polyprotic_ph",
        "pH = 3.68372",
    ),
    (
        "Use the combined gas law: P1=1 atm, V1=2 L, T1=300 K, V2=4 L, T2=300 K, find P2",
        "combined_gas",
        "p2 = 0.5 atm",
    ),
    ("Use Boyle's law: P1=2 atm, V1=3 L, V2=6 L, find P2", "boyle", "p2 = 1 atm"),
    (
        "Use Charles's law: V1=2 L, T1=300 K, T2=600 K, find V2",
        "charles",
        "v2 = 4 L",
    ),
    (
        "Use Dalton's law: P(N2)=0.8 atm and P(O2)=0.2 atm",
        "dalton",
        "Ptotal = 1 atm",
    ),
    (
        "Find the partial pressure when mole fraction=0.25 and total pressure=2 atm",
        "partial_pressure",
        "Pi = 0.5 atm",
    ),
    (
        "Gas collected over water at 25 C with total pressure=760 mmHg",
        "gas_over_water",
        "Pdry = 736.24 mmHg",
    ),
    (
        "Find calorimetry heat when calorimeter constant Ccal=200 J/C and ΔT=2 C",
        "calorimetry",
        "q_rxn = -400 J",
    ),
    (
        "Use Hess's law: ΔH1=-200 kJ, multiplier1=1, ΔH2=50 kJ, multiplier2=2",
        "hess",
        "ΔH = -100 kJ",
    ),
    (
        "Find the formation enthalpy for C + O2 -> CO2 when ΔHf(CO2)=-393.5 kJ/mol",
        "formation_enthalpy",
        "ΔH° = -393.5 kJ/mol",
    ),
    (
        "Find the bond enthalpy when bonds broken=800 kJ and bonds formed=1000 kJ",
        "bond_enthalpy",
        "ΔH = -200 kJ",
    ),
    (
        "Find the molar solubility from Ksp=1.8e-10 for AgCl(s) -> Ag+ + Cl-",
        "ksp",
        "s = 1.3416 × 10^-5 mol/L",
    ),
    (
        "Compare precipitation when Qsp=2e-10 and Ksp=1.8e-10",
        "precipitation",
        "precipitate forms (Qsp > Ksp)",
    ),
    (
        "Common-ion solubility: Ksp=1.8e-10 for AgCl(s) -> Ag+ + Cl- when [Cl-]=0.01",
        "common_ion",
        "[Ag+] = 1.8 × 10^-8 mol/L",
    ),
    (
        "Find Kp for CaCO3(s) -> CaO(s) + CO2(g) when P(CO2)=0.2 atm",
        "kp",
        "Kp = 0.2",
    ),
    (
        "Convert Kc to Kp: Kc=0.5 at T=298 K for N2 + H2 -> NH3",
        "kc_kp",
        "Kp = 8.3618 × 10^-4",
    ),
    (
        "Solve the ICE equilibrium for N2O4 -> NO2 when K=4 and [N2O4]=1",
        "ice_equilibrium",
        "x = 0.618034; [N2O4] = 0.381966 mol/L; [NO2] = 1.23607 mol/L",
    ),
    (
        "For a zero-order reaction [A]0=1, k=0.1, t=2 s, find [A]",
        "zero_order",
        "[A]ₜ = 0.8 mol/L",
    ),
    (
        "For a second-order reaction [A]0=1, k=0.1, t=10 s, find [A]",
        "second_order",
        "[A]ₜ = 0.5 mol/L",
    ),
    (
        "For a zero-order reaction [A]0=1, k=0.1, find the half-life",
        "zero_order_half_life",
        "t₁/₂ = 5 s",
    ),
    (
        "For a second-order reaction [A]0=1, k=0.1, find the half-life",
        "second_order_half_life",
        "t₁/₂ = 10 s",
    ),
    (
        "Find the rate law from experiments a1=0.1, rate1=0.02, a2=0.2, rate2=0.08",
        "rate_law",
        "rate = 2 [A]^2",
    ),
    (
        "Use the two-temperature Arrhenius equation with k1=0.1, T1=300 K, k2=0.4, T2=320 K",
        "arrhenius_two_point",
        "Ea = 55.3262 kJ/mol",
    ),
    (
        "Find the cell potential when cathode=0.34 V and anode=-0.76 V",
        "cell_potential",
        "E°cell = 1.1 V",
    ),
    (
        "Find the galvanic cell for Zn and Cu",
        "galvanic_cell",
        "E°cell = 1.1 V; anode Zn; cathode Cu; n = 2; Zn + Cu2+ → Zn2+ + Cu; spontaneous",
    ),
    ("Find the decay constant when half-life=5 s", "decay_constant", "λ = 0.138629 s⁻¹"),
    (
        "Find the exponential decay when N0=100, decay constant=0.1, and t=10 s",
        "exponential_decay",
        "N = 36.7879",
    ),
    (
        "Find the nuclear activity when decay constant=0.1 and N=1000",
        "nuclear_activity",
        "A = 100",
    ),
    (
        "Balance the nuclear equation 238U -> 234Th + ?",
        "nuclear_equation",
        "238U → 234Th + 4He",
    ),
    (
        "Find the oxidation state of each element in FeSO4",
        "oxidation_state",
        "Fe = +2, S = +6, O = -2",
    ),
    (
        "Find the VSEPR shape of H2O",
        "vsepr",
        "bent, 104.5°, polar, sp3, central formal charge 0; "
        "electron geometry tetrahedral, ideal angle 109.5°",
    ),
    (
        "Find the formal charge when valence=4, nonbonding=0, bonding=8",
        "formal_charge",
        "FC = 0",
    ),
    ("Identify functional groups in SMILES CCO", "functional_groups", "alcohol"),
    (
        "Find the stereochemistry of SMILES C[C@H](N)C(=O)O",
        "stereochemistry",
        "C1=S",
    ),
    (
        "What is the isomer relationship between SMILES CCO and COC?",
        "isomers",
        "constitutional isomers",
    ),
    (
        "Name the coordination complex [Co(NH3)6]Cl3",
        "coordination_complex",
        "Co oxidation state +3, coordination number 6, hexaamminecobalt(III) chloride",
    ),
    (
        "Find the boiling point elevation when i=1, Kb=0.512, and molality=0.5",
        "boiling_elevation",
        "ΔTb = 0.256 °C",
    ),
    (
        "Find the freezing point depression when i=1, Kf=1.86, and molality=0.5",
        "freezing_depression",
        "ΔTf = 0.93 °C",
    ),
    (
        "Find the osmotic pressure when i=1, molarity=0.1, and T=298 K",
        "osmotic_pressure",
        "Π = 2.44531 atm",
    ),
    (
        "Use Raoult's law when mole fraction=0.8 and pure pressure=100",
        "raoult",
        "P = 80",
    ),
    (
        "Use the calibration curve slope=2, intercept=0.1, signal=1.1, find concentration",
        "calibration",
        "c = 0.5",
    ),
    (
        "Gravimetric analysis: precipitate mass=0.5 g and factor=0.2",
        "gravimetric",
        "mass = 0.1 g",
    ),
    (
        "Standard addition: sample signal=0.2, spiked signal=0.6, "
        "standard concentration=0.01, standard volume=0.001 L, sample volume=0.01 L",
        "standard_addition",
        "c = 5 × 10^-4",
    ),
]


def test_pipeline_matrix_covers_every_typed_operation() -> None:
    assert {operation for _question, operation, _answer in PIPELINE_CASES} == set(
        get_args(ChemistryOp)
    )


@pytest.mark.parametrize(("question", "operation", "answer"), PIPELINE_CASES)
def test_text_pipeline_matrix(question: str, operation: ChemistryOp, answer: str) -> None:
    assert is_chemistry_question(question)
    intent = extract_chemistry_intent(question)
    assert intent is not None
    assert intent.chemistry_op == operation

    result = solve_chemistry(intent)
    assert result.answer == answer
    assert ".00" not in result.answer
    assert result.given
    assert result.find
    assert result.formula_name
    assert result.formula
    assert result.substitution


def test_direct_reply_has_scan_friendly_heading_order() -> None:
    intent = extract_chemistry_intent("Find pH when [H+] = 0.001")
    assert intent is not None
    verified = build_verified_chemistry(intent)
    assert verified is not None

    reply = format_direct_chemistry_reply(verified)
    headings = ["**Given**", "**Find**", "**Formula**", "**Substitution**", "**Answer**"]
    positions = [reply.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert "pH = −log₁₀[H⁺] — Definition of pH" in reply
    assert "**pH = 3** ✅" in reply
    assert "```answer" not in reply
    assert "pH = 3.00" not in reply
    assert maybe_direct_chemistry_reply(verified, has_image_attachment=False) == reply
    assert maybe_direct_chemistry_reply(verified, has_image_attachment=True) is None
    assert maybe_direct_chemistry_reply(None, has_image_attachment=False) is None


@pytest.mark.parametrize(
    "question",
    [
        "",
        "What is chemistry?",
        "Find molarity of 2 mol",
        "Use the ideal gas law with P=1 atm",
        "Find buffer pH with pKa=4.7",
        "x" * 4001,
    ],
)
def test_incomplete_or_non_calculation_text_stays_on_model_path(question: str) -> None:
    assert extract_chemistry_intent(question) is None


@pytest.mark.parametrize(
    ("params", "answer"),
    [
        ({"volume": 10, "moles": 1, "temperature": 300}, "P = 2.46172 atm"),
        ({"pressure": 1, "volume": 24.6172, "temperature": 300}, "n = 1 mol"),
        ({"pressure": 1, "volume": 24.6172, "moles": 1}, "T = 300 K"),
    ],
)
def test_ideal_gas_supports_every_rearrangement(params: dict[str, float], answer: str) -> None:
    result = solve_chemistry(ChemistryIntent(kind="gases", chemistry_op="ideal_gas", params=params))
    assert result.answer == answer


def test_dilution_can_find_final_concentration() -> None:
    result = solve_chemistry(
        ChemistryIntent(
            kind="solutions",
            chemistry_op="dilution",
            params={"m1": 2, "v1": 50, "v2": 200},
            units={"v1": "mL"},
        )
    )
    assert result.answer == "M2 = 0.5 mol/L"
    assert result.formula == "M1V1 = M2V2"


def test_dilution_normalizes_each_supplied_volume_unit() -> None:
    intent = extract_chemistry_intent("Dilution using M1V1: M1=1, V1=500 mL, V2=2 L, find M2")
    assert intent is not None
    assert intent.params == {"m1": 1, "v1": 500, "v2": 2}
    assert intent.units == {"v1": "mL", "v2": "L"}

    result = solve_chemistry(intent)
    assert result.given == ("M1 = 1 mol/L", "V1 = 500 mL", "V2 = 2 L")
    assert result.substitution == ("M2 = (1)(0.5 L) / (2 L)",)
    assert result.answer == "M2 = 0.25 mol/L"

    implicit_unit = extract_chemistry_intent(
        "Dilution using M1V1: M1=1, V1=500 mL, V2=2000, find M2"
    )
    assert implicit_unit is not None
    assert implicit_unit.units == {"v1": "mL", "v2": "mL"}
    assert solve_chemistry(implicit_unit).answer == "M2 = 0.25 mol/L"


def test_explicit_zero_nernst_temperature_is_not_defaulted() -> None:
    intent = extract_chemistry_intent("Use Nernst equation with E°=1.1 V, n=2, Q=10, T=0 K")
    assert intent is not None
    assert intent.params["temperature"] == 0
    assert build_verified_chemistry(intent) is None


@pytest.mark.parametrize(
    ("question", "elapsed", "half_life", "unit", "answer"),
    [
        (
            "A radioactive sample has initial mass=100 g, half-life=1 year, "
            "after 2 years find remaining amount",
            2,
            1,
            "years",
            "N = 25 g",
        ),
        (
            "A radioactive sample has initial mass=80 g, half-life=2 hours, "
            "after 30 min find remaining amount",
            30,
            120,
            "min",
            "N = 67.2717 g",
        ),
    ],
)
def test_decay_normalizes_time_aliases_and_scales(
    question: str,
    elapsed: float,
    half_life: float,
    unit: str,
    answer: str,
) -> None:
    intent = extract_chemistry_intent(question)
    assert intent is not None
    assert intent.params["elapsed"] == elapsed
    assert intent.params["half_life"] == half_life
    assert intent.units["time"] == unit
    assert solve_chemistry(intent).answer == answer


def test_beer_lambert_can_find_concentration() -> None:
    result = solve_chemistry(
        ChemistryIntent(
            kind="spectroscopy",
            chemistry_op="beer_lambert",
            params={"absorbance": 2, "epsilon": 100, "path": 1},
        )
    )
    assert result.answer == "c = 0.02 mol/L"


@pytest.mark.parametrize(
    "intent",
    [
        ChemistryIntent(kind="solutions", chemistry_op="molarity", params={"moles": 1}),
        ChemistryIntent(
            kind="solutions",
            chemistry_op="mass_percent",
            params={"solute_mass": 6, "solution_mass": 5},
        ),
        ChemistryIntent(
            kind="gases",
            chemistry_op="ideal_gas",
            params={"pressure": -1, "moles": 1, "temperature": 300},
        ),
        ChemistryIntent(
            kind="kinetics",
            chemistry_op="first_order_half_life",
            params={"rate_constant": 0},
        ),
        ChemistryIntent(
            kind="electrochemistry",
            chemistry_op="nernst",
            params={
                "standard_potential": 1,
                "electrons": 0,
                "quotient": 1,
                "temperature": 298,
            },
        ),
        ChemistryIntent(
            kind="nuclear",
            chemistry_op="radioactive_decay",
            params={"initial": 1, "elapsed": 1, "half_life": 0},
        ),
    ],
)
def test_physically_invalid_inputs_are_rejected(intent: ChemistryIntent) -> None:
    with pytest.raises(MathServiceError):
        solve_chemistry(intent)
    assert build_verified_chemistry(intent) is None


def test_non_finite_inputs_are_rejected_at_schema_boundary() -> None:
    with pytest.raises(ValidationError, match="finite"):
        ChemistryIntent(kind="solutions", chemistry_op="molarity", params={"moles": math.inf})


def test_operation_must_belong_to_its_typed_group() -> None:
    with pytest.raises(ValidationError, match="not a 'gases'"):
        ChemistryIntent(kind="gases", chemistry_op="molarity", params={})


@pytest.mark.parametrize(
    ("value", "formatted"),
    [(20.0, "20"), (20.2, "20.2"), (-0.0, "0"), (6.022e23, "6.022 × 10^23")],
)
def test_number_formatting_removes_only_unnecessary_zeros(value: float, formatted: str) -> None:
    assert format_number(value) == formatted
