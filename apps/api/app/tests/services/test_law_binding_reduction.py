"""A substitution worked one layer at a time, the way a student writes it out."""

from __future__ import annotations

import math

import pytest

from app.modules.physics.display import latex_given
from app.services.law_binding.leaf_units import LeafUnits
from app.services.law_binding.reduction import reduce_substitution
from app.services.units import get_unit_registry


@pytest.mark.parametrize(
    ("symbol", "substituted", "rows", "value"),
    [
        ("a", r"\frac{27.7778 - 0}{8}", [r"a = \frac{27.7778}{8}"], 3.472225),
        # A written number keeps its spelling; a worked one is printed as a given is.
        (
            "E",
            r"\frac{6.6261 \times 10^{-34} \times 299792458}{5 \times 10^{-7}}",
            [r"E = \frac{1.98645 \times 10^{-25}}{5 \times 10^{-7}}"],
            3.97291e-19,
        ),
        # An angle stays in degrees; an inverse sine gives one.
        (
            r"\theta",
            r"\tfrac{1}{2} \arcsin\!\left(\frac{30 \times 9.81}{20^{2}}\right)",
            [
                r"\theta = 0.5 \times \arcsin(\frac{294.3}{400})",
                r"\theta = 0.5 \times \arcsin(0.73575)",
                r"\theta = 0.5 \times 47.3706^\circ",
            ],
            23.6853,
        ),
        # (-8) is a number, not a step; -(2 + 3) is -5 in the row that adds.
        ("J", r"0.2 \times ((-8) - 10)", [r"J = 0.2 \times (-18)"], -3.6),
        ("x", r"-(2 + 3)", [], -5.0),
        # A run of sums is added in one row, as by hand.
        (
            "S",
            r"\frac{1}{12} + \frac{1}{12} + \frac{1}{12} + \frac{1}{12}",
            [r"S = 0.0833333 + 0.0833333 + 0.0833333 + 0.0833333"],
            1 / 3,
        ),
        # cos 90° is 0, and a number before a fraction takes a dot (never a mixed number).
        (
            "T",
            r"5 \times \frac{2 \times 9.81}{5 + 2}",
            [r"T = 5 \times \frac{19.62}{7}", r"T = 5 \times 2.80286"],
            14.0143,
        ),
        ("F", r"2 \times 3\cos(90^\circ)", [r"F = 6 \times 0"], 0.0),
        ("f", r"8\times 9.81\times |\sin(25^\circ)|", [r"f = 78.48 \times 0.422618"], 33.1671),
        ("H", r"\frac{20^2 \sin^2(30^\circ)}{2 \times 9.81}", None, 5.09684),
        ("x", r"\sqrt{3^2 + 4^2}", [r"x = \sqrt{9 + 16}", r"x = \sqrt{25}"], 5.0),
    ],
)
def test_reduce_substitution(
    symbol: str, substituted: str, rows: list[str] | None, value: float
) -> None:
    reduction = reduce_substitution(symbol, substituted, latex_given)
    assert reduction is not None
    if rows is not None:
        assert list(reduction.rows) == rows
    assert math.isclose(reduction.value, value, rel_tol=1e-5, abs_tol=1e-12)


@pytest.mark.parametrize(
    "substituted",
    [
        # A unit, a symbol, or anything else outside the arithmetic: the row stays as written.
        r"2000\,\mathrm{W} \times 10800",
        r"m \times 9.81",
        r"\frac{1}{0}",
        r"\sqrt{-4}",
        "",
    ],
)
def test_a_row_past_reading_is_left_alone(substituted: str) -> None:
    assert reduce_substitution("x", substituted, latex_given) is None


def _units(given: list[tuple[float, str]], answer: str) -> LeafUnits:
    ureg = get_unit_registry()
    return LeafUnits(
        given=[(value, ureg(unit).units) for value, unit in given],
        shown=lambda unit: rf"\,\mathrm{{{unit:~}}}",
        answers=[ureg(answer).dimensionality],
    )


def test_every_number_carries_its_unit_down_to_the_answer() -> None:
    """The owner's chat of 2026-11-10: a = (48 - 8)/10 had dropped m/s and s."""
    units = _units([(8.0, "m/s"), (48.0, "m/s"), (10.0, "s")], "m/s^2")
    reduction = reduce_substitution("a", r"\frac{48 - 8}{10}", latex_given, units)
    assert reduction is not None
    assert reduction.substituted == r"\frac{48\,\mathrm{m / s} - 8\,\mathrm{m / s}}{10\,\mathrm{s}}"
    assert reduction.rows == (r"a = \frac{40\,\mathrm{m / s}}{10\,\mathrm{s}}",)
    assert f"{reduction.unit:~}" == "m / s ** 2"


def test_a_factor_equal_to_a_given_stays_a_number() -> None:
    """2as with a = 2 m/s²: the law's 2 comes first, so the later 2 is the given."""
    units = _units([(2.0, "m/s^2"), (16.0, "m")], "m^2/s^2")
    reduction = reduce_substitution("v^2", r"2 \times 2 \times 16", latex_given, units)
    assert reduction is not None
    assert reduction.substituted == r"2 \times 2\,\mathrm{m / s ** 2} \times 16\,\mathrm{m}"


def test_units_that_do_not_go_together_leave_the_row_bare() -> None:
    """A metre added to a second has no reading: the row stays as the solver wrote it."""
    units = _units([(3.0, "m"), (4.0, "s")], "m")
    reduction = reduce_substitution("x", "3 + 4", latex_given, units)
    assert reduction is not None
    assert reduction.substituted is None
