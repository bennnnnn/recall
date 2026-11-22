"""A one-line summary after the answer cards stays, solved or not (owner, 2026-11-12, and
2026-11-22: "yes", even when it only repeats the cards' numbers). Before, the subject's fence
pass dropped it on a solved turn and ``working_check`` on an unsolved one (the 2026-11-19
finalize review, conflict 7)."""

from __future__ import annotations

import pytest

from app.services.closing_summary import closing_summary, with_closing_summary
from app.tests.behavior.finalize_probe import finalize_reply

pytestmark = pytest.mark.usefixtures("thread_sympy_executor")


async def test_a_solved_turn_keeps_its_closing_summary() -> None:
    reply = (
        "**Substitution**\n$KE = \\tfrac12 \\times 2 \\times 3^2 = 9\\,\\mathrm{J}$\n\n"
        "**Answer**\n\n```answer\n9 J\n```\n\nThe kinetic energy is 9 J."
    )
    _route, out = await finalize_reply(
        "A 2 kg ball moves at 3 m/s. What is its kinetic energy?", reply
    )
    assert out.rstrip().endswith("The kinetic energy is 9 J.")
    assert "verified: true" in out


async def test_a_summary_that_contradicts_the_verified_card_goes() -> None:
    """Review (#2528): "10 J" in the model's card and its closing line, 9 J verified."""
    reply = (
        "**Substitution**\n$KE = \\tfrac12 \\times 2 \\times 3^2 = 10\\,\\mathrm{J}$\n\n"
        "**Answer**\n\n```answer\n10 J\n```\n\nThe kinetic energy is 10 J."
    )
    _route, out = await finalize_reply(
        "A 2 kg ball moves at 3 m/s. What is its kinetic energy?", reply
    )
    assert "The kinetic energy is 10 J." not in out


async def test_an_unsolved_turn_keeps_its_closing_summary() -> None:
    reply = (
        "**Substitution**\n$v = \\frac{160}{12} = 13.33\\,\\mathrm{m/s}$\n\n"
        "**Answer**\n\n$v = 13.33\\,\\mathrm{m/s}$\n\n"
        "The car's average speed is $13.33\\,\\mathrm{m/s}$."
    )
    _route, out = await finalize_reply(
        "A car travels 100 m in 8 s, then 60 m in 4 s. What is its average speed?", reply
    )
    assert "The car's average speed is" in out


def test_only_a_one_line_tail_after_the_last_card_is_a_summary() -> None:
    card = "```answer\nx = 3\n```"
    assert closing_summary(f"Work.\n\n{card}\n\nSo x is 3.") == "So x is 3."
    assert closing_summary(f"Work.\n\n{card}\n\n- x = 3\n- y = 4") is None
    assert closing_summary(f"Work.\n\n{card}") is None
    assert with_closing_summary(f"Work.\n\n{card}\n", "So x is 3.") == (
        f"Work.\n\n{card}\n\nSo x is 3.\n"
    )
    # Already there: nothing added twice.
    text = f"Work.\n\n{card}\n\nSo x is 3."
    assert with_closing_summary(text, "So x is 3.") == text
