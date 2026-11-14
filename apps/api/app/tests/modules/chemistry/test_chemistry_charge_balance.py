"""A compound whose ions' charges cannot cancel gets no verified answer.

"What is the molar mass of NaCl3?" was answered 129.34 g/mol, verified (audit 2026-11-13,
CHEM-05). Only a formula certainly impossible is refused: covalent and variable-valence
formulas, peroxides, superoxides, polyhalides and azides keep their answers.
"""

from __future__ import annotations

import pytest

from app.modules.chemistry.block import build_verified_chemistry
from app.modules.chemistry.charge_balance import impossible_compound
from app.modules.chemistry.extract import extract_chemistry_intent


@pytest.mark.parametrize(
    "formula",
    ["NaCl3", "NaCl2", "MgCl3", "CaCl", "AlCl2", "AlCl4", "Na2Cl", "KF2", "ZnCl", "Na3S", "Na4N"],
)
def test_a_fixed_charge_metal_and_an_anion_that_cannot_cancel(formula: str) -> None:
    assert impossible_compound(formula)


@pytest.mark.parametrize(
    "formula",
    [
        "NaCl",
        "MgCl2",
        "AlCl3",
        "Al2O3",
        "ZnCl2",
        "CaH2",
        "Li3N",
        "Mg3N2",
        # Peroxide, superoxide, ozonide, triiodide, tribromide, azide, disulfide: chains of
        # the anion's atoms carry its charge.
        "Na2O2",
        "KO2",
        "KO3",
        "BaO2",
        "KI3",
        "CsBr3",
        "NaN3",
        "Na2S2",
        # Not a metal of one charge, or not an anion this reads: never refused here.
        "PCl5",
        "SF6",
        "Fe3O4",
        "CuCl",
        "AgF2",
        "CO",
        "H2O2",
        "CaC2",
        "MgB2",
        "C6H12O6",
        "NaHCO3",
        # An ion is not a compound.
        "Cl3-",
    ],
)
def test_a_compound_that_can_exist_is_never_refused(formula: str) -> None:
    assert not impossible_compound(formula)


def _answer(text: str) -> str | None:
    intent = extract_chemistry_intent(text)
    verified = None if intent is None else build_verified_chemistry(intent)
    return None if verified is None else verified.result.answer


@pytest.mark.parametrize(
    "text",
    [
        "What is the molar mass of NaCl3?",
        "What is the molar mass of MgCl3?",
        "How many moles are in 10 g of NaCl3?",
        "What is the mass percent of Cl in MgCl3?",
        "Calculate the moles in 25 g of CaCl",
        "Balance Na + Cl2 -> NaCl2",
        "Balance Na + Cl2 -> NaCl3",
        "How many grams of AlCl2 form from 10 g of Al? Al + Cl2 -> AlCl2",
    ],
)
def test_a_question_about_an_impossible_compound_declines(text: str) -> None:
    assert _answer(text) is None


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("What is the molar mass of PCl5?", "M(PCl5) = 208.22 g/mol"),
        ("What is the molar mass of SF6?", "M(SF6) = 146.05 g/mol"),
        ("What is the molar mass of Fe3O4?", "M(Fe3O4) = 231.53 g/mol"),
        ("What is the molar mass of CO?", "M(CO) = 28.01 g/mol"),
        ("What is the molar mass of H2O2?", "M(H2O2) = 34.01 g/mol"),
        ("What is the molar mass of Na2O2?", "M(Na2O2) = 77.98 g/mol"),
        ("What is the molar mass of KO2?", "M(KO2) = 71.10 g/mol"),
        ("What is the molar mass of KI3?", "M(KI3) = 419.81 g/mol"),
        ("What is the molar mass of NaN3?", "M(NaN3) = 65.01 g/mol"),
        ("Balance Na + Cl2 -> NaCl", "2 Na + Cl2 -> 2 NaCl"),
    ],
)
def test_a_compound_that_exists_keeps_its_answer(text: str, answer: str) -> None:
    assert _answer(text) == answer


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        # A complex ion's formula comes without its charge ("AlF6" of AlF6^3-): it is no neutral
        # compound to refuse (PR #2438 review).
        ("Balance Al3+ + F- -> AlF6^3-", "Al3+ + 6 F- -> AlF6^3-"),
        ("Balance Zn2+ + Cl- -> ZnCl4^2-", "Zn2+ + 4 Cl- -> ZnCl4^2-"),
        ("Balance Fe3+ + SCN- -> FeSCN^2+", "Fe3+ + SCN- -> FeSCN^2+"),
    ],
)
def test_a_complex_ion_in_an_equation_keeps_its_answer(text: str, answer: str) -> None:
    intent = extract_chemistry_intent(text)
    assert intent is not None
    assert build_verified_chemistry(intent).result.answer == answer
