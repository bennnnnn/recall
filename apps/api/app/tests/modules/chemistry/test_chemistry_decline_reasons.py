"""A chemistry question that names something no chemistry has declines with why.

"What is the molar mass of NaCl3?" declined, and the model, told only that nothing verified,
called it "sodium trichloride" at 112 g/mol, then 129 (live round, 2026-11-14). The reason
travels as ``ImpossibleProblemError``: a compound whose charges cannot cancel, an equation no
coefficients balance as written (an element nothing added to it can bring), an atomic number no
element has. Any other decline has none.
"""

from __future__ import annotations

import pytest

from app.modules.chemistry.equations import why_unbalanced
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.input_text import read_chemistry_text
from app.modules.chemistry.solvers.solver import solve_chemistry
from app.services.solving import ImpossibleProblemError, SolveServiceError


@pytest.mark.parametrize(
    ("equation", "reason"),
    [
        (
            "H2 + O2 -> NaCl",
            "H2 + O2 -> NaCl cannot be balanced: Cl and Na are only among the products.",
        ),
        ("Na + O2 -> NaCl", "Na + O2 -> NaCl cannot be balanced: Cl is only among the products."),
        (
            "CaCO3 -> CaO + SO2",
            "CaCO3 -> CaO + SO2 cannot be balanced: C is only among the reactants and S is only "
            "among the products.",
        ),
    ],
)
def test_an_element_on_one_side_only_says_why(equation: str, reason: str) -> None:
    assert why_unbalanced(equation) == reason


@pytest.mark.parametrize(
    "equation",
    [
        # Balances, written balanced or not.
        "H2 + O2 -> H2O",
        "2 Na + Cl2 -> 2 NaCl",
        "KO2 + H2O -> KOH + O2",
        # Balances more than one way: a choice, not an impossibility.
        "Fe + O2 -> FeO + Fe2O3",
        # Short only of what water, H+, OH- or electrons bring: a skeleton to complete.
        "MnO4- + Fe2+ -> Mn2+ + Fe3+",
        "Zn + HNO3 -> Zn(NO3)2 + NH4NO3",
        "Cu + HNO3 -> Cu(NO3)2 + NO2",
        "Fe2+ -> Fe3+",
        "H2O2 + O2 -> H2O",
        # Not read as an equation at all.
        "Xx + O2 -> XxO",
        "CCO",
    ],
)
def test_an_equation_that_balances_or_is_a_skeleton_has_no_reason(equation: str) -> None:
    assert why_unbalanced(equation) is None


def _declined(text: str) -> BaseException:
    intent = extract_chemistry_intent(read_chemistry_text(text))
    assert intent is not None
    with pytest.raises(SolveServiceError) as declined:
        solve_chemistry(intent)
    return declined.value


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (
            "What is the molar mass of NaCl3?",
            "NaCl3 is not a compound: sodium's +1 and chlorine's -1 cannot balance in a 1:3 ratio.",
        ),
        (
            "How many moles are in 10 g of MgCl3?",
            "MgCl3 is not a compound: magnesium's +2 and chlorine's -1 cannot balance in a 1:3 "
            "ratio.",
        ),
        (
            "Balance Na + Cl2 -> NaCl3",
            "NaCl3 is not a compound: sodium's +1 and chlorine's -1 cannot balance in a 1:3 ratio.",
        ),
        (
            "Balance: H2 + O2 -> NaCl",
            "H2 + O2 -> NaCl cannot be balanced: Cl and Na are only among the products.",
        ),
        (
            "What is the name of the element with atomic number 130?",
            "No element has atomic number 130: the table ends at 118, oganesson.",
        ),
    ],
)
def test_a_question_about_what_cannot_exist_declines_with_why(text: str, reason: str) -> None:
    declined = _declined(text)
    assert isinstance(declined, ImpossibleProblemError)
    assert str(declined) == reason


@pytest.mark.parametrize(
    "text",
    [
        # Balances more than one way.
        "Balance Fe + O2 -> FeO + Fe2O3",
        # A redox skeleton is completed with H2O and H+ (battery: chemistry-unverified-self-check).
        "Balance the redox reaction MnO4- + Fe2+ -> Mn2+ + Fe3+ in acidic solution.",
        # A formula no table reads (heavy water's D, a generic acid's A) is no claim that the
        # substance cannot exist.
        "What is the molar mass of D2O?",
        "What is the molar mass of HA?",
        # A concentration below zero is a decline of its own, with no reason given here.
        "What is the pH of -0.01 M HCl?",
        # A half-reaction is completed with H2O, H+ and e-: one that does not balance as
        # written is its question, not a fault in it.
        "Balance H2O -> H2 in acidic solution",
        "Balance the half-reaction FeS -> Fe3+ in acidic solution",
    ],
)
def test_any_other_decline_gives_no_reason(text: str) -> None:
    assert not isinstance(_declined(text), ImpossibleProblemError)
