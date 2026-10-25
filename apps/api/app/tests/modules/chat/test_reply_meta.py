"""A reply says nothing about the turn: no clock read back unasked, no "you accepted my offer"."""

from __future__ import annotations

import pytest

from app.modules.chat.reply_meta import without_turn_meta

_CLOCK = "It's currently **Sunday, October 25, 2026, 6:15 PM EDT**."


@pytest.mark.parametrize(
    ("reply", "asked", "kept"),
    [
        # Live chat (2026-10-25): a short turn got the clock as filler.
        (f"Got it. {_CLOCK}\n\nWhich goal fits best?", "1", "Got it.\n\nWhich goal fits best?"),
        (
            "Got it, Dev. It's Sunday, October 25, 2026, 7:01 PM EDT, so your session "
            "can start tonight.",
            "Okay.",
            "Got it, Dev.",
        ),
        (
            "Dev, you accepted my offer, so here is the 20% down payment comparison.",
            "Yes",
            "Here is the 20% down payment comparison.",
        ),
        (
            "You accepted my last offer again, so here is the 15-year comparison.",
            "yes",
            "Here is the 15-year comparison.",
        ),
    ],
)
def test_turn_meta_goes(reply: str, asked: str, kept: str) -> None:
    assert without_turn_meta(reply, asked) == kept


@pytest.mark.parametrize(
    ("reply", "asked"),
    [
        # The message is about the day or the time: the date is the answer.
        ("Today is Sunday, October 25, 2026, so tomorrow is Monday.", "It is monday"),
        (_CLOCK, "what time is it"),
        ("It's Sunday, October 25, 2026.", "what's today's date"),
        # A date inside a sentence, a plan or code is content.
        ("Read for 20 minutes each evening, starting tonight, Sunday, October 25, 2026.", "Yes"),
        ("```\nIt's Sunday, October 25, 2026\n```", "print the date line"),
        ("Your offer was accepted by the seller, so here are the next steps.", "yes"),
        # A reply that is only the clock keeps it rather than going empty.
        (_CLOCK, "ok"),
    ],
)
def test_other_text_stays(reply: str, asked: str) -> None:
    assert without_turn_meta(reply, asked) == reply
