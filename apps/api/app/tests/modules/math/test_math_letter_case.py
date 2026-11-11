"""A capital X or Y typed as the unknown reads as x or y; names and prose keep theirs."""

from __future__ import annotations

import pytest

from app.modules.math.match.letter_case import fold_capital_unknowns


@pytest.mark.parametrize(
    ("text", "folded"),
    [
        (
            "How many solutions does $4X^2 + 4 = 6$ have?",
            "How many solutions does $4x^2 + 4 = 6$ have?",
        ),
        ("find the vertex of $Y = X^2 - 4X + 3$", "find the vertex of $y = x^2 - 4x + 3$"),
        ("find k so that $X^2 + kX + 9 = 0$", "find k so that $x^2 + kx + 9 = 0$"),
        ("if $f(X) = X^{2} + 1$ find f(2)", "if $f(x) = x^{2} + 1$ find f(2)"),
        ("expand $(X+1)^2$", "expand $(x+1)^2$"),
        # "x-intercepts" is a word, not a second letter x.
        ("find the x-intercepts of $y = X^2 - 4$", "find the x-intercepts of $y = x^2 - 4$"),
    ],
)
def test_fold_capital_unknowns_reads_the_unknown(text: str, folded: str) -> None:
    assert fold_capital_unknowns(text) == folded


@pytest.mark.parametrize(
    "text",
    [
        # A random variable beside another capital.
        "P(X = 2) for X ~ B(10, 0.3)",
        "E(X) = 3",
        # Two letters: x and X may differ.
        "x + X^2 = 3",
        # Names and prose.
        "Malcolm X (born 1925)",
        "X-rays of wavelength 0.154 nm strike a crystal",
        "press Ctrl+Shift+X",
        "a Ryzen 7 9800X3D build",
        "how many users does Twitter (X) have",
        "In a game of tic-tac-toe, did X win?",
        "angle X = 40 degrees in triangle XYZ",
        # Nothing written as algebra: the solver reads X as typed.
        "solve X + 3 = 5",
    ],
)
def test_fold_capital_unknowns_keeps_other_capitals(text: str) -> None:
    assert fold_capital_unknowns(text) == text
