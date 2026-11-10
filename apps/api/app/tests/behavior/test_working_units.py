"""A Substitution line that drops a given's unit is found; one that keeps it is not."""

from __future__ import annotations

import pytest

from app.tests.behavior.working_units import bare_given_lines

_GIVEN = (
    "**Given**  \n$v_i = 8\\,\\mathrm{m/s}$  \n$v_f = 48\\,\\mathrm{m/s}$  \n"
    "$t = 10\\,\\mathrm{s}$\n\n**Required**  \n$a$\n\n**Substitution**  \n"
)


@pytest.mark.parametrize(
    ("working", "bare"),
    [
        # The owner's chat of 2026-11-10: the givens' units were dropped.
        ("$a = \\frac{48 - 8}{10}$", True),
        ("$a = \\frac{48\\,\\mathrm{m/s} - 8\\,\\mathrm{m/s}}{10\\,\\mathrm{s}}$", False),
        # A factor equal to a given, beside the labelled given, is the law's number.
        ("$a = \\frac{2 \\times 8\\,\\mathrm{m/s}}{10\\,\\mathrm{s}}$", False),
        # A logarithm's argument is a pure number.
        ("$x = \\log_{10} (48)$", False),
    ],
)
def test_a_dropped_unit_is_found(working: str, bare: bool) -> None:
    reply = f"{_GIVEN}{working}\n\n**Answer**\n"
    assert bool(bare_given_lines(reply)) is bare


def test_a_chemistry_row_keeps_its_units_as_text() -> None:
    reply = (
        "**Given**  \n$m(\\mathrm{H₂}) = 4\\,\\mathrm{g}$\n\n**Required**  \nn\n\n"
        "**Substitution**  \n$n(\\mathrm{H₂}) = 4 g / 2.016 g/mol$\n\n**Answer**\n"
    )
    assert bare_given_lines(reply) == []
