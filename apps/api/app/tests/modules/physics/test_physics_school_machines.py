"""A machine in a school book's words, and an equivalence a question states
(2026-10-29, a grade 7 physics book: "the M.A of the machine", "a. VR", "Take 1 liter
of water = 1 kg of water")."""

import pytest

from app.modules.physics.numbers import normalize_physics_units
from app.modules.physics.stated_equivalence import apply_stated_equivalence


@pytest.mark.parametrize(
    ("text", "read"),
    [
        ("the M.A of the machine?", "the mechanical advantage of the machine?"),
        ("b. MA of the machine", "b. mechanical advantage of the machine"),
        ("a. VR of the machine. Calculate", "a. velocity ratio of the machine. Calculate"),
        ("M.A. of a lever", "mechanical advantage of a lever"),
        ("the MA. Calculate the effort", "the mechanical advantage. Calculate the effort"),
    ],
)
def test_a_machines_abbreviations_read_as_their_words(text: str, read: str) -> None:
    assert normalize_physics_units(text) == read


@pytest.mark.parametrize(
    "text",
    [
        "I live in MA",  # a state, with no machine in sight
        "a current of 5 mA in the machine",  # a milliamp
        "is a VR headset worth it",
    ],
)
def test_the_letters_elsewhere_are_left_alone(text: str) -> None:
    assert normalize_physics_units(text) == text


def test_a_stated_equivalence_converts_the_questions_own_amount() -> None:
    text = (
        "An electric motor pumps 200 liter of water to a reservoir of height 6 m in 2 s. "
        "Calculate the power developed by the motor. Take 1 liter of water = 1 kg of water."
    )
    assert apply_stated_equivalence(text) == (
        "An electric motor pumps 200 kg of water to a reservoir of height 6 m in 2 s. "
        "Calculate the power developed by the motor."
    )


@pytest.mark.parametrize(
    "text",
    [
        # Nothing stated, or stated about something the question has no amount of.
        "Pump 200 liter of water up 6 m in 2 s. What power?",
        "A tank holds 50 litres of oil. 1 litre of water has a mass of 1 kg. Find the mass.",
    ],
)
def test_without_a_matching_statement_the_text_is_kept(text: str) -> None:
    assert apply_stated_equivalence(text) == text
