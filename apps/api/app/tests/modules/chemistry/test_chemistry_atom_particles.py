"""One atom's or ion's particles from any facts a question gives (2026-10-30, a Class 9 book):
"An atom 70X has 31 electrons. How many neutrons?" was answered 70 - 31 = 40."""

from __future__ import annotations

import pytest

from app.modules.chemistry.block import build_verified_chemistry
from app.modules.chemistry.direct import maybe_direct_chemistry_reply
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.request import is_chemistry_question


def _answer(question: str) -> str | None:
    intent = extract_chemistry_intent(question)
    if intent is None or intent.chemistry_op != "atom_particles":
        return None
    verified = build_verified_chemistry(intent)
    return None if verified is None else verified.result.answer


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        (
            "An atom 70X has 31 electrons. How many neutrons are there in its nucleus?",
            "Neutrons = 39",
        ),
        (
            "An atom has 79 protons and a mass number of 197. Calculate (i) the number of "
            "neutrons, and (ii) the number of electrons.",
            "Neutrons = 118\nElectrons = 79",
        ),
        (
            "For an atom of magnesium with a mass number of 24 and atomic number 12, determine "
            "the number of (i) protons, (ii) neutrons, (iii) electrons, and also illustrate the "
            "arrangement of electrons in a magnesium atom.",
            "Protons = 12\nNeutrons = 12\nElectrons = 12\nElectronic configuration = 2, 8, 2",
        ),
        (
            "An element has atomic number 15 and 16 neutrons. What are its mass number, number "
            "of protons, number of electrons?",
            "Protons = 15\nElectrons = 15\nMass number A = 31",
        ),
        (
            "If a species has 11 protons, 12 neutrons and 10 electrons then (i) what is its "
            "atomic number and mass number? (ii) is it neutral, a cation or an anion? (iii) "
            "write its electronic configuration. (iv) name the species.",
            "Atomic number Z = 11\nMass number A = 23\nElectronic configuration = 2, 8\n"
            "Species = Sodium cation (Na⁺)\nType = cation",
        ),
        (
            "How many protons, neutrons and electrons are in 27Al?",
            "Protons = 13\nNeutrons = 14\nElectrons = 13",
        ),
        ("What is the number of electrons in Na+?", "Electrons = 10"),
        ("An ion has 17 protons and 18 electrons. What is its charge?", "Charge = -1"),
        ("What is the valency of an element with atomic number 16?", "Valency = 2"),
    ],
)
def test_every_quantity_asked_is_derived(question: str, answer: str) -> None:
    assert is_chemistry_question(question)
    assert _answer(question) == answer


@pytest.mark.parametrize(
    ("question", "operation"),
    [
        # One number a one-line law reads keeps that law's layout.
        ("How many neutrons are in carbon-14?", "neutron_count"),
        (
            "Oxygen has atomic number 8 and 10 electrons. What is the charge of the ion?",
            "ion_charge",
        ),
        # Past calcium the shell rule stops: the aufbau reader answers, or the ion declines.
        ("What is the electron configuration of Fe?", "electron_configuration"),
        ("How many valence electrons does nitrogen have?", "valence_electrons"),
    ],
)
def test_another_reader_keeps_its_question(question: str, operation: str) -> None:
    intent = extract_chemistry_intent(question)
    assert intent is not None and intent.chemistry_op == operation


@pytest.mark.parametrize(
    "question",
    [
        "Calculate the mass of 2 moles of electrons",
        "The species 27Al, 80Br- and 201Hg2+ have 13, 35 and 80 protons, respectively. How "
        "many electrons and neutrons do they have?",
        "Imagine all the electrons are replaced with hypothetical particles 500 times heavier.",
        "Write the electron configuration of Fe3+.",
    ],
)
def test_more_than_one_atom_or_an_amount_is_not_read(question: str) -> None:
    intent = extract_chemistry_intent(question)
    assert intent is None or intent.chemistry_op != "atom_particles"


def test_a_question_with_more_parts_than_answers_goes_to_the_model() -> None:
    question = (
        "An element X has a mass number of 35 and contains 18 neutrons. (i) How many electrons "
        "and protons does X have? (ii) What is its atomic number? (iii) Identify the element X. "
        "(iv) Write its electronic configuration. (v) How many valence electrons does it have? "
        "(vi) What will be the mass number if two neutrons are added? (vii) What will be the "
        "relation of X with the new atom?"
    )
    intent = extract_chemistry_intent(question)
    assert intent is not None
    verified = build_verified_chemistry(intent)
    assert verified is not None
    assert (
        maybe_direct_chemistry_reply(verified, has_image_attachment=False, user_text=question)
        is None
    )
