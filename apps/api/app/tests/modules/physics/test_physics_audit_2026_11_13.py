"""The verified answers the 2026-11-13 audit found wrong: each class answers right or declines.

- v = d/t took an amplitude, a period or a wavelength as a distance or a time (PHYS-01);
- known-wrong answers shipped as strict expected failures (PHYS-GAPS);
- a value no such quantity takes was solved (PHYS-03);
- a share that decayed was read as the share left (CHEM-01, physics owns half-lives).
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics.followup import physics_followup_problem
from app.modules.physics.prompt import solve_physics_request

_SETTINGS = Settings(math_tools_enabled=True)


def _answer(text: str) -> str | None:
    outcome, block = solve_physics_request(text, _SETTINGS, None)
    return block.display_answer if outcome == "verified" and block is not None else None


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        # PHYS-01: the forms of v_max = Aω, and λ/T.
        (
            "A mass on a spring oscillates with an amplitude of 0.1 m and a period of 2 s. "
            "What is its maximum speed?",
            "0.314\\,\\mathrm{m/s}",
        ),
        (
            "A body in SHM has amplitude 0.1 m and frequency 0.5 Hz. Find its maximum speed.",
            "0.314\\,\\mathrm{m/s}",
        ),
        (
            "A piston moves in SHM with an amplitude of 5 cm and a period of 0.02 s. "
            "What is its top speed?",
            "15.7\\,\\mathrm{m/s}",
        ),
        (
            "A tuning fork prong vibrates with amplitude 1 mm and period 2 ms. "
            "What is the prong's maximum speed?",
            "3.14\\,\\mathrm{m/s}",
        ),
        (
            "A mass on a spring oscillates with an amplitude of 0.1 m and a period of 2 s. "
            "What is its maximum acceleration?",
            "0.987\\,\\mathrm{m/s²}",
        ),
        (
            "A tsunami has a wavelength of 200 km and a period of 15 minutes. "
            "How fast does it travel?",
            "222\\,\\mathrm{m/s}",
        ),
        ("A runner moves 0.1 m in 2 s. What is her speed?", "0.05\\,\\mathrm{m/s}"),
        ("A car covers 100 m over a period of 5 s. What is its speed?", "20\\,\\mathrm{m/s}"),
        # CHEM-01: a share gone leaves 1 - p.
        (
            "How long does it take for 75% of a radioactive sample to decay if its half-life "
            "is 10 years?",
            "20\\,\\mathrm{years}",
        ),
        (
            "How long for 75% of a first-order reactant to decompose? The half-life is 12 min.",
            "24\\,\\mathrm{min}",
        ),
        (
            "A sample has a half-life of 10 years. How long until it loses 75% of its activity?",
            "20\\,\\mathrm{years}",
        ),
        (
            "A sample has a half-life of 10 years. How long until 25% remains?",
            "20\\,\\mathrm{years}",
        ),
        (
            "A sample has a half-life of 10 years. How long until 75% of the sample is left?",
            "4.15\\,\\mathrm{years}",
        ),
        # PHYS-GAPS: an average speed is no final speed.
        (
            "Starting from rest, a car reaches an average speed of 12 m/s over 30 s. "
            "How far did it go?",
            "360\\,\\mathrm{m}",
        ),
        # Look-alikes that must keep answering.
        (
            "Ignoring air resistance, a ball is dropped from 20 m. "
            "What is its speed when it hits the ground?",
            "19.8\\,\\mathrm{m/s}",
        ),
        ("A 70 kg astronaut stands on the Moon. What is her weight?", "113.4\\,\\mathrm{N}"),
    ],
)
def test_the_class_answers_right(text: str, answer: str) -> None:
    assert _answer(text) == answer


@pytest.mark.parametrize(
    "text",
    [
        # PHYS-01: under-specified, never d/t.
        "A wave has an amplitude of 0.1 m and a period of 2 s. What is its speed?",
        "A pendulum 1 m long has a period of 2 s. What is the bob's speed?",
        "A mass on a spring oscillates with an amplitude of 0.1 m for 10 s. "
        "What is its maximum speed?",
        # PHYS-GAPS: each was a wrong verified number.
        "An object weighs 50 N on Earth. What is its mass on the Moon?",
        "An astronaut has a mass of 70 kg on the Moon. What is her weight on Earth?",
        "A ball is thrown straight up at 20 m/s. How long does it take to first reach a height "
        "of 15 m?",
        "A ball is thrown horizontally at 10 m/s from a 20 m high cliff. "
        "What is its speed after 1 s?",
        "A ball is kicked horizontally at 15 m/s from a 30 m cliff. "
        "What is its vertical velocity after 2 s?",
        "A car travelling at 10 m/s increases its speed by 10 m/s in 5 s. "
        "What is its acceleration?",
        "A ball is dropped from 20 m and air resistance is significant. "
        "What is its speed when it hits the ground?",
        "A car travels at a constant speed of 20 m/s for 5 s and covers 200 m. What is its speed?",
        "A ball dropped from 20 m hits the ground at 30 m/s. How long does it take to fall?",
        # PHYS-03: no such quantity.
        "A −4 Ω resistor is connected across 12 V. What current flows?",
        "A resistor of -5 Ω is connected to a 10 V battery. What current flows?",
        "A box with a mass of 0 kg is pushed with a force of 20 N. What is its acceleration?",
        "A car of mass 1000 kg moves at 400000000 m/s. What is its kinetic energy?",
        # CHEM-01: a share the words call neither.
        "A sample has a half-life of 10 years. How long for 75% of the sample?",
    ],
)
def test_the_class_declines(text: str) -> None:
    assert _answer(text) is None


def test_a_follow_up_that_changes_the_motion_is_no_new_problem() -> None:
    recent = [
        {"role": "user", "content": "A car travels at a constant speed of 20 m/s for 5 seconds. "
         "How far does it travel?"},
        {"role": "assistant", "content": "**Answer** s = 100 m"},
    ]  # fmt: skip
    assert physics_followup_problem("What if it takes 10 s to stop instead?", recent) is None
    assert physics_followup_problem("what if it was 30 m/s?", recent) is not None
