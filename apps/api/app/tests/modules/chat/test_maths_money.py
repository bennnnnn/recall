"""A sum of money in a bold or word group inside maths leaves the maths (``maths_money``)."""

from __future__ import annotations

import pytest

from app.modules.chat.maths_money import money_out_of_maths
from app.tests.behavior.latex_check import latex_problems


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        # The owner's loan reply (2026-11-22): drawn "M ≈ {\773}$ per month".
        ("$M \\approx \\textbf{\\$773}$ per month", "$M \\approx$ **$773** per month"),
        ("So $M \\approx \\textbf{\\$619}$", "So $M \\approx$ **$619**"),
        ("$\\textbf{\\$542}$ a month", "**$542** a month"),
        ("$\\mathbf{\\$3,440}$", "**$3,440**"),
        ("$M = \\text{\\$1{,}720}$.", "$M =$ $1,720."),
        # Not at the formula's end: only its group goes.
        ("$\\textbf{\\$80} \\times 7 = \\$560$", "$\\$80 \\times 7 = \\$560$"),
        # A price beside it would pair with the next dollar: it stays in the maths.
        (
            "$M \\approx \\textbf{\\$773}$ and $x = 2$ then $5",
            "$M \\approx \\$773$ and $x = 2$ then $5",
        ),
    ],
)
def test_money_out_of_maths(reply: str, expected: str) -> None:
    assert money_out_of_maths(reply) == expected
    assert latex_problems(money_out_of_maths(reply)) == []


@pytest.mark.parametrize(
    "reply",
    [
        "$\\$80 \\times 7 = \\$560$",
        "No money $x^2$ here \\$5",
        "$\\textbf{x} = 5$ and \\$5",
        "    $M \\approx \\textbf{\\$773}$ indented code",
        "```\n$M \\approx \\textbf{\\$773}$\n```",
        "`$M \\approx \\textbf{\\$773}$`",
    ],
)
def test_money_out_of_maths_leaves_other_text(reply: str) -> None:
    assert money_out_of_maths(reply) == reply


def test_money_out_of_maths_keeps_the_rest_of_a_reply() -> None:
    reply = (
        "Working:\n\n$r = \\frac{0.06}{12}$  \n$r = 0.005$\n\n"
        "$M = 32000 \\times \\frac{0.005(1.005)^{60}}{(1.005)^{60} - 1}$\n\n"
        "$M \\approx \\textbf{\\$619}$\n\nThat is about $154 less."
    )
    out = money_out_of_maths(reply)
    assert out == reply.replace("$M \\approx \\textbf{\\$619}$", "$M \\approx$ **$619**")
