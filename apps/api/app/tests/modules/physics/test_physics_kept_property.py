"""A follow-up that changes what is done to a component keeps the component's constant."""

from __future__ import annotations

import pytest

from app.modules.physics.followup import physics_followup_problem
from app.modules.physics.subject import solved_text
from app.modules.physics.verified_answers import plain_number, results
from app.tests.modules.physics.test_physics_binding import _answer

_RESISTOR = "A 12 V battery drives a current of 2 A through a resistor. Find the resistance."
_CAPACITOR = "A capacitor stores 6e-4 C at 12 V. Find its capacitance."
_SPRING = "A spring stretches 0.05 m under a 5 N force. Find the spring constant."


def _recent(prior: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": prior}, {"role": "assistant", "content": "done"}]


# Each answer worked by hand from the constant the first problem found.
@pytest.mark.parametrize(
    ("prior", "line", "problem", "answer"),
    [
        (
            _RESISTOR,
            "what if the voltage doubled?",
            "A resistance of 6 Ω and a voltage of 24 V. Find the current.",
            "4 A",
        ),
        (
            _RESISTOR,
            "what if the current was halved?",
            "A resistance of 6 Ω and a current of 1 A. Find the voltage.",
            "6 V",
        ),
        (
            _SPRING,
            "what if the force doubled?",
            "A spring constant of 100 N/m and a force of 10 N. Find the extension.",
            "0.1 m",
        ),
        # The capacitor laws need the object named; the problem names it.
        (
            _CAPACITOR,
            "what if the voltage doubled?",
            "A capacitor with a capacitance of 5e-05 F and a voltage of 24 V. Find the charge.",
            "0.0012 C",
        ),
        (
            _CAPACITOR,
            "what if the charge doubled?",
            "A capacitor with a capacitance of 5e-05 F and a charge of 0.0012 C. Find the voltage.",
            "24 V",
        ),
    ],
)
def test_a_change_to_a_component_is_asked_with_its_constant_kept(
    prior: str, line: str, problem: str, answer: str
) -> None:
    assert physics_followup_problem(line, _recent(prior)) == problem
    assert _answer(problem) == answer


@pytest.mark.parametrize(
    ("prior", "line"),
    [
        # The constant itself changed: nothing is held.
        (_RESISTOR, "what if the resistance doubled?"),
        # A rated device: twice the voltage on a 60 W bulb is no 60 W bulb.
        ("A 60 W bulb runs on 120 V. Find its resistance.", "what if the voltage doubled?"),
        # A source's emf and internal resistance are what the change would hold wrongly.
        (
            "A cell of emf 12 V and internal resistance 0.5 ohm drives 2 A. "
            "Find the external resistance.",
            "what if the current doubled?",
        ),
        # A material's density: "twice the mass" may be more of it or another material.
        ("A 2 kg block has a volume of 0.001 m^3. Find its density.", "what if the mass doubled?"),
        # A medium's refractive index: a new speed is a new medium.
        (
            "Light travels at 2e8 m/s in glass. Find the refractive index of the glass.",
            "what if the speed was halved?",
        ),
        # Components whose resistance changes with what drives them hold none.
        (
            "A filament lamp draws 2 A from a 12 V supply. Find its resistance.",
            "what if the voltage doubled?",
        ),
        ("An LED draws 0.02 A at 2 V. Find its resistance.", "what if the voltage doubled?"),
        (
            "A thermistor carries 0.002 A at 6 V. Find its resistance.",
            "what if the voltage doubled?",
        ),
        (
            "A light bulb draws 0.5 A at 230 V. Find its resistance.",
            "what if the voltage was halved?",
        ),
        # A heat capacity's law has three givens, not a constant and two that move together.
        (
            "4000 J of heat raises the temperature of 1 kg of a metal by 10 K. "
            "Find the specific heat capacity.",
            "what if the heat doubled?",
        ),
    ],
)
def test_a_change_that_holds_no_component_constant_declines(prior: str, line: str) -> None:
    assert physics_followup_problem(line, _recent(prior)) is None


@pytest.mark.parametrize(
    ("line", "solved"),
    [
        # A change: the reply is the rewritten problem's working, written by the server.
        ("what if the voltage doubled?", "the follow-up problem"),
        ("in km/h please", "the follow-up problem"),
        ("and after 10 s?", "the follow-up problem"),
        # More than the rewritten problem answers: the model writes it with the result.
        ("and after 10 s, in km/h?", "and after 10 s, in km/h?"),
        ("and after 10 s? why?", "and after 10 s? why?"),
        ("what if it was 3 m/s^2? explain why", "what if it was 3 m/s^2? explain why"),
        ("and after 10 s? compare with before", "and after 10 s? compare with before"),
        # A question about the working: the model explains it, nothing is written again.
        ("why?", "why?"),
        ("how did you get that?", "how did you get that?"),
    ],
)
def test_the_server_writes_the_follow_up_it_solved_but_not_an_explanation(
    line: str, solved: str
) -> None:
    assert solved_text(line, "the follow-up problem") == solved


def test_a_line_with_no_follow_up_problem_is_its_own_text() -> None:
    assert solved_text("A 2 kg ball falls 5 m. Find its speed.", None) == (
        "A 2 kg ball falls 5 m. Find its speed."
    )


@pytest.mark.parametrize(
    ("written", "plain"),
    [
        ("5 × 10⁻⁵ F", "5e-5 F"),
        ("1.2 × 10^-3 C", "1.2e-3 C"),
        ("3 × 10^(8) m/s", "3e8 m/s"),
        ("2.5 × 10¹² Hz", "2.5e12 Hz"),
        ("6 Ω", "6 Ω"),
    ],
)
def test_a_card_number_with_a_power_of_ten_reads_as_one_number(written: str, plain: str) -> None:
    assert plain_number(written) == plain


def test_a_change_in_another_unit_scales_by_its_si_value() -> None:
    # 2 A to 500 mA is a quarter: the 6 Ω resistor then has 3 V across it.
    problem = physics_followup_problem("with 500 mA instead", _recent(_RESISTOR))
    assert problem is not None
    assert _answer(problem) == "3 V"


def test_a_capacitance_result_reads_with_its_power_of_ten() -> None:
    found = results(_CAPACITOR)
    assert found is not None
    assert [(given.value, given.unit) for given in found] == [(5e-5, "F")]
