"""An average atomic mass uses the masses a question states, however it states them."""

from __future__ import annotations

import pytest

from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.solvers import solve_chemistry


def _answer(question: str) -> str | None:
    intent = extract_chemistry_intent(question)
    return None if intent is None else solve_chemistry(intent).answer


@pytest.mark.parametrize(
    ("question", "answer", "given"),
    [
        # 2026-10-31, an Ethiopian Grade 7 book: the stated 10 and 11, not 10.0129 and 11.0093,
        # and 10.8 rather than 11.
        (
            "The atomic masses of the two stable isotopes of boron, ¹⁰B (20%) and ¹¹B (80%) are "
            "10 and 11 respectively. Calculate the average atomic mass of Boron. The percentages "
            "in parenthesis denote the relative abundance.",
            "A(B) = 10.8 u",
            ("B-10: 10 u, 20%", "B-11: 11 u, 80%"),
        ),
        (
            "Chlorine-35 (75%) and chlorine-37 (25%) have masses 35 and 37. "
            "Find the relative atomic mass of chlorine.",
            "A(Cl) = 35.5 u",
            ("Cl-35: 35 u, 75%", "Cl-37: 37 u, 25%"),
        ),
        # Beside each isotope, without a unit.
        (
            "Chlorine-35 has a mass of 34.97 and an abundance of 75.8%; chlorine-37 has a mass "
            "of 36.97 and an abundance of 24.2%. Calculate the average atomic mass.",
            "A(Cl) = 35.45 u",
            ("Cl-35: 34.97 u, 75.8%", "Cl-37: 36.97 u, 24.2%"),
        ),
        (
            "Lithium has two isotopes, 6Li with mass 6.015 (7.5%) and 7Li with mass 7.016 "
            "(92.5%). What is the relative atomic mass of lithium?",
            "A(Li) = 6.941 u",
            ("Li-6: 6.015 u, 7.5%", "Li-7: 7.016 u, 92.5%"),
        ),
        # Lists in the isotopes' order.
        (
            "Copper exists as 63Cu (69.2%) and 65Cu (30.8%), whose masses are 62.93 and 64.93 "
            "respectively. What is the atomic mass of copper?",
            "A(Cu) = 63.55 u",
            ("Cu-63: 62.93 u, 69.2%", "Cu-65: 64.93 u, 30.8%"),
        ),
        (
            "35Cl and 37Cl have masses of 34.97 u and 36.97 u and abundances of 75.8% and 24.2% "
            "respectively. Calculate the relative atomic mass of chlorine.",
            "A(Cl) = 35.45 u",
            ("Cl-35: 34.97 u, 75.8%", "Cl-37: 36.97 u, 24.2%"),
        ),
        (
            "Chlorine has two isotopes, 35Cl and 37Cl, with abundances of 75.77% and 24.23% "
            "respectively. Find the average atomic mass.",
            "A(Cl) = 35.45 u",
            ("Cl-35: 34.9689 u, 75.77%", "Cl-37: 36.9659 u, 24.23%"),
        ),
        # A table under a header that names its columns.
        (
            "Isotope | Mass (u) | Abundance (%)\n|---|---|---|\n| 24Mg | 23.985 | 78.99 |\n"
            "| 25Mg | 24.986 | 10.00 |\n| 26Mg | 25.983 | 11.01 |\n"
            "Calculate the average atomic mass of magnesium.",
            "A(Mg) = 24.31 u",
            ("Mg-24: 23.985 u, 78.99%", "Mg-25: 24.986 u, 10.00%", "Mg-26: 25.983 u, 11.01%"),
        ),
        (
            "Isotope Mass number Atomic mass Relative abundance\n24Mg 24 23.985 0.7899\n"
            "25Mg 25 24.986 0.1000\n26Mg 26 25.983 0.1101\nWhat is the atomic mass of magnesium?",
            "A(Mg) = 24.31 u",
            ("Mg-24: 23.985 u, 78.99%", "Mg-25: 24.986 u, 10%", "Mg-26: 25.983 u, 11.01%"),
        ),
    ],
)
def test_a_stated_isotope_mass_beats_the_table(
    question: str, answer: str, given: tuple[str, ...]
) -> None:
    intent = extract_chemistry_intent(question)
    assert intent is not None
    result = solve_chemistry(intent)
    assert (result.answer, result.given) == (answer, given)


