"""Laws a school chemistry question asks that the catalog did not answer before.

The answers are hand-worked in ``new_law_cases.py`` and the corpus; these tests pin what each
reader takes, what it declines, and the units a question may write.
"""

from __future__ import annotations

import pytest

from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.request import is_chemistry_question
from app.modules.chemistry.solvers import solve_chemistry
from app.modules.chemistry.solvers.types import format_number
from app.modules.chemistry.species_facts import dissolution_equation
from app.services.solving import SolveServiceError
from app.services.subject_solving import detect_subject


def _answer(question: str) -> str | None:
    intent = extract_chemistry_intent(question)
    return None if intent is None else solve_chemistry(intent).answer


@pytest.mark.parametrize(
    ("formula", "equation"),
    [
        ("AgCl", "AgCl(s) -> Ag+ + Cl-"),
        ("CaF2", "CaF2(s) -> Ca2+ + F-"),
        ("Ag2CrO4", "Ag2CrO4(s) -> Ag+ + CrO4^2-"),
        ("Ca3(PO4)2", "Ca3(PO4)2(s) -> Ca2+ + PO4^3-"),
        # The cation's charge is the one that makes the salt neutral.
        ("Fe(OH)3", "Fe(OH)3(s) -> Fe3+ + OH-"),
        ("Bi2S3", "Bi2S3(s) -> Bi3+ + S^2-"),
        # Not salts: an acid, a molecule, a hydrocarbon.
        ("HCl", None),
        ("H2O", None),
        ("CH4", None),
    ],
)
def test_a_salt_formula_gives_its_dissolution(formula: str, equation: str | None) -> None:
    assert dissolution_equation(formula) == equation


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("The Ksp of AgCl is 1.8 × 10^-10. Find its molar solubility.", "s = 1.3 × 10^-5 mol/L"),
        ("Ksp(PbI2) = 7.1e-9. What is the molar solubility?", "s = 0.0012 mol/L"),
        ("The molar solubility of PbI2 is 1.5 × 10^-3 M. Find Ksp.", "Ksp = 1.4 × 10^-8"),
    ],
)
def test_a_solubility_product_reads_the_salt_by_its_formula(question: str, answer: str) -> None:
    assert _answer(question) == answer


def test_partial_pressures_listed_in_words_are_numbered_in_order() -> None:
    intent = extract_chemistry_intent(
        "The partial pressures are 0.30 atm, 0.50 atm and 0.20 atm. Find the total pressure."
    )
    assert intent is not None
    result = solve_chemistry(intent)
    assert result.given == ("P₁ = 0.30 atm", "P₂ = 0.50 atm", "P₃ = 0.20 atm")
    assert result.answer == "Ptotal = 1.00 atm"


def test_a_stated_total_is_not_a_partial_pressure() -> None:
    question = (
        "The total pressure is 2 atm and the partial pressures are 0.3 atm and 0.5 atm. "
        "Find the third."
    )
    assert extract_chemistry_intent(question) is None


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("Compare the rates of effusion of H2 and O2.", "rate(H2) / rate(O2) = 3.984"),
        # Gases named in words; a noble gas is a single atom.
        (
            "How many times faster does helium effuse than oxygen?",
            "rate(He) / rate(O2) = 2.827",
        ),
        # "Times slower" asks how many times the second gas outpaces the first.
        ("How many times slower does O2 effuse than H2?", "rate(H2) / rate(O2) = 3.984"),
    ],
)
def test_grahams_law_compares_two_named_gases(question: str, answer: str) -> None:
    assert _answer(question) == answer


@pytest.mark.parametrize(
    "question",
    [
        "How many times longer does it take O2 to effuse than H2?",
        "Which gas effuses faster and which slower, H2 or O2?",
    ],
)
def test_grahams_law_declines_a_time_or_an_unclear_direction(question: str) -> None:
    # A time ratio is the inverse of the rate ratio; asked both ways, the direction is unclear.
    assert extract_chemistry_intent(question) is None


