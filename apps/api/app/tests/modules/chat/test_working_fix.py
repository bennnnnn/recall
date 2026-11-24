"""A wrong number in the model's own working is put right, and the lines built on it after."""

from __future__ import annotations

import pytest

from app.modules.chat.tex_arithmetic import evaluate, plain_arithmetic
from app.modules.chat.working_approximations import corrected_approximations
from app.modules.chat.working_check import working_note, wrong_steps
from app.modules.chat.working_fix import put_right


def corrected_working(reply: str, question: str = "") -> str:
    return put_right(reply, question)[0]


# The owner's projectile question (live, 2026-11-23): each slip reached the student.
_ROOT_SLIP = (
    "**Substitution**\n\n"
    "$t = \\frac{14.339 + \\sqrt{(-14.339)^2 - 4(4.905)(-45)}}{2(4.905)}$\n"
    "$t = \\frac{14.339 + \\sqrt{205.6 + 882.9}}{9.81}$\n"
    "$t = \\frac{14.339 + 33.11}{9.81}$\n"
    "$t = 4.82\\,\\mathrm{s}$\n"
)
_TIME_SLIP = (
    "**Substitution**\n\n"
    "$4.9t^2 - 14.34t - 45 = 0$\n\n"
    "$t = \\frac{14.34 + \\sqrt{14.34^2 + 4(4.9)(45)}}{2(4.9)}$\n"
    "$t = 4.85\\ \\text{s}$\n\n"
    "$x = 20.48(4.85)$\n"
    "$x = 99.3\\ \\text{m}$\n\n"
    "**Answer**\n\n"
    "**Time in the air: $t \\approx 4.85\\ \\text{s}$**\n\n"
    "**Range: $x \\approx 99.3\\ \\text{m}$**\n\n"
    "The ball lands 99.3 m from the base after 4.85 s.\n"
)


def test_a_root_written_wrong_inside_a_fraction_is_put_right() -> None:
    fixed = corrected_working(_ROOT_SLIP)
    assert "$t = \\frac{14.339 + 32.99}{9.81}$" in fixed
    # The answer was already right (4.8246): it stays as written.
    assert "$t = 4.82\\,\\mathrm{s}$" in fixed
    assert fixed.replace("32.99", "33.11") == _ROOT_SLIP


def test_a_wrong_time_is_put_right_and_carried_to_the_range_and_the_answer() -> None:
    fixed = corrected_working(_TIME_SLIP)
    assert fixed == (_TIME_SLIP.replace("4.85", "4.83").replace("99.3", "98.9")), fixed
    assert wrong_steps(fixed) == []


def test_the_carried_range_is_the_corrected_time_s() -> None:
    # 20.48 * 4.85 = 99.33 is right arithmetic on a wrong time: only the time is the slip.
    steps = wrong_steps(_TIME_SLIP)
    assert [step.shown for step in steps] == ["4.85\\ \\text{s}"]


@pytest.mark.parametrize(
    ("line", "right"),
    [
        # Roots, of any degree.
        ("$\\sqrt{1088.5} = 33.11$", "32.99"),
        ("$\\sqrt[3]{30} = 3.20$", "3.11"),
        # Sine, cosine and tangent of degrees and of radians.
        ("$25 \\sin(35^\\circ) = 14.84$", "14.34"),
        ("$25\\cos 35^\\circ = 20.98$", "20.48"),
        ("$\\tan 35^\\circ = 0.75$", "0.70"),
        ("$\\sin(0.5) = 0.52$", "0.48"),
        ("$\\cos\\left(\\frac{\\pi}{3}\\right) = 0.55$", "0.50"),
        # Fractions and powers.
        ("$\\frac{9.81}{2.5} = 3.98$", "3.92"),
        ("$1.5^{3} = 3.45$", "3.38"),
        # Logarithms, e and pi.
        ("$\\ln 2 = 0.71$", "0.69"),
        ("$\\log_{10}(250) = 2.47$", "2.40"),
        ("$100 e^{-0.5} = 62.1$", "60.7"),
        ("$\\pi (2.5)^2 = 19.8$", "19.6"),
        # An absolute value, and moles (never a step to millis).
        ("$|90 - 82.5| = 7.9$", "7.5"),
        (
            "$4\\,\\mathrm{g} / 2.016\\,\\mathrm{g/mol} = 2.124\\,\\mathrm{mol}$",
            "1.984\\,\\mathrm{mol}",
        ),
        # Powers of ten.
        ("$6.02 \\times 10^{23} \\times 2 = 1.5 \\times 10^{24}$", "1.2 \\times 10^{24}"),
        ("$\\frac{1.6 \\times 10^{-19}}{2} = 0.85 \\times 10^{-19}$", "8.00 \\times 10^{-20}"),
    ],
)
def test_each_function_family_is_held_to_its_value(line: str, right: str) -> None:
    # A short decimal is exact only as a given: the circle's radius is the question's.
    question = "A circle of radius 2.5 cm." if "2.5)^2" in line else ""
    fixed = corrected_working(f"**Steps**\n\n{line}\n", question)
    left = line.strip("$").split("=")[0]
    assert fixed == f"**Steps**\n\n${left}= {right}$\n", fixed


