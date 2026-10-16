"""The arithmetic in working the model wrote itself is recomputed, never guessed at."""

from __future__ import annotations

import pytest

from app.services.working_check import is_worked_solution, working_note, wrong_steps


@pytest.mark.parametrize(
    ("reply", "slip"),
    [
        # A slip, with or without units around the numbers.
        ("$3.2 \\times 4.5 = 14.8$", ("3.2 \\times 4.5", "14.8")),
        (
            "$v = 3\\,\\text{m/s}^2 \\times 5\\,\\text{s} = 18\\,\\text{m/s}$",
            ("3\\,\\text{m/s}^2 \\times 5\\,\\text{s}", "18\\,\\text{m/s}"),
        ),
        ("$2(8) + 5 = 22$", ("2(8) + 5", "22")),
        (
            "$6.02 \\times 10^{23} \\times 2 = 1.5 \\times 10^{24}$",
            ("6.02 \\times 10^{23} \\times 2", "1.5 \\times 10^{24}"),
        ),
        ("$1,500 \\times 2 = 3,100$", ("1,500 \\times 2", "3,100")),
        ("$\\frac{12}{4} = 4$", ("\\frac{12}{4}", "4")),
    ],
)
def test_wrong_steps_finds_a_slip(reply: str, slip: tuple[str, str]) -> None:
    steps = wrong_steps(reply)
    assert [(step.left, step.shown) for step in steps] == [slip]


@pytest.mark.parametrize(
    "reply",
    [
        # Right, or rounded as a student would round.
        "$3.2 \\times 4.5 = 14.4$",
        "$9.81 \\times 2.02 = 19.8$",
        "$v = \\sqrt{2 \\times 9.81 \\times 20} = 19.8\\,\\text{m/s}$",
        "$t = \\frac{2 \\times 20}{9.81} \\approx 4.1$",
        "$\\frac{1000}{3} = 333$",
        "$6.02 \\times 10^{23} \\times 2 = 1.204 \\times 10^{24}$",
        "$E = 3.98\\times10^{-19} / 1.602\\times10^{-19} = 2.48$",
        # Not arithmetic: a variable, a unit conversion, a prefix step, a word between.
        "$2x + 5 = 21$",
        "$7200 \\text{ m} = 7.2\\,\\text{km}$",
        "$2 \\times 2.26\\times10^6\\,\\text{J} = 4.5\\,\\text{MJ}$",
        "$mL = 2 \\times 2.26\\times10^6 \\approx 4.5$ MJ",
        "$x = 2 \\text{ and } (3)^{2} - 5 (3) + 6 = 0$",
        "$15\\% \\text{ of } 80 = 12$",
        "$\\sin 30^\\circ = 0.5$",
        "$x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$",
        # A power too big to compute, inline code and a code block.
        "$2^{1000000} = 5$",
        "Type `$2 + 2 = 5$` to see the error.",
        "```python\nprint('$2 + 2 = 5$')\n```",
    ],
)
def test_wrong_steps_leaves_right_or_unreadable_working(reply: str) -> None:
    assert wrong_steps(reply) == []


def test_working_note_names_the_first_slip_in_its_own_units() -> None:
    reply = (
        "**Substitution**\n$a = 3\\,\\text{m/s}^2 \\times 5\\,\\text{s} = 18\\,\\text{m/s}$\n"
        "$s = 18 \\times 2 = 37$\n\n**Answer**\n$s = 37\\ \\text{m}$"
    )
    assert working_note(reply) == (
        "Check this step: $3\\,\\text{m/s}^2 \\times 5\\,\\text{s} = 15\\,\\text{m/s}$, "
        "not $18\\,\\text{m/s}$. The lines after it depend on it."
    )


def test_working_note_rounds_a_tie_up_as_a_class_does() -> None:
    # 0.5 * 0.25 is 0.125: to the two places shown, 0.13, not the 0.12 of ties-to-even.
    assert working_note("$0.5 \\times 0.25 = 0.15$") == (
        "Check this step: $0.5 \\times 0.25 = 0.13$, not $0.15$. The lines after it depend on it."
    )


def test_working_note_is_none_when_the_working_adds_up() -> None:
    assert working_note("**Answer**\n$3 \\times 5 = 15$") is None


@pytest.mark.parametrize(
    ("reply", "worked"),
    [
        ("**Given**\n$m = 2$\n\n**Answer**\n$4$", True),
        ("**1. Subtract 5 from both sides**\n$2x = 12$", True),
        ("Is $3 \\times 4 = 13$? No, it's 12.", False),
    ],
)
def test_is_worked_solution(reply: str, worked: bool) -> None:
    assert is_worked_solution(reply) is worked