def test_a_particle_count_divides_by_avogadros_number_as_one_quantity() -> None:
    intent = extract_chemistry_intent("How many grams do 3.01 × 10^23 molecules of H2O weigh?")
    assert intent is not None
    assert solve_chemistry(intent).substitution == (
        "m = [3.01 × 10^23 / (6.022 × 10^23 mol⁻¹)](18.015 g/mol)",
    )


def test_grahams_law_with_a_stated_rate_declines() -> None:
    # A rate or a time is another Graham question, not the ratio of two known gases.
    question = "H2 effuses at 4.0 mL/s. How fast does O2 effuse by Graham's law?"
    assert extract_chemistry_intent(question) is None


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("How many grams of oxygen are in 10.0 g of H2O?", "m(O) = 8.88 g"),
        ("Find the mass of carbon in 50.0 g of glucose.", "m(C) = 20.0 g"),
        # The element is not in the compound.
        ("How many grams of sulfur are in 10.0 g of H2O?", None),
    ],
)
def test_an_elements_mass_in_a_sample(question: str, answer: str | None) -> None:
    assert _answer(question) == answer


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        # Unstated masses come from the isotope table, not the mass numbers (35.48 u).
        (
            "Chlorine has isotopes 35Cl (75.77%) and 37Cl (24.23%). Find its average atomic mass.",
            "A(Cl) = 35.45 u",
        ),
        (
            "Copper has two isotopes: Cu-63 (62.93 amu, 69.17%) and Cu-65 (64.93 amu, 30.83%). "
            "Calculate the average atomic mass of copper.",
            "A(Cu) = 63.55 u",
        ),
        # Abundances that do not make 100% are a different question.
        ("Chlorine has isotopes 35Cl (70%) and 37Cl (20%). Find its average atomic mass.", None),
        # An isotope the table lacks, with no stated mass.
        ("Tin has isotopes Sn-118 (50%) and Sn-120 (50%). Find its average atomic mass.", None),
    ],
)
def test_an_average_atomic_mass_weights_isotope_masses(question: str, answer: str | None) -> None:
    assert _answer(question) == answer


@pytest.mark.parametrize(
    "question",
    [
        # 1 + 1 -> 1 is not the balanced equation.
        "What is the atom economy of H2 + O2 -> H2O?",
        # Two products, and the question does not say which mass is desired.
        "What is the atom economy of CH3COOH + CH3OH -> CH3COOCH3 + H2O?",
    ],
)
def test_atom_economy_declines_an_unbalanced_or_unnamed_product(question: str) -> None:
    assert extract_chemistry_intent(question) is None


def test_binary_vapor_pressure_declines_when_only_one_pressure_is_stated() -> None:
    question = (
        "What is the total vapor pressure if the mole fraction of A is 0.400, "
        "the vapor pressure of A is 0.800 atm, and the mole fraction of B is 0.600?"
    )
    assert extract_chemistry_intent(question) is None


def test_an_ions_electron_configuration_is_not_the_atoms() -> None:
    assert _answer("What is the electron configuration of copper?") == "Cu: [Ar] 3d10 4s1"
    assert extract_chemistry_intent("Write the electron configuration of Fe3+.") is None


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("What is the pH of 5 mM HCl?", "pH = 2.30"),
        ("What is the pH of a 250 µM HNO3 solution?", "pH = 3.602"),
        ("How much heat is released when 2.0 mol react if ΔH = -10 kcal/mol?", "q = -84 kJ"),
        (
            "Vmax = 10 μmol/min, Km = 2.0 mM and [S] = 2.0 mM. Find the reaction rate.",
            "v = 5.0 μmol/min",
        ),
    ],
)
def test_millimolar_micromolar_and_kilocalories_are_converted(question: str, answer: str) -> None:
    assert _answer(question) == answer


