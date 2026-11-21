"""The arithmetic in working the model wrote itself is recomputed, never guessed at."""

from __future__ import annotations

import pytest

from app.modules.chat.working_check import (
    corrected_approximations,
    is_worked_solution,
    working_note,
    wrong_steps,
)
from app.modules.chat.working_systems import unheld_equations


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


# A Grade 10 long-jump answer (2026-10-30): t = 3.5/9.8 = 0.36 s, then 2 x 0.36 = 0.71 s
# with the unrounded 0.357 carried. Flagged "0.72, not 0.71", it told a student a right
# answer was broken.
def test_a_line_built_on_a_rounded_result_carries_its_rounding() -> None:
    reply = "$t = \\frac{3.5}{9.8}$\n$t = 0.36\\ \\text{s}$\n\n$t_{flight} = 2 \\times 0.36 = 0.71$"
    assert wrong_steps(reply) == []


@pytest.mark.parametrize(
    "reply",
    [
        # A given is exact as written: only an earlier result is rounded.
        "$3.2 \\times 4.5 = 14.8$",
        # The earlier result's rounding is not enough to reach a real slip.
        "$t = 0.36$\n$2 \\times 0.36 = 0.75$",
        "$x = 4.5$\n$3.2 \\times 4.5 = 14.8$",
    ],
)
def test_a_slip_beyond_the_carried_rounding_is_still_one(reply: str) -> None:
    assert wrong_steps(reply)


# Review: a given is exact, and so is an exact result; only a rounded one carries slack.
@pytest.mark.parametrize(
    "reply",
    [
        "**Given** $m = 3.2\\ \\text{kg}$ $a = 4.5$ $F = 3.2 \\times 4.5 = 14.8$",
        "**Given** $I = 0.2\\ \\text{A}$ $R = 12 / 0.2 = 55$",
        "$I = 6/30 = 0.2$ then $R = 12/0.2 = 55$",
        "$v = 2.5$ $KE = 0.5 \\times 4 \\times 2.5^2 = 13.0$",
    ],
)
def test_a_given_or_exact_result_carries_no_rounding(reply: str) -> None:
    assert wrong_steps(reply)


def test_a_name_solved_then_rounded_carries_its_rounding() -> None:
    reply = "$t = \\frac{3.5}{9.8}$\n$t = 0.36\\ \\text{s}$\n$t_{f} = 2 \\times 0.36 = 0.71$"
    assert wrong_steps(reply) == []


# Second review: a step is checked against the exact value an earlier rounded result had,
# and a result is rounded only when it is within half its last place of that value.
@pytest.mark.parametrize(
    "reply",
    [
        "$t = \\frac{3.5}{9.8} = 0.357 \\approx 0.36$ then $2 \\times 0.36 = 0.71$",
        "$t = \\frac{3.5}{9.8} = 0.357$\n$= 0.36$ then $2 \\times 0.36 = 0.71$",
    ],
)
def test_a_rounding_chain_carries_its_exact_value(reply: str) -> None:
    assert wrong_steps(reply) == []


@pytest.mark.parametrize(
    "reply",
    [
        # 36 on the shown 0.3, 34.3 on the exact 2/7: 40 is neither.
        "$t = 2/7 = 0.3$ then $d = 120 \\times 0.3 = 40$",
        "$x = 1/3 = 0.3$ then $1000 \\times 0.3 = 349$",
        # A name reused in a later part holds a new value, not a rounding of the old one.
        "$I = \\frac{6}{20}$ $I = 0.3$ part b $I = 0.2$ then $R = 12/0.2 = 55$",
    ],
)
def test_a_slip_on_a_rounded_result_is_still_one(reply: str) -> None:
    assert wrong_steps(reply)


# Third review: only a decimal result is carried, never a whole number or an exponent, and
# a later given with the same digits is that given.
@pytest.mark.parametrize(
    "reply",
    [
        "$n = 9/4 = 2$ then $m = 2\\ \\text{kg}$ $F = 2 \\times 4.5 = 10$",
        "$n = 9/4 = 2$ then $0.5 \\times 4 \\times 3^2 = 23.7$",
        "$t = 1/3 = 0.3$ part b $\\mu = 0.3$ then $0.3 \\times 50 = 16.7$",
    ],
)
def test_a_carried_value_stays_with_its_own_result(reply: str) -> None:
    assert wrong_steps(reply)


# Live, 2026-11-21: hard geometry replies whose working slipped where the old check could
# not see (a root, a function of degrees, a name worked out on two lines, an exact form).
@pytest.mark.parametrize(
    ("reply", "left", "value"),
    [
        (
            "**Substitution**\n$L = \\frac{1}{21} \\sqrt{(6)(14)(28)(48)}$\n"
            "$L = \\frac{1}{21} \\sqrt{279552}$\n$L = \\frac{1}{21} \\times 528.915$",
            "\\frac{1}{21} \\sqrt{(6)(14)(28)(48)}",
            16.0,
        ),
        (
            "$\\text{Area}(ABC) = \\sqrt{11375}$\n$\\text{Area}(ABC) = 25\\sqrt{73}\\ \\text{cm}^2$",
            "\\sqrt{11375}",
            106.6536,
        ),
        ("$a = 10 \\sin 30° \\times 2 = 12$", "10 \\sin 30° \\times 2", 10.0),
        ("$A = \\pi (6)^2 = 112$", "\\pi (6)^2", 113.0973),
    ],
)
def test_a_slip_through_a_root_a_sine_or_a_name_s_next_line_is_found(
    reply: str, left: str, value: float
) -> None:
    steps = wrong_steps(reply)
    assert steps and steps[0].left == left and steps[0].value == pytest.approx(value, rel=1e-4)


