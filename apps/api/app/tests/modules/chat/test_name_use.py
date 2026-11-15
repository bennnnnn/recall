"""The user's name now and then, and a frightening turn met plainly.

The owner's Greeting chat (2026-11-15): "bini" in 94 of 100 replies, every line of an
emergency role-play included, which also told the user when to fire a gun.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.chat.message_notes import message_notes
from app.modules.chat.name_use import named_lately, without_name
from app.modules.chat.prompt_constants.care import DISTRESS_RULE, PERSONAL_HELP_RULE
from app.modules.chat.prompt_profile import _NAME_USE, format_user_name_only_block
from app.modules.chat.prompt_sections import STABLE_SECTIONS


@pytest.mark.parametrize(
    "reply, without",
    [
        ("Hey bini! 👋 What's on your mind?", "Hey! 👋 What's on your mind?"),
        ("**A is correct, bini!** 🎉 France.", "**A is correct!** 🎉 France."),
        ("Sorry, bini, that's fair.", "Sorry, that's fair."),
        ("Bini, call 911 now.", "Call 911 now."),
        ('Bini, "To eat" is a plot twist.', '"To eat" is a plot twist.'),
        ("I'm glad. Bini, rest well.", "I'm glad. Rest well."),
        ("Alright, Bini — round two.", "Alright — round two."),
        # A sentence about them, a sign-off and a fence keep it.
        ("Bini is a lovely name.", "Bini is a lovely name."),
        ("Best,\nBini", "Best,\nBini"),
        ("```copy\nHi Sam, it's Bini, see you soon.\n```", None),
        # Another word that holds the name keeps it.
        ("Try the binicorn app, sir.", None),
    ],
)
def test_the_name_goes_from_where_it_addresses_them(reply: str, without: str | None) -> None:
    assert without_name(reply, "Bini") == (reply if without is None else without)


def test_the_name_waits_two_replies_after_one_used_it() -> None:
    def row(role: str, text: str) -> SimpleNamespace:
        return SimpleNamespace(role=role, content=text)

    named = [row("assistant", "Hey bini!"), row("user", "hi"), row("assistant", "Sure.")]
    assert named_lately("Bini", named)
    assert not named_lately("Bini", [*named, row("user", "x"), row("assistant", "Okay.")])
    assert not named_lately("Bini", [])


def test_the_prompt_says_to_use_the_name_rarely() -> None:
    user = SimpleNamespace(name="Bini Tesfaye")
    assert _NAME_USE in format_user_name_only_block(user)  # type: ignore[arg-type]


def test_personal_help_and_the_distress_rule_are_in_every_prompt() -> None:
    stable = [section for section in STABLE_SECTIONS if section.name == "tone"]
    user = SimpleNamespace(response_tone="casual", emoji_use="some")
    turn = SimpleNamespace(user=user)
    assert PERSONAL_HELP_RULE in stable[0].render(turn)  # type: ignore[arg-type]
    # Beside the message: with it only at the top, the free model said when to fire a gun.
    reader = SimpleNamespace(emoji_use="more", locale="en", custom_instructions="")
    assert DISTRESS_RULE in message_notes("I have a gun. Can I shoot", [], reader)
