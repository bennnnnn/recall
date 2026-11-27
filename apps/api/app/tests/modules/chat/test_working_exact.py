# ruff: noqa: RUF002, RUF003 -- the docstring writes × as replies do.
"""The exact values behind rounded numbers a working writes, its units read by Pint, and the
line check that holds a line to them (live, 2026-11-27: "84.95, not 84.96" for 10 × 9.81 ×
cos 30°)."""

from __future__ import annotations

import math

import pytest

from app.modules.chat.working_check import wrong_steps
from app.modules.chat.working_exact import standard_values
from app.modules.chat.working_units import conversions, quantity_unit, unit_after


@pytest.mark.parametrize(
    ("reply", "question", "expected"),
    [
        ("$98.1 \\times 0.8660$", "θ = 30°", {"0.8660": math.cos(math.radians(30))}),
        ("$\\frac{98}{1.732}$", "at 60° to the ground", {"1.732": math.tan(math.radians(60))}),
        ("$\\frac{171.5}{1.732}$ for $\\frac{171.5}{\\sqrt{3}}$", "", {"1.732": math.sqrt(3)}),
        ("$2 \\times 3.142$ for $2\\pi$", "", {"3.142": math.pi}),
        # Too coarse to be sure of: 3.1 is no π.
        ("$\\frac{16200}{3.1}$ with $\\pi$ nearby", "", {}),
        # No angle written: 0.8660 is only a number.
        ("$98.1 \\times 0.8660$", "", {}),
        # A given is exact as written.
        ("$0.866 \\times 2$", "θ = 30°, k = 0.866", {}),
    ],
)
def test_a_rounded_standard_value_is_read_as_the_value(
    reply: str, question: str, expected: dict[str, float]
) -> None:
    found = standard_values(reply, question)
    assert found.keys() == expected.keys()
    for written, value in expected.items():
        assert math.isclose(found[written], value)


@pytest.mark.parametrize(
    ("tex", "unit"),
    [
        ("250\\,\\mathrm{rev/min}", "1 / minute"),
        ("3\\,\\text{m/s}^2", "meter / second ** 2"),
        ("400\\,\\mathrm{W/(m·K)}", "watt / kelvin / meter"),
        ("4\\,\\mathrm{\\Omega}", "ohm"),
        ("12\\,\\mathrm{N\\cdot m}", "meter * newton"),
    ],
)
def test_a_unit_the_working_writes_is_read(tex: str, unit: str) -> None:
    assert str(quantity_unit(unit_after(tex))) == unit


@pytest.mark.parametrize(
    "tex", ["100\\,^\\circ\\mathrm{C}", "30^\\circ", "2.5\\,\\mathrm{rad}", "5"]
)
def test_a_temperature_an_angle_or_no_unit_is_not_read(tex: str) -> None:
    assert quantity_unit(unit_after(tex)) is None


def test_a_givens_conversion_is_worked_from_its_first_value() -> None:
    found = conversions(
        ["9.00\\,\\mathrm{cm}", "0.09\\,\\mathrm{m}", "90\\,\\mathrm{mm}", "3\\,\\mathrm{kg}"]
    )
    assert found[0] is not None and math.isclose(found[0], 0.09)
    assert found[1] is not None and math.isclose(found[1], 90)
    assert found[2] is None


@pytest.mark.parametrize(
    "reply",
    [
        # Right on cos 30° (the slip was the check's own).
        "**Substitution**\n$N = 10 \\times 9.81 \\times 0.8660$  \n$N = 84.96\\,\\mathrm{N}$",
        # A prefixed unit outside the maths: no power-of-ten slip.
        "**Substitution**\n$E = 4.52 \\times 10^6$ J $\\approx 4.5$ MJ",
    ],
)
def test_a_right_line_is_no_slip(reply: str) -> None:
    assert wrong_steps(reply, "θ = 30°") == []


@pytest.mark.parametrize(
    ("reply", "question"),
    [
        # A power of ten lost between two worked forms (u8-28).
        (
            "$H = \\frac{70}{\\frac{2.0}{400 \\times 1.0 \\times 10^{-4}}}$  \n$H = \\frac{70}{50000}$",
            "",
        ),
        # 0.3% off, but every input is a given (u8-22).
        ("$F = 6\\pi(0.985)(4\\times10^{-3})(0.5) = 0.011784\\pi$", "viscosity 0.985, 0.5 m/s"),
        # A conversion of a given is exact, so its rounding no longer hides the slip (u6-19).
        (
            "$r = 9.00\\,\\mathrm{cm} = 0.09\\,\\mathrm{m}$  \n"
            "$K = \\frac{1}{2}(\\frac{2}{5})(7.27)(0.09)^2(50.5556)^2 = 30.09$",
            "A 7.27 kg ball with radius 9.00 cm.",
        ),
    ],
)
def test_a_slip_the_check_used_to_let_by_is_named(reply: str, question: str) -> None:
    assert wrong_steps(reply, question)
