"""A verified answer reads the whole question (``unread.py``).

Nine book questions got a check mark on a wrong number because a reader answered with part
of the question unread and filled the rest with its law's default (Grade 7 and Grade 8
books, 2026-11-19): a lost superscript's mantissa, two directions, an asked average, a
stated equivalence, a fall nobody stated, an angle measured from no line. Each is read now,
or the solve declines; the same questions written cleanly still verify.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics import extract_physics_intent
from app.modules.physics.numbers import fold_lost_powers, normalize_physics_units
from app.modules.physics.prompt import solve_physics_request
from app.modules.physics.unread import unread_in_request

_SETTINGS = Settings()


def _answer(text: str) -> str | None:
    """The verified answer to ``text``, by any route (one law, a chain, parts), or None."""
    outcome, block = solve_physics_request(text, _SETTINGS, True)
    if outcome != "verified" or block is None:
        return None
    return block.canonical_answer


@pytest.mark.parametrize(
    ("text", "folded"),
    [
        ("1.36 × 104 kg/m3", "1.36e4 kg/m3"),
        ("2 × 103 N", "2e3 N"),
        ("1.6 × 10-19 C", "1.6e-19 C"),
        ("3 x 108 m/s", "3e8 m/s"),
        ("13.6 × 103 kg/m3", "13.6e3 kg/m3"),
        # No exponent after the 10, or one that starts with 0: a product, not a power.
        ("4 × 100 m", "4 × 100 m"),
        ("2 × 10 m", "2 × 10 m"),
        ("5 x 10,000 J", "5 x 10,000 J"),
        ("a 10 m pole", "a 10 m pole"),
    ],
)
def test_a_lost_superscript_is_read_as_its_power(text: str, folded: str) -> None:
    assert fold_lost_powers(text) == folded


@pytest.mark.parametrize(
    "text",
    [
        "In a 4 × 100 m relay each runner takes 12 s. Find the speed.",
        "A plate measures 2 m × 3 m and carries 600 N. Find the pressure.",
        "Compute 270 N ÷ 0.00036 m2 in pascal.",
        "Find 0.039 m − 0.0023 m.",
        "A 2 kg ball and twenty metres of rope.",
        "A tank holds 50 litres of oil. 1 litre of water has a mass of 1 kg. Find the mass.",
    ],
)
def test_a_part_no_reader_reads_is_found(text: str) -> None:
    assert unread_in_request(normalize_physics_units(text)) is not None


@pytest.mark.parametrize(
    "text",
    [
        "R1 = 10 Ω and R2 = 20 Ω are in series. Find the total resistance.",
        "Light travels at 3e8 m/s for 2 s. How far?",
        "The temperature falls from 20 °C to −5 °C.",
        "A car speeds up from 5 m/s to 10 m/s in 5 s.",
        "Pump 200 liter of water up 6 m in 2 s. Take 1 liter of water = 1 kg of water.",
    ],
)
def test_a_question_read_whole_has_nothing_unread(text: str) -> None:
    assert unread_in_request(normalize_physics_units(text)) is None


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        # The nine book questions that were verified wrong, now right (or declined below).
        (
            "What is the angle between incident ray and reflected ray if the angle of "
            "incidence is 40°?",
            "80°",
        ),
        (
            "What is the pressure at a depth of 0.76 m in mercury of density 1.36 × 104 kg/m3? "
            "Take g = 10 m/s2.",
            "103360 Pa (gauge)",
        ),
        ("A force of 2 × 103 N acts on an area of 4 m2. What is the pressure?", "500 Pa"),
        (
            "Calculate the power of a pump that can lift 300 liters of water through a "
            "vertical height of 12 m in 8 sec\n(Note that 1 liter of water= 1 kg of water)",
            "4414.5 W",
        ),
        # Their look-alikes, written cleanly, verify as before.
        (
            "What is the angle between the incident ray and the reflected ray if the angle of "
            "incidence is 40°?",
            "80°",
        ),
        ("A force of 2 × 10^3 N acts on an area of 4 m2. What is the pressure?", "500 Pa"),
        (
            "A car starts from rest and accelerates at 2 m/s². What is its velocity after 10 s?",
            None,
        ),
        ("A stone is dropped from rest. What is its velocity after 2 seconds?", None),
        (
            "A body accelerates uniformly from rest at 2m/s2 for 5 seconds. Calculate its "
            "final velocity.",
            "10 m/s",
        ),
        (
            "A car moving at 20 m/s east slows down to 10 m/s east in 5 s. What is its "
            "acceleration?",
            "-2 m/s²",
        ),
        ("A runner does one full lap of a 400 m track in 80 s. What is her average speed?", None),
        # Review: an average a law's result already is, every way a fall is said, the angle
        # of the reflected ray, a litre spelt two ways.
        (
            "A car's velocity changes from 5 m/s to 25 m/s in 10 s. Calculate the average "
            "acceleration.",
            None,
        ),
        ("A charge of 120 C passes a point in 1 minute. Find the average current.", None),
        ("A motor does 6000 J of work in 20 s. What is its average power?", None),
        ("A stone falls freely from rest. What is its velocity after 3 s?", None),
        ("An apple drops from a tree. What is its speed after 0.8 s?", None),
        ("A stone is released from rest from a bridge. What is its speed after 2 s?", None),
        (
            "The angle of incidence on a plane mirror is 35°. What is the angle of the "
            "reflected ray?",
            "35°",
        ),
        (
            "An electric motor pumps 200 L of water to a reservoir of height 6 m in 2 s. Take "
            "1 liter of water = 1 kg of water. Find the power of the motor.",
            None,
        ),
    ],
)
def test_a_question_read_whole_is_answered(text: str, answer: str | None) -> None:
    found = _answer(text)
    assert found is not None
    if answer is not None:
        assert found == answer


@pytest.mark.parametrize(
    "text",
    [
        # Opposite directions, read as two magnitudes: (80 - 16.7)/20 for (-80 - 16.7)/20.
        "A car's velocity changes from 60 km/h north to 80 m/s south in 20 s. What is its "
        "acceleration?",
        "A car moving at 20 m/s east reverses to 10 m/s west in 5 s. What is its acceleration?",
        # An asked average, answered with the final speed (10 m/s for 5).
        "A body accelerates uniformly from rest at 2m/s2 for 5 seconds. Calculate its average "
        "velocity in this time.",
        "A car starts from rest and accelerates at 2 m/s2 for 5 s. What is its average speed?",
        # No fall and no acceleration stated: g is nobody's (-98.1 m/s).
        "A car starts from rest and accelerates. What is its velocity after 10 seconds?",
        "A ball rolls along the floor. What is its velocity after 10 seconds?",
        # A product that is no power of ten.
        "In a 4 × 100 m relay a runner covers his 100 m in 12 s. What is his speed?",
    ],
)
def test_a_part_left_unread_declines(text: str) -> None:
    assert extract_physics_intent(text) is None
    assert _answer(text) is None
