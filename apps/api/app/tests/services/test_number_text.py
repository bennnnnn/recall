"""Scientific notation is one number, however it is typed."""

from __future__ import annotations

import pytest

from app.services.number_text import read_scientific_numbers


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2 × 10^-6 C", "2e-6 C"),
        ("2x10^-6", "2e-6"),
        ("2 X 10^-6", "2e-6"),
        ("2*10**-6", "2e-6"),
        ("2·10⁻⁶ C", "2e-6 C"),
        ("1.5 × 10³", "1.5e3"),
        (r"2 \times 10^{-6}", "2e-6"),
        (r"6.63\,\times\,10^{-34}", "6.63e-34"),
        (r"1.6 \cdot 10^{-19}", "1.6e-19"),
        ("1.6 × 10^(−19) C", "1.6e-19 C"),
        ("−1.6×10^–19", "-1.6e-19"),
        ("4.5 x 10 ^ -3", "4.5e-3"),
        ("3 × 10^8 m/s", "3e8 m/s"),
        ("a speed of 10^8 m/s", "a speed of 1e8 m/s"),
        ("6,000 × 10^3", "6000e3"),
        # A full stop ending the sentence is not a decimal exponent.
        ("Ka = 1.8 × 10^-5. Find the pH", "Ka = 1.8e-5. Find the pH"),
        ("c = 3 × 10^8.", "c = 3e8."),
    ],
)
def test_read_scientific_numbers_folds_one_literal(text: str, expected: str) -> None:
    assert read_scientific_numbers(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "2 × 10 m",  # a product, not a power of ten
        "10^2.5",  # a fractional exponent is not notation
        "x10^5",  # a variable times a power
        "m/s^2",
        "2E-6",  # already one literal
        "in 2010 the",
        "10^1234",  # four-digit exponents are not read
    ],
)
def test_read_scientific_numbers_leaves_other_text(text: str) -> None:
    assert read_scientific_numbers(text) == text
