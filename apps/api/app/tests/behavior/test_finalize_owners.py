"""Finalize passes that once overruled each other, held fixed: the review probes of
``docs/review/2026-11-19-finalize-pipeline.md`` a fix turned red (probe 1 by #2501, probe 5
by #2495)."""

from __future__ import annotations

import pytest

from app.tests.behavior.finalize_probe import finalize_reply

pytestmark = pytest.mark.usefixtures("thread_sympy_executor")

_BLOCK = (
    "A rectangular block of mass 50 kg lies with a side 2m by 1m on a table. "
    "What is the pressure exerted by its weight on the table? (g = 10 m/s2)"
)
_BLOCK_REPLY = (
    "**Given**\n$m = 50\\,\\mathrm{kg}$, $A = 2\\,\\mathrm{m^2}$, $g = 10\\,\\mathrm{m/s^2}$\n\n"
    "**Required**\nP\n\n**Substitution**\n$W = 50 \\times 10 = 500\\,\\mathrm{N}$\n"
    "$P = \\frac{500}{2} = 250\\,\\mathrm{Pa}$\n\n**Answer**\n\n```answer\n250 Pa\n```"
)


async def test_a_right_card_on_the_questions_own_g_stands_over_the_formal_value() -> None:
    """The question states g = 10 and the reply works with it to 250 Pa. The formal setup
    took 9.81 (245.25 Pa): the reply's answer stands, and no 245 lands under working that
    ends at 250 Pa."""
    _route, saved = await finalize_reply(_BLOCK, _BLOCK_REPLY, formal=(245.25, "Pa", (50.0, 2.0)))
    assert "245" not in saved
    assert saved.rstrip().endswith("250 Pa")


async def test_a_physics_answer_with_a_percent_of_g_gets_no_loan_card() -> None:
    """Probe 5: "6% of g" read as a car loan's rate put a loan calculator under a physics
    answer (fixed by #2495)."""
    reply = (
        "**Given**\n$a = 0.06 \\times 9.81 = 0.5886\\,\\mathrm{m/s^2}$, $t = 5\\,\\mathrm{s}$\n\n"
        "**Required**\n$v$\n\n**Substitution**\n$v = 0.5886 \\times 5 = 2.943\\,\\mathrm{m/s}$\n\n"
        "**Answer**\n\n$v = 2.94\\,\\mathrm{m/s}$"
    )
    route, saved = await finalize_reply(
        "A car accelerates at 6% of g for 5 s from rest. What is its final speed?", reply
    )
    assert route.subject == "physics"
    assert "```calculator" not in saved