# A value the question quotes as the answer, a sample's mass in grams, a molar mass in g/mol
# or a stated average is never an isotope's mass (PR review, 2026-10-31). The ones marked
# "main" were wrong before this reader too.
@pytest.mark.parametrize(
    ("question", "answer"),
    [
        (
            "Boron consists of 10B (20%) and 11B (80%). Show that its relative atomic mass is "
            "10.8.",
            "A(B) = 10.81 u",
        ),
        (
            "Lithium consists of 7Li (92.5%) and 6Li (7.5%). Show that its relative atomic mass "
            "is 6.9.",
            "A(Li) = 6.941 u",
        ),
        (
            "Boron has isotopes 10B (19.9%) and 11B (80.1%). Find the average atomic mass of "
            "boron, and the moles in a sample whose mass is 10.8 g.",
            "A(B) = 10.81 u",
        ),
        (
            "Lithium has two isotopes, 6Li (7.59%) and 7Li (92.41%), with molar masses 6.015 "
            "g/mol and 7.016 g/mol respectively. Calculate the average atomic mass of lithium.",
            "A(Li) = 6.940 u",
        ),
        (
            "Carbon consists of 12C (98.89%) and 13C (1.11%). Calculate the average atomic mass "
            "of carbon. The accepted atomic mass is 12.011.",
            "A(C) = 12.01 u",
        ),
        (
            "Nitrogen has two isotopes, 14N (99.63%) and 15N (0.37%). Calculate the average "
            "atomic mass of nitrogen. The periodic table lists an atomic mass of 14.01.",
            "A(N) = 14.01 u",
        ),
        # main
        (
            "Boron has isotopes 10B (19.9%) and 11B (80.1%). Calculate the average atomic mass "
            "of boron and compare it with the value of 10.81 u in the periodic table.",
            "A(B) = 10.81 u",
        ),
        # main
        (
            "Boron has isotopes 10B (20%) and 11B (80%). Calculate its average atomic mass. "
            "[Ans. 10.8 amu]",
            "A(B) = 10.81 u",
        ),
        # main
        (
            "Boron's isotopes are 11B (80.1%) and 10B (19.9%). Verify that the average atomic "
            "mass of boron is 10.81 u.",
            "A(B) = 10.81 u",
        ),
        # main
        (
            "Magnesium: 24Mg (78.99%), 25Mg (10.00%), 26Mg (11.01%). Calculate the relative "
            "atomic mass. Your answer should be close to 24.3 u.",
            "A(Mg) = 24.31 u",
        ),
        # main
        (
            "Bromine is 79Br (50.69%) and 81Br (49.31%). Show that the atomic mass of bromine is "
            "79.9 u.",
            "A(Br) = 79.90 u",
        ),
        # main
        (
            "Quick one for my kid's homework: chlorine is 35Cl at 75.8% and 37Cl at 24.2%, she "
            "says the atomic mass is 35.5 - is that right?",
            "A(Cl) = 35.45 u",
        ),
        # The average stated: the question asks for an isotope's mass instead.
        (
            "Gallium has two isotopes: 69Ga (60.11%, 68.926 u) and 71Ga (39.89%). If the average "
            "atomic mass of gallium is 69.72 u, what is the mass of the heavier isotope?",
            None,
        ),
    ],
)
def test_a_quoted_answer_or_a_sample_is_never_an_isotope_mass(
    question: str, answer: str | None
) -> None:
    assert _answer(question) == answer


# A list is the masses only when the last quantity named before it is a mass, never "mass
# numbers"; a list names every isotope, however many.
@pytest.mark.parametrize(
    ("question", "answer"),
    [
        (
            "The relative atomic mass of chlorine is found from 35Cl and 37Cl, whose mass numbers "
            "are 35 and 37 respectively, with abundances of 75.77% and 24.23% respectively.",
            "A(Cl) = 35.45 u",
        ),
        (
            "To calculate the atomic mass of magnesium, note that 24Mg, 25Mg and 26Mg have mass "
            "numbers 24, 25 and 26 respectively and abundances of 78.99%, 10.00% and 11.01% "
            "respectively.",
            "A(Mg) = 24.31 u",
        ),
        (
            "Silicon has three isotopes, 28Si, 29Si and 30Si, with masses 27.977, 28.976 and "
            "29.974 and abundances 92.23%, 4.67% and 3.10% respectively. Calculate the average "
            "atomic mass.",
            "A(Si) = 28.09 u",
        ),
    ],
)
def test_a_list_is_masses_only_when_it_says_so(question: str, answer: str) -> None:
    assert _answer(question) == answer


