"""Every answer card's number by one rule (owner, 2026-11-18): two places, whole numbers
whole, written in full below 10^9, a power of ten only past it or below 0.001."""

from __future__ import annotations

import pytest

from app.services.answer_number import Precision, asked_precision, number_latex, number_plain


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (2.453, "2.45"),
        (2.456, "2.46"),
        (2.4, "2.40"),
        (2.199, "2.20"),
        (2.09, "2.09"),
        (2.675, "2.68"),  # a 5 rounds up, on the number as written
        (19394.567, "19394.57"),
        (1500.0, "1500"),
        (109324.04, "109324.04"),  # the owner's chat: never 1.09 x 10^5
        (1093.2404, "1093.24"),
        (999999999.4, "999999999.40"),
        (0.05, "0.05"),
        (0.0567, "0.0567"),  # two places would leave one figure
        (0.00123, "0.00123"),
        (-4.8333, "-4.83"),
        (0.0, "0"),
        (6.022e23, "6.02 \\times 10^{23}"),
        (1.602e-19, "1.60 \\times 10^{-19}"),
        (1e9, "1.00 \\times 10^{9}"),
    ],
)
def test_the_rule(value: float, shown: str) -> None:
    assert number_latex(value) == shown


def test_the_plain_spelling_uses_superscripts() -> None:
    assert number_plain(6.022e23) == "6.02 × 10²³"


@pytest.mark.parametrize(
    ("asked", "value", "shown"),
    [
        ("Give the answer to 1 decimal place.", 18.5185, "18.5"),
        ("to 3 d.p.", 2.0, "2.000"),
        ("correct to 3 significant figures", 109324.04, "109000"),
        ("to 2 s.f.", 6.022e23, "6.0 \\times 10^{23}"),
        ("don't round it", 2.4567891, "2.4567891"),
        ("give me the exact value", 1.6e-19, "1.6 \\times 10^{-19}"),
        ("what is the speed?", 18.5185, "18.52"),
    ],
)
def test_the_precision_the_question_asks_wins(asked: str, value: float, shown: str) -> None:
    assert number_latex(value, asked_precision(asked)) == shown


def test_no_ask_is_the_rule() -> None:
    assert asked_precision("How far does it go?") == Precision()
