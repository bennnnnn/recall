"""Inputs a student writes that the readers declined (audit 2026-11-13, CHEM-07).

"500. mL" (a decimal point that marks trailing zeros significant), a formula typed in
lowercase where an amount names it ("0.01 M hcl"), a formula that opens with a bracketed group
("(NH4)3PO4") and a concentration in g/L. Answers are worked here from standard atomic masses.
"""

from __future__ import annotations

import pytest

from app.modules.chemistry.block import build_verified_chemistry
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.input_text import read_chemistry_text
from app.modules.chemistry.lowercase_formulas import lowercase_substance
from app.modules.chemistry.request import is_chemistry_question


def _answer(text: str) -> str | None:
    intent = extract_chemistry_intent(text)
    verified = None if intent is None else build_verified_chemistry(intent)
    return None if verified is None else verified.result.answer


@pytest.mark.parametrize(
    ("text", "read"),
    [
        ("0.25 mol NaCl in 500. mL of solution", "0.25 mol NaCl in 500 mL of solution"),
        ("a 250. mL flask", "a 250 mL flask"),
        ("What is the pH of 0.01 M hcl?", "What is the pH of 0.01 M HCl?"),
        ("How many moles are in 36 g of h2o?", "How many moles are in 36 g of H2O?"),
        ("the molar mass of naoh", "the molar mass of NaOH"),
        ("how many moles in 10 g of nacl", "how many moles in 10 g of NaCl"),
    ],
)
def test_the_input_reader_writes_what_the_student_meant(text: str, read: str) -> None:
    assert read_chemistry_text(text) == read


@pytest.mark.parametrize(
    "text",
    [
        # A numbered list keeps its numbers: the point is a list item's, not a decimal's.
        "1. What is 2. mol of water?",
        "Step 5. Mix",
        # A word where an amount names its substance stays a word: "co" is Co or CO, "hf" is
        # HF or hafnium, and "gas" (GaS) and "water" (WAtEr) are no substances.
        "What is the molar mass of co?",
        "What is the pH of 0.01 M hf?",
        "How many moles are in 3 g of gas?",
        "the molar mass of water",
        # A lowercase word anywhere else is never read.
        "hi, so what is a mole",
    ],
)
def test_text_that_is_no_formula_is_left_as_written(text: str) -> None:
    assert read_chemistry_text(text) == text


@pytest.mark.parametrize(
    ("token", "formula"),
    [("hcl", "HCl"), ("naoh", "NaOH"), ("koh", "KOH"), ("hbr", "HBr"), ("h2so4", "H2SO4")],
)
def test_a_lowercase_formula_with_one_reading_is_read(token: str, formula: str) -> None:
    assert lowercase_substance(token) == formula


@pytest.mark.parametrize("token", ["co", "no", "hf", "gas", "so", "of", "his", "water"])
def test_a_lowercase_word_with_another_reading_is_not(token: str) -> None:
    assert lowercase_substance(token) is None


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("What is the molarity of 0.25 mol NaCl in 500. mL of solution?", "c = 0.50 mol/L"),
        ("What is the pH of 0.01 M hcl?", "pH = 2.00"),
        ("What is the pH of 0.01 M naoh?", "pH = 12.00"),
        ("How many moles are in 36 g of h2o?", "n(H2O) = 2.0 mol"),
        # 3(14.007) + 12(1.008) + 30.974 + 4(15.999) = 149.087
        ("What is the molar mass of (NH4)3PO4?", "M((NH4)3PO4) = 149.09 g/mol"),
        # M = 132.134 g/mol, so 10 g is 0.0757 mol.
        ("How many moles are in 10 g of (NH4)2SO4?", "n((NH4)2SO4) = 0.076 mol"),
        # 5.85 / 58.44 = 0.1001 mol/L; 20 / 39.997 = 0.500 mol/L.
        ("What is the molarity of a solution with 5.85 g/L NaCl?", "c = 0.100 mol/L"),
        ("A solution contains 20 g/L of NaOH. What is its molarity?", "c = 0.50 mol/L"),
        ("What is the molarity of NaCl at 5.85 g/L?", "c = 0.100 mol/L"),
    ],
)
def test_the_written_input_is_answered(text: str, answer: str) -> None:
    assert _answer(text) == answer


@pytest.mark.parametrize(
    "text",
    [
        # A density is the solution's mass per volume, solute and water together: never the
        # solute's grams per litre. Each was verified as a molarity, up to 32.6 M (review
        # 2026-11-13); main declined them all.
        "The density of a NaCl solution is 1.07 g/mL. What is its molarity?",
        "What is the molarity of an HCl solution with a density of 1.19 g/mL?",
        "An H2SO4 solution has a density of 1.84 g/mL. What is the molarity?",
        "A NaCl solution has a density of 1.07 g/cm3. Find the molarity.",
        "Find the molarity of NaOH whose density is 1.5 g/L",
        "What is the molarity of a solution with 1.84 g/mL density of H2SO4?",
        # Grams per millilitre on a solution is its density, named or not.
        "What is the molarity of a 1.19 g/mL HCl solution?",
        # A density and a mass percent need a law of their own: no reading of either alone.
        "Concentrated HCl is 37% HCl by mass with a density of 1.19 g/mL. What is the molarity?",
        "The solution has 5.85 g/L NaCl and a density of 1.00 g/mL. What is the molarity?",
        # Grams of "dissolved salts" are not one salt's.
        "Seawater contains 35 g/L of dissolved salts. What is the molarity of NaCl?",
    ],
)
def test_a_density_is_never_a_solute_concentration(text: str) -> None:
    assert _answer(text) is None


def test_a_gas_density_still_gives_its_molar_mass() -> None:
    # M = dRT/P = 1.25 g/L * 0.082057 * 273.15 K / 1 atm = 28.0 g/mol.
    assert _answer("A gas has a density of 1.25 g/L at STP. What is its molar mass?") == (
        "M = 28.0 g/mol"
    )


def test_a_formula_opening_with_a_bracket_is_a_chemistry_question() -> None:
    assert is_chemistry_question("How many moles are in 10 g of (NH4)2SO4?")
