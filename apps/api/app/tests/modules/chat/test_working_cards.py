"""An unchecked card held to the working's last line: an expression left unworked and a
card that is not its value (live, 2026-11-22: "5 + 20" carded 37, "D = 4 - 12" carded -7)."""

from __future__ import annotations

import pytest

from app.modules.chat.working_cards import held_cards


def _reply(working: str, card: str, closing: str = "") -> str:
    reply = f"{working}\n\n**Answer**\n\n```answer\nverified: false\n{card}\n```\n"
    return f"{reply}\n{closing}" if closing else reply


_PERCENT = (
    "**Given**  \n$base = 80$  \n$percent = 25\\,\\%$  \n$addend = 5$\n\n**Substitution**  \n"
    "$\\text{part} = 80 \\times 0.25$  \n$\\text{part} = 20$  \n$\\text{total} = 5 + 20$"
)
_DISCRIMINANT = "**Substitution**  \n$D = 2^2 - 4(3)(1)$  \n$D = 4 - 12$"


@pytest.mark.parametrize(
    ("working", "card", "closing", "fixed_card", "fixed_closing"),
    [
        (
            _PERCENT,
            "total = 37",
            "Add **5** to **20** for a final answer of **37**.",
            "total = 25",
            "Add **5** to **20** for a final answer of **25**.",
        ),
        (
            _DISCRIMINANT,
            "D = -7",
            "Since -7 is negative, the equation has no real roots.",
            "D = -8",
            "Since -8 is negative, the equation has no real roots.",
        ),
        # A bare expression, a card with no symbol, its decimals kept.
        ("$\\text{x} = 1.5$, $\\text{y} = 2.25$\n\n$1.5 + 2.25$", "3.85", "", "3.75", ""),
    ],
)
def test_the_card_takes_the_value_its_working_makes(
    working: str, card: str, closing: str, fixed_card: str, fixed_closing: str
) -> None:
    text, note = held_cards(_reply(working, card, closing))
    assert note is None
    assert text == _reply(working, fixed_card, fixed_closing)


@pytest.mark.parametrize(
    ("working", "card"),
    [
        # The card is the expression's value, rounded once.
        ("$t = 10/3$", "t = 3.33"),
        ("$t = 10/3$", "t \\approx 3.3"),
        ("$\\text{total} = 5 + 20$", "total = 25"),
        # A count rounded up as the question needs.
        ("$\\text{buses} = 45 / 12$", "buses = 4"),
        # Another name: c^2 is worked, c is carded.
        ("$c^2 = 9 + 16$", "c = 5"),
        ("$c^2 = 9 + 16$", "5"),
        # The line reached its value; the card is another step's.
        ("$x = 3 + 4 = 7$", "x = 9"),
        # A unit the working did not use.
        ("$d = 7000 + 200\\,\\text{m}$", "d = 7.2\\,\\text{km}"),
        # Words between the line and the card work more out.
        ("$\\text{total} = 5 + 20$, then add the 12 extra ones.", "total = 37"),
    ],
)
def test_a_card_its_working_does_not_contradict_stays(working: str, card: str) -> None:
    reply = _reply(working, card)
    assert held_cards(reply) == (reply, None)


def test_a_number_of_the_question_is_the_workings() -> None:
    """The live reply never wrote the 5 it added: the question did (2026-11-22)."""
    working = "$\\frac{25}{100} \\times 80$  \n$0.25 \\times 80 = 20$  \nbase + result\n$5 + 20$"
    reply = _reply(working, "total = 37")
    assert held_cards(reply)[1] is not None
    text, note = held_cards(reply, "what is 5 plus 25% of 80?")
    assert note is None
    assert text == _reply(working, "total = 25")


def test_a_checked_card_is_the_solvers() -> None:
    reply = "$\\text{total} = 5 + 20$\n\n```answer\nverified: true\ntotal = 37\n```\n"
    assert held_cards(reply) == (reply, None)


@pytest.mark.parametrize(
    "working",
    [
        # 20 is no value the working reached: the expression may be the slip, not the card.
        "$\\text{part} = 32$  \n$\\text{total} = 5 + 20$",
        # An earlier step slips too.
        "$\\text{part} = 80 \\times 0.25 = 21$  \n$\\text{total} = 5 + 20$",
    ],
)
def test_a_slip_whose_side_is_unknown_is_named(working: str) -> None:
    reply = _reply(working, "total = 37")
    text, note = held_cards(reply)
    assert text == reply
    assert note == "Check the answer: $5 + 20 = 25$, not $37$."


def test_only_the_last_card_is_corrected() -> None:
    """The text after an earlier card is the next part's working, not its summary."""
    first = _reply("$a = 5$  \n$b = 20$  \n$\\text{total} = 5 + 20$", "total = 37")
    reply = first + "\n**(b)**\n$y = 37 + 1$\n\n```answer\nverified: false\ny = 38\n```\n"
    assert held_cards(reply) == (reply, "Check the answer: $5 + 20 = 25$, not $37$.")


def test_a_wrong_value_the_working_also_wrote_leaves_the_closing_line() -> None:
    working = "$a = 20$  \n$b = 5$  \n$\\text{total} = a + b$  \n$\\text{total} = 20 + 5$"
    reply = _reply(working, "total = 20", "So the total is 20.\n\nHope that helps!")
    text, note = held_cards(reply)
    assert note is None
    assert "total = 25" in text
    assert "So the total is 20." not in text and "Hope that helps!" in text