# Four figures, as a table of atomic masses gives, never more places than the stated masses:
# the textbook tables keep their answers.
@pytest.mark.parametrize(
    ("question", "answer"),
    [
        (
            "Calculate the atomic mass (average) of chlorine using the following data:\n"
            "Isotope  % Natural Abundance  Molar Mass\n35Cl  75.77  34.9689\n37Cl  24.23  36.9659",
            "A(Cl) = 35.45 u",
        ),
        (
            "Calculate the atomic mass (average) of chlorine using the following data:\n"
            "Isotope | Isotopic molar mass | Abundance\n35Cl | 34.96885 g/mol | 75.77\n"
            "37Cl | 36.96590 g/mol | 24.23",
            "A(Cl) = 35.45 u",
        ),
        (
            "Bromine has two isotopes: 79Br (78.9183 u, 50.69%) and 81Br (80.9163 u, 49.31%). "
            "Calculate the average atomic mass of bromine.",
            "A(Br) = 79.90 u",
        ),
        (
            "Chlorine-35 (34.96885 u, 75.78%) and chlorine-37 (36.96590 u, 24.22%). Find the "
            "average atomic mass of chlorine.",
            "A(Cl) = 35.45 u",
        ),
        (
            "Copper has two isotopes: Cu-63 (62.93 amu, 69.17%) and Cu-65 (64.93 amu, 30.83%). "
            "Calculate the average atomic mass of copper.",
            "A(Cu) = 63.55 u",
        ),
    ],
)
def test_an_average_atomic_mass_has_a_tables_precision(question: str, answer: str) -> None:
    assert _answer(question) == answer


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        # No mass stated: the table's, and whole-percent abundances do not cut the mean to two
        # figures (35 u, 11 u).
        (
            "Chlorine has isotopes 35Cl (75%) and 37Cl (25%). Find its average atomic mass.",
            "A(Cl) = 35.47 u",
        ),
        (
            "Boron has isotopes 10B (20%) and 11B (80%). Find its average atomic mass.",
            "A(B) = 10.81 u",
        ),
        # 235U is uranium, not 235 u.
        (
            "Uranium has isotopes 235U (0.72%) and 238U (99.28%). Find its average atomic mass.",
            "A(U) = 238.0 u",
        ),
        # Mass numbers are not masses.
        (
            "Chlorine's isotopes 35Cl and 37Cl have mass numbers 35 and 37 and abundances of "
            "75% and 25% respectively. Find the average atomic mass.",
            "A(Cl) = 35.47 u",
        ),
        # A sample's mass, in grams and in another sentence, is not an isotope's.
        (
            "Chlorine has isotopes 35Cl (75%) and 37Cl (25%). A sample has a mass of 2 g. "
            "Find the average atomic mass.",
            "A(Cl) = 35.47 u",
        ),
        # A stated mass far from its mass number belongs to something else.
        (
            "Chlorine has isotopes 35Cl (75%, mass 35.0 u) and 37Cl (25%, mass 2.0 u). "
            "Find the average atomic mass.",
            None,
        ),
        # Masses for some isotopes but not all are a misreading, not data.
        (
            "Copper has isotopes 63Cu (69.17%, 62.93 u) and 65Cu (30.83%). "
            "Find the average atomic mass.",
            None,
        ),
        # Given twice, beside the isotopes and as a list: which holds is not ours to choose.
        (
            "Chlorine has isotopes 35Cl (75%) and 37Cl (25%), with abundances of 76% and 24% "
            "respectively. Find the average atomic mass.",
            None,
        ),
        # A list that does not name every isotope is not theirs.
        (
            "Magnesium has isotopes 24Mg (79%), 25Mg (10%) and 26Mg (11%), and masses of 23.985 "
            "and 24.986. Find the average atomic mass.",
            None,
        ),
    ],
)
def test_an_average_atomic_mass_reads_only_what_is_certain(
    question: str, answer: str | None
) -> None:
    assert _answer(question) == answer
