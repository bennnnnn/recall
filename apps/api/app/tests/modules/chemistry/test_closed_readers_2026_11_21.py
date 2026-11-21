"""A reader claims a question only when it answers what the question asks (closed world).

P57 of the 2026-11-21 physics round: "A helium-4 nucleus has a mass of 4.001506 u. The proton
mass is 1.007276 u and the neutron mass is 1.008665 u. Find the mass defect, the binding energy
in MeV (1 u = 931.5 MeV) and the binding energy per nucleon." The atom-particles reader read
"proton mass" and "neutron mass" as asks, and the subject order gave the line to chemistry,
whose card stated "Protons = 2, Neutrons = 2", verified. A particle's own mass or charge asks
no count, an ask for an energy or a mass is none this reader answers, and the mass-defect
reader reads the nucleus as the question writes it, with the constants it states.
"""

from __future__ import annotations

import pytest

from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.extractors.atom_particles import extract_atom_particles
from app.modules.chemistry.solvers.solver import solve_chemistry
from app.services.subjects.order import read_subject_reason

P57 = (
    "A helium-4 nucleus has a mass of 4.001506 u. The proton mass is 1.007276 u and the "
    "neutron mass is 1.008665 u. Find the mass defect, the binding energy in MeV "
    "(1 u = 931.5 MeV) and the binding energy per nucleon."
)


@pytest.mark.parametrize(
    "question",
    [
        P57,
        # An ask beside the particles that no count answers.
        "An atom of He-4 has 2 protons. Find its neutrons and its binding energy.",
        # A particle's mass is a given, not an ask.
        "The mass of a proton is 1.007276 u. What is the mass defect of He-4 if its nuclear mass = 4.0015 u?",
    ],
)
def test_the_particles_reader_claims_no_question_it_does_not_answer(question: str) -> None:
    assert extract_atom_particles(question) is None


@pytest.mark.parametrize(
    ("question", "target"),
    [
        ("An atom 70X has 31 electrons. How many neutrons?", "neutrons|atom"),
        (
            "An atom of Al-27 has 13 protons. How many neutrons and electrons does it have?",
            "neutrons,electrons|atom",
        ),
        (
            "Magnesium, mass number 24, atomic number 12: protons, neutrons, electrons",
            "protons,neutrons,electrons",
        ),
    ],
)
def test_the_particles_reader_still_answers_its_own_questions(question: str, target: str) -> None:
    intent = extract_atom_particles(question)
    assert intent is not None and intent.target == target


def test_p57_is_a_mass_defect_with_the_constants_it_states() -> None:
    intent = extract_chemistry_intent(P57)
    assert intent is not None and intent.chemistry_op == "mass_defect"
    assert intent.formula == "He-4"
    assert intent.params == {
        "nuclear_mass": 4.001506,
        "proton_mass": 1.007276,
        "neutron_mass": 1.008665,
        "mev_per_u": 931.5,
    }
    answer = solve_chemistry(intent).answer
    # Δm = 0.030376 u, E = 28.295 MeV, E/A = 7.074 MeV per nucleon.
    assert answer.splitlines() == ["Δm = 0.03038 u", "E = 28.30 MeV", "E/A = 7.074 MeV/nucleon"]


def test_p57_is_read_by_the_reader_that_answers_it() -> None:
    reading = read_subject_reason(P57, False, True)
    assert reading is not None and reading.subject == "chemistry"


def test_a_nucleus_heavier_than_its_nucleons_has_no_defect() -> None:
    from app.services.solving import SolveServiceError

    intent = extract_chemistry_intent("Find the mass defect of He-4 when nuclear mass = 4.5 u.")
    assert intent is not None
    with pytest.raises(SolveServiceError):
        solve_chemistry(intent)
