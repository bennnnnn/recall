"""One way to show a physics number and unit, in plain text and in LaTeX."""

from __future__ import annotations

import pytest

from app.modules.physics.display import (
    GIVEN_FIGURES,
    latex_number,
    latex_unit,
    plain_number,
    plain_quantity,
    plain_unit,
    typeset_numbers,
)
from app.modules.physics.solvers.chip import render_chip, render_chip_latex
from app.modules.physics.solvers.common import QuantityResult


@pytest.mark.parametrize(
    ("value", "plain", "latex"),
    [
        (39.618, "39.6", "39.6"),
        (0.2157, "0.216", "0.216"),
        (36.7875, "36.8", "36.8"),
        (20.0, "20", "20"),
        (22620, "22600", "22600"),
        (240000, "2.4 × 10⁵", r"2.4 \times 10^{5}"),
        (3.3131e-19, "3.31 × 10⁻¹⁹", r"3.31 \times 10^{-19}"),
        # Rounding comes before the choice of form.
        (99999.7, "1 × 10⁵", r"1 \times 10^{5}"),
        (0.00099996, "0.001", "0.001"),
        (-29.714, "-29.7", "-29.7"),
        (0.0, "0", "0"),
    ],
)
def test_answer_numbers_have_three_figures_and_no_calculator_notation(
    value: float, plain: str, latex: str
) -> None:
    assert plain_number(value) == plain
    assert latex_number(value) == latex


def test_a_given_keeps_the_figures_typed() -> None:
    assert plain_number(4186, GIVEN_FIGURES) == "4186"
    assert plain_number(0.385, GIVEN_FIGURES) == "0.385"
    assert latex_number(6.62607015e-34, GIVEN_FIGURES) == r"6.62607 \times 10^{-34}"


@pytest.mark.parametrize(
    ("unit", "plain", "latex"),
    [
        ("m/s^2", "m/s²", r"\,\mathrm{m/s²}"),
        ("kg*m^2", "kg·m²", r"\,\mathrm{kg·m²}"),
        ("N*s", "N·s", r"\,\mathrm{N·s}"),
        ("J/kg/K", "J/(kg·K)", r"\,\mathrm{J/(kg·K)}"),
        ("uC", "µC", r"\,\mathrm{µC}"),
        ("deg", "°", r"^\circ"),
        ("ohm", "Ω", r"\,\Omega"),
        ("", "", ""),
    ],
)
def test_units_are_upright_symbols(unit: str, plain: str, latex: str) -> None:
    assert plain_unit(unit) == plain
    assert latex_unit(unit) == latex


def test_an_angle_sits_against_its_number() -> None:
    assert plain_quantity(23.685, "deg") == "23.7°"
    assert plain_quantity(6, "ohm") == "6 Ω"


def test_rows_lose_calculator_notation_and_float_noise() -> None:
    row = r"E = \frac{6.6261e-34 \cdot 3e+08}{5e-07} + 0.30000000000000004 - 4186"
    assert typeset_numbers(row) == (
        r"E = \frac{6.6261 \times 10^{-34} \cdot 3 \times 10^{8}}{5 \times 10^{-7}} + 0.3 - 4186"
    )


def test_a_chip_reads_the_same_in_both_spellings() -> None:
    items = (
        QuantityResult("", 3.3131e-19, "J", detail="2.068 eV"),
        QuantityResult("", 2.4525, "m/s^2"),
    )
    assert render_chip(items) == "3.31 × 10⁻¹⁹ J (2.07 eV) and 2.45 m/s²"
    assert render_chip_latex(items) == (
        r"3.31 \times 10^{-19}\,\mathrm{J}\ (\text{2.07 eV})"
        r"\ \text{and}\ 2.45\,\mathrm{m/s²}"
    )


def test_a_note_escapes_latex_specials() -> None:
    item = QuantityResult("", 0.39988, "", detail="39.988%")
    assert render_chip((item,)) == "0.4 (40%)"
    assert render_chip_latex((item,)) == r"0.4\ (\text{40\%})"
