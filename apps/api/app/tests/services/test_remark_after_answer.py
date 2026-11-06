"""The answer card holds the answer; a remark about it goes in a sentence under the card.

Live, 2026-11-06: a rolling sphere's card read "√(10gh/7) m/s (about 1.20sqrt{gh}; option A
gives sqrt{2gh}, which is the sliding-block result with no rotation)".
"""

from __future__ import annotations

import pytest

from app.modules.chat.worked_render import WorkedLayout, render_worked
from app.modules.chat.worked_solution import assemble, read_record
from app.services.answer_fence import land_answer_card
from app.services.part_answer_cards import land_part_answer_cards
from app.services.remark_after_answer import split_tail


@pytest.mark.parametrize(
    "value, card, said",
    [
        (
            r"$v = \sqrt{\frac{10gh}{7}}$ (about $1.20\sqrt{gh}$; option A gives $\sqrt{2gh}$)",
            r"$v = \sqrt{\frac{10gh}{7}}$",
            r"About $1.20\sqrt{gh}$; option A gives $\sqrt{2gh}$.",
        ),
        (r"$x = 3$, since 3 is greater than 2", "$x = 3$", "Since 3 is greater than 2."),
        ("$x = 3$ \u2014 so the answer is 3.", "$x = 3$", "So the answer is 3."),
        ("$v = 4$ m/s; it slows as it climbs", "$v = 4$ m/s", "It slows as it climbs."),
        # A unit, a short label in brackets, and both roots stay on the card.
        ("$x = 3$ m/s", "$x = 3$ m/s", ""),
        ("$0.90$ dollars", "$0.90$ dollars", ""),
        ("$v = 8$ m/s (east)", "$v = 8$ m/s (east)", ""),
        ("$x = 3.33$ (to 3 s.f.)", "$x = 3.33$ (to 3 s.f.)", ""),
        ("$x = 2$, $x = -2$", "$x = 2$, $x = -2$", ""),
        # An answer written as a sentence, or with no maths, is as it was.
        ("The ball lands at $x = 3$ m away.", "The ball lands at $x = 3$ m away.", ""),
        ("Paris", "Paris", ""),
    ],
)
def test_the_card_keeps_the_value_and_a_remark_goes_under_it(
    value: str, card: str, said: str
) -> None:
    assert split_tail(value) == (card, said)


def test_a_remark_after_the_answer_lands_under_its_card() -> None:
    reply = "**Solution**\n\nwork\n\n**Answer**\n\n$x = 3$, since 3 is greater than 2"
    landed = land_answer_card(reply, None)
    assert landed.endswith("```answer\nverified: false\n$x = 3$\n```\n\nSince 3 is greater than 2.")


def test_the_rolling_sphere_card_holds_only_its_value() -> None:
    block = (
        "given: M | M | | mass of the sphere\n"
        "required: v | speed at the bottom\n"
        "formula: Energy conservation | Mgh = \\frac{7}{10}Mv^2\n"
        "substitution: v = \\sqrt{\\frac{10gh}{7}}\n"
        "answer: v | \\sqrt{\\frac{10gh}{7}} | m/s | about 1.20\\sqrt{gh}; option A gives "
        "\\sqrt{2gh}, which is the sliding-block result with no rotation"
    )
    records = [read_record(line) for line in block.split("\n")]
    solution = assemble([record for record in records if record is not None])
    landed = land_answer_card(render_worked(solution, WorkedLayout()), None)
    card = landed[landed.index("```answer") : landed.index("```", landed.index("```answer") + 3)]
    assert "option" not in card and "about" not in card
    assert landed.rstrip().endswith(
        "About $1.20\\sqrt{gh}$; option A gives $\\sqrt{2gh}$, which is the sliding-block "
        "result with no rotation."
    )


def test_each_part_card_holds_only_its_value() -> None:
    reply = "**Answer (a)**\n\n$v = 4$ m/s; it slows as it climbs\n\n**Answer (b)**\n\n$t = 2$ s"
    landed = land_part_answer_cards(reply) or ""
    assert "```answer\nverified: false\n$v = 4$ m/s\n```\n\nIt slows as it climbs." in landed
    assert "```answer\nverified: false\n$t = 2$ s\n```" in landed