@pytest.mark.parametrize(
    ("reply", "fixed"),
    [
        # The root a ± line was nearest, put right.
        (
            "**Steps**\n\n$x = \\frac{3 \\pm \\sqrt{9 + 16}}{2}$\n$x = 4.1$",
            "**Steps**\n\n$x = \\frac{3 \\pm \\sqrt{9 + 16}}{2}$\n$x = 4.0$",
        ),
        (
            "**Steps**\n\n$x = \\frac{3 \\pm \\sqrt{9 + 16}}{2}$\n$x = -1.2$",
            "**Steps**\n\n$x = \\frac{3 \\pm \\sqrt{9 + 16}}{2}$\n$x = -1.0$",
        ),
        # The root of the + branch, written as a number on the next line.
        (
            "**Steps**\n\n$t = \\frac{14.34 \\pm \\sqrt{14.34^2 + 4(4.9)(45)}}{9.8}$\n"
            "$t = \\frac{14.34 + 33.40}{9.8}$",
            "**Steps**\n\n$t = \\frac{14.34 \\pm \\sqrt{14.34^2 + 4(4.9)(45)}}{9.8}$\n"
            "$t = \\frac{14.34 + 32.98}{9.8}$",
        ),
    ],
)
def test_a_plus_or_minus_is_held_to_its_nearest_root(reply: str, fixed: str) -> None:
    assert corrected_working(reply) == fixed


@pytest.mark.parametrize(
    "reply",
    [
        # Right, or rounded as a student rounds, as it goes.
        "**Steps**\n\n$\\sqrt{1088.5} = 32.99$",
        "**Steps**\n\n$v_{0y} = 25\\sin 35^\\circ$\n$v_{0y} = 14.34\\ \\text{m/s}$",
        "**Steps**\n\n$t = \\frac{3.5}{9.8} = 0.36$\n$d = 2 \\times 0.36 = 0.71$",
        "**Steps**\n\n$R = 25 \\cos(35^\\circ) \\times 4.82$\n$R = 25 \\times 0.8192 \\times 4.82$\n"
        "$R = 98.8\\,\\mathrm{m}$",
        "**Steps**\n\n$t = \\frac{14.34 + \\sqrt{14.34^2 + 4(4.9)(45)}}{2(4.9)}$\n"
        "$t = \\frac{14.34 + 32.98}{9.8}$\n\n$t = 4.83\\ \\text{s}$\n\n$x = 20.48 \\times 4.83$",
        # Inputs rounded coarsely on the way, the result kept from the first line's value.
        "**Steps**\n\n$t = \\frac{14.34 + \\sqrt{14.34^2 + 4(4.9)(45)}}{2(4.9)}$\n"
        "$t = \\frac{14 + 33}{9.8}$\n$t = 4.83$",
        # 3.14 for pi, worked on the true pi.
        "**Steps**\n\n$A = 3.14 \\times 5^2 = 78.54$",
        # A variable, a percent, a sine with no degree sign, an unknown e.
        "**Steps**\n\n$4.9t^2 - 14.34t - 45 = 0$",
        "**Steps**\n\n$15\\% \\text{ of } 80 = 12$",
        "**Steps**\n\n$\\sin(30) = 0.5$",
        "**Steps**\n\n$e^2 = 1 - \\frac{9}{25} = 0.64$",
        # A log with no base: right as a natural log.
        "**Steps**\n\n$\\log(20) = 3.00$",
        # Text that is no arithmetic: a range, a date, a score, money.
        "**Steps**\n\nIt takes $2-3$ hours, from $2026-11-23$, and the score was $3-2$.",
        "**Steps**\n\nIt costs $12.50 each, so three cost $37.50 in all.",
    ],
)
def test_right_or_unreadable_working_is_never_changed(reply: str) -> None:
    assert corrected_working(reply) == reply
    assert working_note(reply) is None