def test_a_template_never_reads_a_millimolar_value_as_molar() -> None:
    # The labelled dilution template would take 5 mM as 5 M; such a question goes unread.
    assert extract_chemistry_intent("Dilution: M1 = 5 mM, V1 = 10 mL, V2 = 50 mL. Find M2.") is None


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("What volume of 6.0 M HCl is needed to make 500 mL of 1.5 M HCl?", "V1 = 1.2 × 10^2 mL"),
        (
            "How many liters of 18 M H2SO4 do you need to make 2.0 L of 3.0 M H2SO4?",
            "V1 = 0.33 L",
        ),
    ],
)
def test_a_dilution_finds_the_stock_volume(question: str, answer: str) -> None:
    assert _answer(question) == answer


def test_a_stock_weaker_than_its_dilution_has_no_answer() -> None:
    intent = extract_chemistry_intent(
        "What volume of 0.5 M NaCl is needed to make 100 mL of 2 M NaCl?"
    )
    assert intent is not None
    with pytest.raises(SolveServiceError):
        solve_chemistry(intent)


def test_a_first_order_half_life_gives_k_per_its_time_unit() -> None:
    assert _answer("The half-life of a first-order reaction is 20.0 min. Find k.") == (
        "k = 0.0347 min⁻¹"
    )
    assert _answer(
        "A first-order reaction has a half-life of 3.0 hours. What is the rate constant?"
    ) == ("k = 0.23 h⁻¹")


def test_an_ice_table_reads_a_chain_of_equal_concentrations() -> None:
    intent = extract_chemistry_intent(
        "For H2 + I2 ⇌ 2HI, Kc = 50 and the initial [H2] = [I2] = 1.0 M. "
        "Find the equilibrium concentrations."
    )
    assert intent is not None
    assert intent.species == {"H2": 1.0, "I2": 1.0}


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        (
            "25.0 mL of NaOH is neutralized by 20.0 mL of 0.100 M HCl. "
            "Find the concentration of the NaOH.",
            "C₂ = 0.0800 mol/L",
        ),
        # H2SO4 gives two protons: it neutralizes twice its amount of NaOH.
        (
            "40.0 mL of NaOH is neutralized by 25.0 mL of 0.0500 M H2SO4. "
            "Find the concentration of the NaOH.",
            "C₂ = 0.0625 mol/L",
        ),
    ],
)
def test_a_neutralization_finds_the_unknown_concentration(question: str, answer: str) -> None:
    assert _answer(question) == answer


@pytest.mark.parametrize(
    "question",
    [
        "25.0 mL of NaOH is neutralized by 20.0 mL of 0.100 M HCl. Find the concentration.",
        "Compare the rates of effusion of H2 and O2.",
        "How many grams of oxygen are in 10 g of H2O?",
        "Vmax = 10 μmol/min, Km = 2 mM and [S] = 2 mM. Find the reaction rate.",
        "What volume of 6 M HCl is needed to make 500 mL of 1.5 M HCl?",
        "The partial pressures are 0.3 atm, 0.5 atm and 0.2 atm. Find the total pressure.",
    ],
)
def test_each_new_reading_reaches_chemistry(question: str) -> None:
    assert is_chemistry_question(question)
    assert detect_subject(question) == "chemistry"


@pytest.mark.parametrize(
    ("value", "figures", "shown"),
    [
        # Zeros that are the number's own digits stay plain.
        (200.0, 2, "200"),
        (16700.0, 3, "16700"),
        (110.02, 2, "110"),
        # Rounding that replaces a whole number's digits with zeros writes a power of ten.
        (1780.0, 2, "1.8 × 10^3"),
        (125.0, 2, "1.2 × 10^2"),
    ],
)
def test_a_rounded_whole_number_is_not_mistaken_for_measured_zeros(
    value: float, figures: int, shown: str
) -> None:
    assert format_number(value, significant=figures, keep_zeros=True) == shown
