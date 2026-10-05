"""One stated number from each later chemistry law, and a decline when an input is missing."""

from __future__ import annotations

import pytest

from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.solvers import solve_chemistry
from app.services.solving import SolveServiceError
from app.services.subject_solving import detect_subject
from app.tests.modules.chemistry.new_law_cases import STATED_LAW_CASES


@pytest.mark.parametrize(("question", "operation", "answer"), STATED_LAW_CASES)
def test_a_stated_law_answers_one_number(question: str, operation: str, answer: str) -> None:
    assert detect_subject(question) == "chemistry"
    intent = extract_chemistry_intent(question)
    assert intent is not None
    assert intent.chemistry_op == operation
    assert solve_chemistry(intent).answer == answer


@pytest.mark.parametrize(
    "question",
    [
        "The mass number is 23. Find the number of neutrons.",
        "The atomic number is 11. Find the ion charge.",
        "Find the maximum electrons.",
        "The bonding electron count is 8. Find the bond order.",
        "Find the wavenumber.",
        "The event count is 50. Find the quantum yield.",
        "Find the tetrahedral splitting.",
        "A buffer has pKb = 4.74. Find the pOH.",
        "The molar heat capacity is 75.0 J/(mol·K). Find the heat.",
        "The current is 1.00 A. Find the moles of electrons.",
        "Use the Hill equation. The ligand concentration is 2.00 M. Find the saturation.",
        "Use the Freundlich isotherm. The Freundlich constant is 2.00. Find the adsorbed amount.",
        "The polymer molar mass is 10000 g/mol. Find the degree of polymerization.",
        "The weight-average molar mass is 20000 g/mol. Find the polydispersity.",
        "Use the Carothers equation. Find the degree of polymerization.",
        "The monomer concentration is 3.00 M. Find the polymerization rate.",
        "Use the Butler-Volmer equation. The exchange current is 1.00e-6 A. Find the current.",
        "Use the Tafel equation. The current is 0.0100 A. Find the overpotential.",
        "The charge number z = 1.00. Find the electrochemical potential.",
        "The activity is 0.500. Find the chemical potential.",
        "The activity coefficient is 0.800. Find the activity.",
        "The field is 1.00 T. Find the Larmor frequency.",
        "The sample frequency is 4.00004e8 Hz. Find the chemical shift.",
        "The field is 0.500 T. Find the mass-to-charge ratio.",
        "The lattice constant is 0.400 nm. Find the interplanar spacing.",
        "Use the lever rule. The alpha composition is 0.200. Find the alpha fraction.",
        "The diffusion coefficient is 1.00e-5 cm^2/s. Find the mean-square displacement.",
        "Use the Stokes-Einstein equation. The radius is 1.00 nm. Find the diffusion coefficient.",
        "The standard deviation is 0.200. Find the relative standard deviation.",
        "Ka = 1.00e-5. Find the conjugate fraction.",
        "Ka = 1.00e-5. Find the acid fraction.",
        "[H+] = 1.00e-4 M. Find the acid fraction.",
        "The pH is 4.00. Find the conjugate fraction.",
    ],
)
def test_a_stated_law_declines_when_an_input_is_missing(question: str) -> None:
    assert extract_chemistry_intent(question) is None


def test_carothers_declines_when_the_extent_reaches_one() -> None:
    intent = extract_chemistry_intent(
        "Use the Carothers equation. The extent of reaction is 1.00. "
        "Find the degree of polymerization."
    )
    assert intent is not None
    with pytest.raises(SolveServiceError, match="below 1"):
        solve_chemistry(intent)
