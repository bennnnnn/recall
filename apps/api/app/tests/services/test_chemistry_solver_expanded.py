"""Broad regression matrix for the typed chemistry pipeline."""

from __future__ import annotations

import math
from typing import get_args

import pytest
from pydantic import ValidationError

from app.models.schemas.chemistry import ChemistryIntent, ChemistryOp
from app.services.chemistry.block import build_verified_chemistry
from app.services.chemistry.direct import (
    format_direct_chemistry_reply,
    maybe_direct_chemistry_reply,
)
from app.services.chemistry.extract import extract_chemistry_intent
from app.services.chemistry.request import is_chemistry_question
from app.services.chemistry.solvers import solve_chemistry
from app.services.chemistry.solvers.types import format_number
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
