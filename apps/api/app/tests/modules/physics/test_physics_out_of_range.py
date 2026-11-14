"""Why physics declined a question whose values no real case has (``out_of_range``).

"A 10 V battery is connected across a -5 Ω resistor. What current flows?" declined, and the
model, told only that nothing verified, answered -2 A without a word about the resistor
(live round, 2026-11-14). A stated value outside its quantity's range is the question's
fault, said for certain; a result outside it depends on the signs as read, so it is a reason
to check them. A negative velocity, charge or acceleration breaks no rule.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics.out_of_range import result_out_of_range, stated_out_of_range
from app.modules.physics.prompt import solve_or_say_why

_SETTINGS = Settings(math_tools_enabled=True)


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (
            "A 10 V battery is connected across a -5 Ω resistor. What current flows?",
            "A resistance cannot be zero or negative, and the question gives -5 Ω.",
        ),
        (
            "A -3 kg box is pushed with a net force of 12 N. What is its acceleration?",
            "A mass cannot be zero or negative, and the question gives -3 kg.",
        ),
        (
            "A gas at -300 °C and 100 kPa has a volume of 2 L. How many moles?",
            "No temperature is at or below absolute zero (-273.15 °C), and the question "
            "gives -300 °C.",
        ),
        (
            "A car moves at 4 x 10^8 m/s for 10 s. How far does it go?",
            "Nothing moves faster than light, and the question gives 4 × 10⁸ m/s.",
        ),
        (
            "A wave has a wavelength of -2 m and a frequency of 5 Hz. What is its speed?",
            "A wavelength cannot be zero or negative, and the question gives -2 m.",
        ),
        (
            "A 2 kg mass on a spring of constant -50 N/m. What is the period?",
            "A spring constant cannot be zero or negative, and the question gives -50 N/m.",
        ),
        # An oscillation's amplitude is its own input, named for what it is.
        (
            "A spring oscillates with an amplitude of -0.1 m and a period of 2 s. "
            "What is its maximum speed?",
            "An amplitude cannot be zero or negative, and the question gives -0.1 m.",
        ),
    ],
)
def test_a_stated_value_out_of_range_is_named(text: str, reason: str) -> None:
    assert stated_out_of_range(text) == reason
    _outcome, block, no_answer = solve_or_say_why(text, _SETTINGS, None)
    assert block is None and no_answer is not None and no_answer.stated
    assert reason in no_answer.note


@pytest.mark.parametrize(
    "text",
    [
        # Signed quantities keep their sign.
        "A ball is thrown at -20 m/s. What is its kinetic energy if its mass is 2 kg?",
        "A charge of -3 μC sits 0.2 m from a charge of 5 μC. What is the force between them?",
        "An electron with charge -1.6e-19 C moves through a potential difference of 100 V. "
        "How much energy does it gain?",
        "A 2 kg box slides with a velocity of -3 m/s. What is its momentum?",
        "A car accelerates from 20 m/s to 10 m/s in 5 s. What is its acceleration?",
        # A temperature below freezing and light's own speed are values they can take.
        "A 2 kg block of ice at -10 °C warms to 0 °C. How much heat does it take? "
        "The specific heat of ice is 2100 J/(kg·K).",
        "Light travels at 3 x 10^8 m/s. How long does it take to travel 300 km?",
        # A decline for another reason states nothing out of range.
        "A ball is thrown upward at -20 m/s. How high does it go?",
    ],
)
def test_a_value_its_quantity_can_take_gives_no_reason(text: str) -> None:
    assert stated_out_of_range(text) is None
    assert result_out_of_range(text) is None
    assert solve_or_say_why(text, _SETTINGS, None)[2] is None


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (
            "A force of -10 N gives a mass an acceleration of 2 m/s². What is the mass?",
            "Read with the signs as written, the stated values give -5 kg, and a mass cannot "
            "be zero or negative.",
        ),
        # A braking force given as a size beside a deceleration written negative: the note
        # asks the reply to check the signs, never calls the question impossible.
        (
            "A car decelerates at -2.5 m/s² under a braking force of 3000 N. What is its mass?",
            "Read with the signs as written, the stated values give -1200 kg, and a mass "
            "cannot be zero or negative.",
        ),
    ],
)
def test_a_result_out_of_range_asks_for_the_signs_checked(text: str, reason: str) -> None:
    assert stated_out_of_range(text) is None
    assert result_out_of_range(text) == reason
    _outcome, _block, no_answer = solve_or_say_why(text, _SETTINGS, None)
    assert no_answer is not None and not no_answer.stated
    assert reason in no_answer.note and "Physics sign check" in no_answer.note
