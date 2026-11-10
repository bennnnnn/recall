"""The independent reader of printed units flags a wrong one and passes a right one."""

from __future__ import annotations

import pytest

from app.tests.behavior.labelled_rows import row_problems

_GIVEN = (
    "**Given**  \n$v = 10\\,\\mathrm{m/s}$  \n$a = 10\\,\\mathrm{m/s²}$  \n"
    "$t_r = 1\\,\\mathrm{s}$\n\n**Required**  \n$d$\n\n**Substitution**  \n"
)


@pytest.mark.parametrize(
    ("row", "wrong"),
    [
        (
            r"$d_b = \frac{(10\,\mathrm{m/s})^{2}}{2 \times 10\,\mathrm{m/s²}} = 5\,\mathrm{m}$",
            False,
        ),
        # The review of 2026-11-10: a braking distance printed in m/s.
        (
            r"$d_b = \frac{(10\,\mathrm{m/s})^{2}}{2 \times 10\,\mathrm{m/s}} = 5\,\mathrm{m/s}$",
            True,
        ),
        # A metre added to a second.
        (r"$d = 10\,\mathrm{m} + 1\,\mathrm{s}$", True),
        # The law's 2 printed as a given: 2 m/s is no given here.
        (
            r"$d_b = \frac{(10\,\mathrm{m/s})^{2}}{2\,\mathrm{m/s} \times 10\,\mathrm{m/s}} = 5$",
            True,
        ),
        # A stated value its numbers do not make.
        (r"$d_r = 10\,\mathrm{m/s} \times 1\,\mathrm{s} = 12\,\mathrm{m}$", True),
    ],
)
def test_a_wrong_unit_is_found(row: str, wrong: bool) -> None:
    problems, _unread = row_problems(f"{_GIVEN}{row}\n\n**Answer**\n")
    assert bool(problems) is wrong, problems