def test_a_number_given_in_the_question_is_never_carried() -> None:
    """4.85 is the question's own value: only the slip's line is put right, and it is named,
    since the lines after it may depend on it."""
    reply = "**Steps**\n\n$a = \\frac{20}{4} = 4.85$\n\n$F = 4.85 \\times 2$"
    fixed, note = put_right(reply, "A 4.85 kg box is pushed with 20 N over 4 m.")
    assert fixed == reply.replace("\\frac{20}{4} = 4.85", "\\frac{20}{4} = 5.00")
    assert note is not None


def test_a_later_result_with_the_same_digits_is_judged_on_its_own() -> None:
    """2.425 * 2 is 4.85: that line is right and keeps its number."""
    reply = (
        "**Steps**\n\n$4.9t^2 - 14.34t - 45 = 0$\n\n"
        "$t = \\frac{14.34 + \\sqrt{14.34^2 + 4(4.9)(45)}}{2(4.9)}$\n"
        "$t = 4.85\\ \\text{s}$\n\n$y = 2.425 \\times 2 = 4.85$"
    )
    fixed = corrected_working(reply)
    assert "$t = 4.83\\ \\text{s}$" in fixed
    assert fixed.endswith("$y = 2.425 \\times 2 = 4.85$")


def test_fences_and_a_card_are_never_touched() -> None:
    reply = (
        "**Steps**\n\n$a = \\frac{9.81}{2.5} = 3.98\\ \\text{m/s}^2$\n\n"
        "```answer\nResult\na = 3.98 m/s^2\n```\n\n```python\nprint(3.98)\n```"
    )
    fixed = corrected_working(reply)
    assert fixed == reply.replace("= 3.98\\ ", "= 3.92\\ ", 1)


def test_a_step_that_cannot_be_put_right_stops_the_walk_and_is_named() -> None:
    """Another exact form: which side slipped is unknown, so nothing after it changes."""
    reply = "**Steps**\n\n$A = \\sqrt{11375}$\n$A = 25\\sqrt{72}$\n\n$t = \\frac{9.81}{2.5} = 3.98$"
    assert corrected_working(reply) == reply
    assert working_note(reply) is not None


@pytest.mark.parametrize(
    ("tex", "value"),
    [
        ("\\sqrt[3]{-27}", -3.0),
        ("\\ln 2", 0.693147),
        ("\\log_{10}(1000)", 3.0),
        ("\\log_{2} 8", 3.0),
        ("e^{-0.5}", 0.606531),
        ("\\mathrm{e}^{2}", 7.389056),
        ("\\sin(\\frac{\\pi}{6})", 0.5),
        ("\\exp(1)", 2.718282),
    ],
)
def test_functions_read_as_numbers(tex: str, value: float) -> None:
    plain = plain_arithmetic(tex)
    assert plain is not None and evaluate(plain) == pytest.approx(value, rel=1e-5)


@pytest.mark.parametrize(
    "tex",
    ["e^2", "\\sin(30)", "\\log_{5}(25)", "\\sin^{-1}(0.5)", "\\arcsin(0.5)", "e^{1000}"],
)
def test_ambiguous_or_huge_functions_are_not_read(tex: str) -> None:
    plain = plain_arithmetic(tex)
    assert plain is None or evaluate(plain) is None


def test_a_short_number_is_carried_only_where_it_is_said_again() -> None:
    """ "38" may be another value's in a calculation: its restatement follows the fix."""
    reply = "**Steps**\n\n$12 \\times 3 = 38$\n\n**Answer**\n\n$38$"
    assert corrected_working(reply) == reply.replace("38", "36")


def test_a_short_number_used_again_in_a_calculation_is_named_not_changed() -> None:
    """Which later 38 is the slip's is unknown: the working is left as written, and named."""
    reply = "**Steps**\n\n$12 \\times 3 = 38$\n$y = 38 + 2$"
    assert corrected_working(reply) == reply
    assert working_note(reply) is not None


