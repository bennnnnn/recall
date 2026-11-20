"""A precision said alone ("1 digit") after an answer: the server shows the card again in it
(the owner's chat, 2026-11-20: "3.1 m/s … as ordered: 3 m/s … 3.13 m/s is the truer figure")."""

from __future__ import annotations

import pytest

from app.modules.chat.card_numbers import card_numbers
from app.modules.chat.precision_reply import rounded_again
from app.services.rounding_rule import asked_precision

_SPEED = (
    "**Substitution**  \n$v = \\sqrt{1\\,\\mathrm{m} \\times 9.81\\,\\mathrm{m/s²}}$  \n"
    "$v = 3.13209\\,\\mathrm{m/s}$\n\n**Answer**\n\n"
    "```answer\nverified: true\nv = 3.13\\,\\mathrm{m/s}\n```"
)


def _card(value: str) -> str:
    return f"```answer\nverified: true\nv = {value}\\,\\mathrm{{m/s}}\n```"


@pytest.mark.parametrize(
    ("said", "value"),
    [
        ("1 digit", "3.1"),
        ("3 dp", "3.132"),  # from the working's 3.13209, not the card's 3.13
        ("2 sig figs", "3.1"),
        ("no rounding", "3.13209"),
    ],
)
def test_the_last_card_again_in_the_precision_asked(said: str, value: str) -> None:
    again = rounded_again(said, _SPEED)
    assert again == _card(value)
    # The finalize pass shows the turn's cards in the same precision: it keeps them.
    assert card_numbers(again, asked_precision(said)) == again


def test_every_card_of_a_reply_in_parts() -> None:
    reply = (
        "$T = 104.43\\,\\mathrm{N}$\n\n```answer\nverified: true\nT = 104.43\\,\\mathrm{N}\n```\n\n"
        "$T = 45.57\\,\\mathrm{N}$\n\n```answer\nverified: true\nT = 45.57\\,\\mathrm{N}\n```"
    )
    assert rounded_again("1 dp", reply) == (
        "```answer\nverified: true\nT = 104.4\\,\\mathrm{N}\n```\n\n"
        "```answer\nverified: true\nT = 45.6\\,\\mathrm{N}\n```"
    )


def test_each_part_s_card_keeps_its_heading() -> None:
    reply = (
        "**Answer (a)**\n\n```answer\nverified: true\nT = 104.43\\,\\mathrm{N}\n```\n\n"
        "**Answer (b)**\n\n```answer\nverified: true\nT = 45.57\\,\\mathrm{N}\n```"
    )
    assert rounded_again("ok 1 dp", reply) == (
        "**Answer (a)**\n\n```answer\nverified: true\nT = 104.4\\,\\mathrm{N}\n```\n\n"
        "**Answer (b)**\n\n```answer\nverified: true\nT = 45.6\\,\\mathrm{N}\n```"
    )


@pytest.mark.parametrize(
    ("said", "prior"),
    [
        ("3 dp", _card("3.13")),  # no working: 3.13 is no 3.130
        ("no rounding", _card("3.13")),
        ("1 digit", "Do you mean one decimal place or one significant figure?"),  # no card
        ("1 digit", None),
        ("Explain 2 sig figs", _SPEED),  # asks more than a precision
        ("1 dp", "```answer\nverified: true\n\\$1,234.57\n```"),  # money stays to the cent
        # One place of 0.0456 A shows no figure at all: no 0.0 A (review).
        (
            "1 dp",
            "$I = 0.045632\\,\\mathrm{A}$\n\n```answer\nverified: true\nI = 0.0456\\,\\mathrm{A}\n```",
        ),
        # "The exact answer" is √2, no decimal the server rounds (review).
        ("exact answer", "$x = \\sqrt{2} = 1.414214$\n\n```answer\nverified: false\nx = 1.41\n```"),
    ],
)
def test_nothing_rounded_again(said: str, prior: str | None) -> None:
    assert rounded_again(said, prior) is None
