"""The verified answers the 2026-11-13 audit found wrong: each class answers right or declines.

- v = d/t took an amplitude, a period or a wavelength as a distance or a time (PHYS-01);
- known-wrong answers shipped as strict expected failures (PHYS-GAPS);
- a value no such quantity takes was solved (PHYS-03);
- a share that decayed was read as the share left (CHEM-01, physics owns half-lives).

The review of the fix (2026-11-13) found more inside the same classes: a share written as a
fraction or a decimal, an asked share that decayed, a change "by" another verb, a qualified
amplitude, a solved result outside its kind's range, and a wave's speed for a particle's.
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


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        # A share however it is written: 3/4 and 0.75 are what the number reader leaves.
        ("A sample has a half-life of 10 years. How long until 3/4 of it has decayed?",
         "20\\,\\mathrm{years}"),
        ("A sample has a half-life of 10 years. How long until 7/8 of it has decayed?",
         "30\\,\\mathrm{years}"),
        ("How long until 0.75 of the nuclei have decayed? The half-life is 10 years.",
         "20\\,\\mathrm{years}"),
        ("If 1/4 of a sample decays, how long has it been? The half-life is 10 years.",
         "4.15\\,\\mathrm{years}"),
        ("A sample has a half-life of 10 years. How long until it has lost 3/4 of its atoms?",
         "20\\,\\mathrm{years}"),
        ("A sample has a half-life of 10 years. How long until 1/4 of it remains?",
         "20\\,\\mathrm{years}"),
        # An asked share that decayed.
        ("What percentage of a sample has decayed after 2 half-lives?", "75\\,\\%"),
        ("What fraction of a sample has decayed after 3 half-lives?", "0.875"),
        ("How much of a 100 g sample has decayed after 2 half-lives?", "75\\,\\mathrm{g}"),
        ("A sample has a half-life of 10 years. What percentage has decayed after 20 years?",
         "75\\,\\%"),
        ("After 3 half-lives, what percentage of a sample remains?", "12.5\\,\\%"),
        ("A 100 g sample with half-life 5 years. How much is left after 15 years?",
         "12.5\\,\\mathrm{g}"),
        # A change with nothing of its kind before it is the law's own value.
        ("A spring's extension increases by 2 cm when a 4 N load is added. What is the spring "
         "constant?", "200\\,\\mathrm{N/m}"),
        ("The voltage across a 2 μF capacitor increases by 5 V. How much charge flows onto it?",
         "1 \\times 10^{-5}\\,\\mathrm{C}"),
        # Set-aside air resistance, a duration said "a period", crests apart.
        ("A ball is dropped from 80 m with air resistance neglected. How long does it take to "
         "fall?", "4.04\\,\\mathrm{s}"),
        ("Considering air resistance to be negligible, how long does a stone dropped from 20 m "
         "take to fall?", "2.02\\,\\mathrm{s}"),
        ("A cyclist rides at 5 m/s for a short period of 10 s. How far does she go?",
         "50\\,\\mathrm{m}"),
        ("Ocean waves have a period of 4 s and the crests are 20 m apart. What is the wave "
         "speed?", "5\\,\\mathrm{m/s}"),
        # A diverging lens: a size and a side (owner, 2026-11-13).
        ("An object is 20 cm from a diverging lens of focal length -10 cm. Find the image "
         "distance.", "6.67\\,\\mathrm{cm}\\ (\\text{virtual, on the object's side of the lens})"),
        ("An object is 20 cm from a concave lens of focal length 10 cm. Find the image "
         "distance.", "6.67\\,\\mathrm{cm}\\ (\\text{virtual, on the object's side of the lens})"),
        ("An object is placed 30 cm from a concave lens of focal length 15 cm. What is the "
         "magnification?", "0.333\\ (\\text{upright and smaller})"),
        ("An object is 30 cm from a convex lens of focal length 10 cm. Find the image distance.",
         "15\\,\\mathrm{cm}"),
        # Once declined for its sign, a diverging lens however worded (owner, 2026-11-13).
        ("An object 30 cm from a concave thin lens of focal length 15 cm. Find the image "
         "distance.", "10\\,\\mathrm{cm}\\ (\\text{virtual, on the object's side of the lens})"),
        ("The lens is concave. An object is placed 30 cm from it and its focal length is 15 cm. "
         "Find the image distance.",
         "10\\,\\mathrm{cm}\\ (\\text{virtual, on the object's side of the lens})"),
        ("An object is 30 cm from a biconcave lens of focal length 15 cm. Find the image "
         "distance.", "10\\,\\mathrm{cm}\\ (\\text{virtual, on the object's side of the lens})"),
        ("An object is placed 30 cm from a minus lens of focal length 15 cm. Find the image "
         "distance.", "10\\,\\mathrm{cm}\\ (\\text{virtual, on the object's side of the lens})"),
        ("what is the image distance for a diverging lens of focal length 10 cm and object at "
         "30 cm", "7.5\\,\\mathrm{cm}\\ (\\text{virtual, on the object's side of the lens})"),
        ("An object is 30 cm from a concave lens with focal length 10 cm. Where is the image "
         "and how big is it?", "7.5\\,\\mathrm{cm}\\ (\\text{virtual, on the object's side of "
         "the lens});\\quad 0.25\\ (\\text{upright and smaller})"),
    ],
)  # fmt: skip
def test_the_reviewed_class_answers_right(text: str, answer: str) -> None:
    assert _answer(text) == answer


@pytest.mark.parametrize(
    "text",
    [
        # A change of a stated value is no end of it.
        "A car moving at 20 m/s reduces its speed by 5 m/s in 2 s. What is its deceleration?",
        "A car moving at 10 m/s picks up speed by 6 m/s in 3 s. What is its acceleration?",
        "A cyclist moving at 4 m/s accelerates by 2 m/s over 4 s. What is her acceleration?",
        "A gas at 27 °C and 100 kPa is heated through 100 °C at constant volume. What is the new "
        "pressure?",
        "The temperature of a gas at 300 K and 2 L is raised by 150 K at constant pressure. What "
        "is the new volume?",
        "A gas at 400 K and 2 L has its temperature lowered by 100 K at constant pressure. What "
        "is its new volume?",
        "A gas at 20 °C and 1 atm in a sealed can is heated by 80 °C. What is the new pressure?",
        # A qualified amplitude, and a condition that scales a given.
        "A mass oscillates with a peak-to-peak amplitude of 0.2 m and a period of 2 s. What is "
        "its maximum speed?",
        "A mass oscillates with an amplitude of 0.1 m and a period of 2 s. If the amplitude is "
        "doubled, what is its maximum speed?",
        # A solved result no such quantity takes.
        "A force of -10 N gives an acceleration of 2 m/s^2. What is the mass?",
        "A potential difference of -6 V drives a current of 2 A. What is the resistance?",
        # A particle's speed is no wave's.
        "A wave has a wavelength of 2 m and a period of 0.5 s. What is the maximum speed of a "
        "particle in the medium?",
        "A wave on a string has a wavelength of 2 m and a period of 0.5 s. How fast does a point "
        "on the string move?",
        # A lens not said to diverge, with an image distance stated, is not read as one.
        "An object is 30 cm from a lens and forms a virtual image 60 cm from the lens. Find the "
        "magnification.",
        # p = mv is classical, and a convex mirror's sign is a convention.
        "A proton moves at 2.9e8 m/s. What is its momentum? (mass 1.67e-27 kg)",
        "An object is 20 cm from a convex mirror of focal length 10 cm. Find the image distance.",
    ],
)
def test_the_reviewed_class_declines(text: str) -> None:
    assert _answer(text) is None


_VIRTUAL = "\\text{virtual, on the object's side of the lens}"


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        # Second review: a diverging lens only when the lens itself is called one.
        ("A lens of focal length -10 cm has an object 20 cm away. Where is the image?",
         f"6.67\\,\\mathrm{{cm}}\\ ({_VIRTUAL})"),
        ("A Galilean telescope eyepiece is a concave lens of focal length 5 cm. An object is 20 "
         "cm from it. Where is the image?", f"4\\,\\mathrm{{cm}}\\ ({_VIRTUAL})"),
        # A negated decay is the share left; "undecayed" too.
        ("What fraction of the sample has not decayed after 3 half-lives?", "0.125"),
        ("What fraction of the sample has not yet decayed after 3 half-lives?", "0.125"),
        ("What percentage of the nuclei are yet to decay after 2 half-lives?", "25\\,\\%"),
        ("What fraction of the original nuclei remain undecayed after 3 half-lives?", "0.125"),
        # Air resistance set aside however it is said.
        ("A ball is dropped from 45 m with air resistance taken as zero. How long does it take "
         "to fall?", "3.03\\,\\mathrm{s}"),
        ("A ball is dropped from 45 m. Air resistance can be ignored. How long does it take to "
         "fall?", "3.03\\,\\mathrm{s}"),
        ("A ball is dropped from 45 m without air resistance. How long does it take to fall?",
         "3.03\\,\\mathrm{s}"),
    ],
)  # fmt: skip
def test_the_second_review_answers_right(text: str, answer: str) -> None:
    assert _answer(text) == answer


@pytest.mark.parametrize(
    "text",
    [
        # A converging lens's virtual image, or diverging light, is no diverging lens.
        "A convex lens of focal length 10 cm forms a virtual image of an object placed 5 cm from "
        "it. Where is the image?",
        "A magnifying glass is a converging lens of focal length 10 cm. It forms a virtual image "
        "of an object 6 cm away. Find the image distance.",
        "Light diverging from a point source 30 cm in front of a converging lens of focal length "
        "10 cm is focused. Where is the image?",
        "Rays diverging from an object 40 cm from a convex lens of focal length 10 cm are brought "
        "to a focus. Find the image distance.",
        # An ask that is not the diverging lens's image distance or magnification.
        "A concave lens has a focal length of 25 cm. An object is 50 cm away. What is the power "
        "of the lens?",
        "A concave lens of focal length 20 cm has an object 30 cm away. What is the focal length "
        "in metres?",
        "A diverging lens of focal length 10 cm has an object 20 cm away. What is the image "
        "distance from the object?",
        "A concave lens of focal length 10 cm has an object 20 cm away. Where is the image if the "
        "lens is replaced by a convex lens of the same focal length?",
        # Air resistance said to act, and a change that reads two ways.
        "A ball is dropped from 45 m with air resistance not neglected. How long does it take to "
        "fall?",
        "A steel rod 2 m long is heated from 20 °C through 50 °C. α = 1.2e-5 /K. How much does it "
        "expand?",
    ],
)
def test_the_second_review_declines(text: str) -> None:
    assert _answer(text) is None