# Review (#2576): each of these was changed wrongly, or lost its note.
@pytest.mark.parametrize(
    "reply",
    [
        # A slip's short number (0.5) is also the half of a kinetic energy.
        "**Steps**\n\n$a = \\frac{1.1}{2.5} = 0.5$\n$KE = 0.5 \\times 4 \\times 3^2 = 18$",
        # A thousands mark inside the result, and a decimal comma.
        "**Steps**\n\n$1{,}200 \\times 1.5 = 1{,}850$",
        "**Steps**\n\n$2{,}5 \\cdot 4{,}2 = 11{,}5$",
    ],
)
def test_a_slip_that_cannot_be_put_right_safely_is_named(reply: str) -> None:
    fixed, note = put_right(reply)
    assert fixed == reply
    assert note is not None or working_note(reply) is not None


@pytest.mark.parametrize(
    "reply",
    [
        # A cosine or sine worked in the head, to two places.
        "**Steps**\n\n$F_x = 50\\cos 30^\\circ = 50 \\times 0.87 = 43.3\\,\\text{N}$",
        "**Steps**\n\n$F = 20\\sin 45^\\circ = 20(0.71) = 14.1$",
        # e as a name after an operation, and an angle of 2π.
        "**Steps**\n\n$(1 - e^2) \\times 50 = 0.36 \\times 50 = 18$",
        "**Steps**\n\n$\\sin 2\\pi = 0$",
        "**Steps**\n\n$\\cos 2\\pi = 1$",
        # A decimal comma.
        "**Steps**\n\n$F = 2{,}5 \\cdot 4 = 10\\,\\mathrm{N}$",
        # A rounded result in powers of ten, carried.
        "**Steps**\n\n$n = 2.5 \\times 6.02 \\times 10^{23} = 1.5 \\times 10^{24}$\n"
        "$N = 1.5 \\times 10^{24} \\times 3 = 4.52 \\times 10^{24}$",
        # A log right as ln, to its own rounding.
        "**Steps**\n\n$\\log(3.14) = 1.145$",
        # A value and its uncertainty.
        "**Steps**\n\n$L = 2.50 \\pm 0.05\\ \\text{m}$\n$L = 2.50\\ \\text{m}$",
    ],
)
def test_review_look_alikes_are_never_changed(reply: str) -> None:
    assert corrected_working(reply) == reply
    assert working_note(reply) is None


def test_a_slip_closing_its_maths_mid_sentence_is_carried_to_the_next() -> None:
    reply = (
        "**Steps**\n\n$a = \\frac{9.81}{2.5} = 3.98\\ \\text{m/s}^2$, so "
        "$F = 2 \\times 3.98 = 7.96\\ \\text{N}$"
    )
    assert corrected_working(reply, "2.5 kg") == (
        reply.replace("3.98", "3.92").replace("7.96", "7.84")
    )


# Second review (#2576): each of these turned a right line wrong.
def test_a_log_with_no_base_is_read_as_the_decimal_beside_it_means() -> None:
    reply = "So $\\int_1^2 \\frac{1}{x}\\,dx = \\log 2$ (approximately 0.693)."
    assert corrected_approximations(reply) == reply
    steps = "**Steps**\n\n$\\frac{\\log 2}{0.05} = 13.86$"
    assert corrected_working(steps) == steps
    assert working_note(steps) is None


def test_a_number_written_as_another_number_is_another_form() -> None:
    near = "**Steps**\n\n$\\sqrt{50} \\approx \\sqrt{49} = 7$"
    assert corrected_working(near) == near
    assert working_note(near) is None
    fraction = "**Steps**\n\n$P = \\frac{12}{16} = \\frac{2}{3}$"
    assert corrected_working(fraction) == fraction
    assert working_note(fraction) is not None


@pytest.mark.parametrize(
    "rounding",
    [
        "Using cos 30° ≈ 0.87:",
        "$$\\cos 30^\\circ \\approx 0.87$$",
        "Using \\(\\cos 30^\\circ \\approx 0.87\\):",
    ],
)
def test_a_short_number_the_reply_worked_out_keeps_its_rounding(rounding: str) -> None:
    reply = f"**Steps**\n\n{rounding}\n\n$F_x = 50 \\times 0.87 = 43.3\\,\\text{{N}}$"
    assert corrected_working(reply) == reply
    assert working_note(reply) is None
