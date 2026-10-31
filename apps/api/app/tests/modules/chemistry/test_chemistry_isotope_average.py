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
            "A(Mg) = 24.305 u",
            ("Mg-24: 23.985 u, 78.99%", "Mg-25: 24.986 u, 10.00%", "Mg-26: 25.983 u, 11.01%"),
        ),
        (
            "Isotope Mass number Atomic mass Relative abundance\n24Mg 24 23.985 0.7899\n"
            "25Mg 25 24.986 0.1000\n26Mg 26 25.983 0.1101\nWhat is the atomic mass of magnesium?",
            "A(Mg) = 24.305 u",
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
        # A mass that cannot be the isotope's (a sample's) declines.
        (
            "Chlorine has isotopes 35Cl (75%) and 37Cl (25%). A sample has a mass of 2 g. "
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
