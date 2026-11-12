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
        # What the value is written with stays, whatever the words (reviews of #2303).
        ("$A = 12$ square meters", "$A = 12$ square meters", ""),
        ("$v = 60$ miles per hour", "$v = 60$ miles per hour", ""),
        ("$v = 5$ meters/second", "$v = 5$ meters/second", ""),
        ("$n = 12$ students", "$n = 12$ students", ""),
        ("$x = 3$ approximately", "$x = 3$ approximately", ""),
        ("$v = 8$ m/s north", "$v = 8$ m/s north", ""),
        ("$h = 20$ m above the ground", "$h = 20$ m above the ground", ""),
        ("$n = 0.5$ mol of oxygen", "$n = 0.5$ mol of oxygen", ""),
        ("$r = 5\\%$ per year", "$r = 5\\%$ per year", ""),
        (
            "$\\theta = 30^\\circ$ above the horizontal",
            "$\\theta = 30^\\circ$ above the horizontal",
            "",
        ),
        ("$F$ = 10 newtons", "$F$ = 10 newtons", ""),
        ("$x$ ≈ 3.2 m", "$x$ ≈ 3.2 m", ""),
        ("$M$ = 1,073.64 USD per month", "$M$ = 1,073.64 USD per month", ""),
        ("$x = 3$ and $y = 4$", "$x = 3$ and $y = 4$", ""),
        ("$t = 2$ s and $t = 4$ s", "$t = 2$ s and $t = 4$ s", ""),
        ("$x = 2$ or $x = -2$", "$x = 2$ or $x = -2$", ""),
        ("$x = 3$ m/s.", "$x = 3$ m/s.", ""),
        # A clause break starts the remark, with or without a mark before it.
        (
            "$V = 5$ cubic centimeters, about a teaspoon",
            "$V = 5$ cubic centimeters",
            "About a teaspoon.",
        ),
        ("$x = 3$ and so $y = 4$", "$x = 3$", "And so $y = 4$."),
        ("$x = 3$ m/s since the net force is zero", "$x = 3$ m/s", "Since the net force is zero."),
        ("$v = 4$ m/s. It slows down as it climbs.", "$v = 4$ m/s", "It slows down as it climbs."),
        # Second review round of #2303.
        ("$M = \\$1{,}073.64$ per month", "$M = \\$1{,}073.64$ per month", ""),
        ("$v = 8$ m/s, 30° north of east", "$v = 8$ m/s, 30° north of east", ""),
        ("$x = 2$ as well as $x = 3$", "$x = 2$ as well as $x = 3$", ""),
        ("Speed = 4 m/s, since it starts from rest", "Speed = 4 m/s", "Since it starts from rest."),
        ("$x = 3$ as expected", "$x = 3$", "As expected."),
        # A value written without maths marks.
        ("x = 3, since 3 > 2", "x = 3", "Since 3 > 2."),
        ("x = 2, x = -2", "x = 2, x = -2", ""),
        ("x = 3, y = 4, since both fit", "x = 3, y = 4", "Since both fit."),
        ("v = 4 m/s; it slows as it climbs", "v = 4 m/s", "It slows as it climbs."),
        ("\\[x = 3\\], since 3 > 2", "\\[x = 3\\]", "Since 3 > 2."),
        # A range written with an en dash is one value; a spaced en dash opens a remark.
        ("T = 2\u20133 seconds", "T = 2\u20133 seconds", ""),
        ("$v = 3$\u2013$5$ m/s", "$v = 3$\u2013$5$ m/s", ""),
        ("$t = 2$ s \u2013 it lands then", "$t = 2$ s", "It lands then."),
        # Words that are no unit are a remark.
        ("$x = 3$ so it works", "$x = 3$", "So it works."),
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
    assert landed.endswith("```answer\nverified: false\nx = 3\n```\n\nSince 3 is greater than 2.")


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


def test_a_note_with_nested_maths_is_one_maths_run() -> None:
    """Review of #2303: one level of braces split \\sqrt{\\frac{10gh}{7}} in two."""
    from app.modules.chat.worked_prose import prose_maths

    assert prose_maths(r"about \sqrt{\frac{10gh}{7}}") == r"about $\sqrt{\frac{10gh}{7}}$"
    assert prose_maths(r"about 1.20\sqrt{gh}; A gives \sqrt{2gh}.") == (
        r"about $1.20\sqrt{gh}$; A gives $\sqrt{2gh}$."
    )
    assert prose_maths("east") == "east"


@pytest.mark.parametrize(
    ("note", "shown"),
    [
        (r"about \frac{v_0}{2}", r"about $\frac{v_0}{2}$"),
        (r"about $\frac{v_0}{2}$", r"about $\frac{v_0}{2}$"),
        (r"5\% error", "5% error"),
        (r"a\,b", "a b"),
        (r"1.20\,\sqrt{gh}", r"$1.20 \sqrt{gh}$"),
        ("**east**, the `v_0` axis", "east, the $v_0$ axis"),
        ("east", "east"),
    ],
)
def test_a_note_keeps_its_maths_and_loses_its_marks(note: str, shown: str) -> None:
    """Review of #2303: marks were stripped before the maths was found, so subscripts went,
    and a backslash before a non-letter showed raw."""
    from app.modules.chat.worked_prose import prose_maths

    assert prose_maths(note) == shown