@pytest.mark.parametrize(
    "reply",
    [
        "$x = \\frac{4 + 2}{2}$\n$x = 3$\n$x = \\frac{4 - 2}{2}$\n$x = 1$",
        "$x = 1$\n$x = 3$",
        # Two statements in one line, then each alone (live, 2026-11-21: "√36 = 6, not 10").
        "$l_{maj} = 2(10) = 20, l_{min} = 2(6) = 12$\n$l_{maj} = 20$\n$l_{min} = 12$",
        # Two roots as expressions on consecutive lines (review, #2520).
        "$x = \\frac{4 + 2}{2}$\n$x = \\frac{4 - 2}{2}$",
        "$x = \\frac{-b \\pm \\sqrt{16}}{2}$\n$x = \\frac{6 + 4}{2}$",
        "$m_b = \\frac{1}{2}\\sqrt{592}$\n$m_b = \\frac{1}{2}\\sqrt{16 \\times 37}$\n$m_b = 2\\sqrt{37}$",
        "$h = 40 \\tan 35° = 28.01$ m",
        "$A = 36\\pi$\n$A \\approx 113.10$",
        "$R = \\frac{17 \\times 25 \\times 28}{4 \\times 210} = \\frac{85}{6}$",
        # A unit converted, and a constant substituted (physics, live 2026-11-21).
        "$7.35981 \\times 10^{-20}\\,\\mathrm{J} = 0.459363\\,\\mathrm{eV}$",
        "$d = 0.98\\,\\mathrm{c} \\times 11.056\\,\\mathrm{\\mu s} = 0.98 \\times 299,792,458\\,"
        "\\mathrm{m/s} \\times 11.056 \\times 10^{-6}\\,\\mathrm{s}$",
    ],
)
def test_working_that_adds_up_is_never_flagged(reply: str) -> None:
    assert wrong_steps(reply) == []


@pytest.mark.parametrize(
    ("reply", "fixed"),
    [
        (
            "is **$\\frac{\\sqrt{65}}{8}\\ \\text{cm}$** (approximately **0.999 cm**).",
            "is **$\\frac{\\sqrt{65}}{8}\\ \\text{cm}$** (approximately **1.008 cm**).",
        ),
        (
            "**$2(\\sqrt{10} + \\sqrt{13} + \\sqrt{17})$ units** (approximately **19.13 units**)",
            "**$2(\\sqrt{10} + \\sqrt{13} + \\sqrt{17})$ units** (approximately **21.78 units**)",
        ),
        (
            "**$2\\sqrt{37}\\ \\text{cm}$** (approx. $12.16\\ \\text{cm}$)",
            "**$2\\sqrt{37}\\ \\text{cm}$** (approx. $12.17\\ \\text{cm}$)",
        ),
    ],
)
def test_a_decimal_given_for_an_exact_value_is_written_right(reply: str, fixed: str) -> None:
    assert corrected_approximations(reply) == fixed


@pytest.mark.parametrize(
    "reply",
    [
        "**$2\\sqrt{30}$ cm** (approx. **10.95 cm**)",
        "$84 - 16\\pi$ cm² (approximately $33.73$ cm²)",
        "$x = 7.32$ (approximately 7.3)",
        "```text\n$\\sqrt{2}$ (approximately 9.9)\n```",
    ],
)
def test_a_right_decimal_or_one_of_a_rounded_value_stays(reply: str) -> None:
    assert corrected_approximations(reply) == reply


_KIRCHHOFF = (
    "**Substitution**\n$10 - 2I_1 - 6(I_1 + I_2) = 0$\n$8I_1 + 6I_2 = 10$\n"
    "$6 - 4I_2 - 6(I_1 + I_2) = 0$\n$6I_1 + 10I_2 = 6$\n"
    "$I_1 = \\frac{15}{13} A$\n$I_2 = \\frac{1}{13} A$\n**Answer**\n"
)


def test_values_that_do_not_satisfy_the_reply_s_own_equations_are_named() -> None:
    """Live (2026-11-21): two batteries in parallel, the equations right and the values
    15/13 A and 1/13 A satisfying neither (they are 1.45 A and -0.27 A)."""
    unheld = unheld_equations(_KIRCHHOFF)
    assert unheld and unheld[0].values == pytest.approx({"I_1": 15 / 13, "I_2": 1 / 13})
    note = working_note(_KIRCHHOFF)
    assert note is not None and "do not satisfy" in note and "I_1 = 1.15" in note


@pytest.mark.parametrize(
    "reply",
    [
        # The same system, solved right.
        "$8I_1 + 6I_2 = 10$\n$6I_1 + 10I_2 = 6$\n$I_1 = \\frac{16}{11}$\n$I_2 = -\\frac{3}{11}$",
        # A formula with units, and a value given in its unit.
        "$V_1 = 7.2\\,\\mathrm{V}$\n$V = 12$\n$V_1 + V_2 = V$\n$V_2 = 4.8\\,\\mathrm{V}$",
        # One unknown: a plain step, not a system.
        "$2x + 3 = 7$\n$x = 2$",
        # A name given two values (two roots) is no single value to hold.
        "$x + y = 5$\n$x = 1$\n$x = 3$\n$y = 4$",
    ],
)
def test_values_that_hold_or_cannot_be_held_say_nothing(reply: str) -> None:
    assert unheld_equations(reply) == []
