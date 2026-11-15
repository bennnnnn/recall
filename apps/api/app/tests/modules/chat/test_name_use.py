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
from app.modules.chat.prompt_sections import STABLE_SECTIONS


@pytest.mark.parametrize(
    "reply, without",
    [
        ("Hey bini! 👋 What's on your mind?", "Hey! 👋 What's on your mind?"),
        ("**A is correct, bini!** 🎉 France.", "**A is correct!** 🎉 France."),
        ("Sorry, bini, that's fair.", "Sorry, that's fair."),
        ("Bini, call 911 now.", "Call 911 now."),
        ('Bini, "To eat" is a plot twist.', '"To eat" is a plot twist.'),
        ("Alright, Bini — round two.", "Alright — round two."),
        ("Great question, bini!", "Great question!"),
        # Not where it addresses them (review, 2026-11-15): kept.
        ("I'm glad. Bini, rest well.", None),
        ("Bini is a lovely name.", None),
        ("Bini, Anna and Carl are on the team.", None),
        ("Invite Anna, Bini, and Carl.", None),
        ("Call Bini.", None),
        ("Head down Bini Street, then turn left.", None),
        ("Here's your email:\n\nDear Bini,\n\nThanks for the invite.", None),
        ("Hi Bini, thanks for yesterday!", None),
        ("Best,\nBini", None),
        ("- Great work, Bini!", None),
        ("> Great work, Bini!", None),
        ("Run `print('Hi, Bini!')` to test.", None),
        ("```copy\nHi Sam, it's Bini, see you soon.\n```", None),
        # Another case, or another word that holds the name.
        ("Great question, BINI!", None),
        ("Try the binicorn app, sir.", None),
    ],
)
def test_the_name_goes_from_where_it_addresses_them(reply: str, without: str | None) -> None:
    # The owner's profile spells it "bini"; "Bini" is the same name capitalised.
    assert without_name(reply, "bini") == (reply if without is None else without)


@pytest.mark.parametrize(
    ("name", "reply"),
    [
        ("Max", "Use 8 GB, max."),
        ("Will", "Free will."),
        ("Joy", "Pure joy!"),
        ("Grace", "Saving grace."),
        ("May", "Last May."),
        ("Summer", "Hello summer!"),
        ("Hope", "Lost hope."),
    ],
)
def test_a_name_that_is_a_word_stays_a_word(name: str, reply: str) -> None:
    # Matched as the profile spells it or capitalised, and only where it addresses them.
    assert without_name(reply, name) == reply


def test_the_name_waits_two_replies_after_one_used_it() -> None:
    def row(role: str, text: str) -> SimpleNamespace:
        return SimpleNamespace(role=role, content=text)

    named = [row("assistant", "Hey bini!"), row("user", "hi"), row("assistant", "Sure.")]
    assert named_lately("bini", named)
    assert not named_lately("bini", [*named, row("user", "x"), row("assistant", "Okay.")])
    assert not named_lately("bini", [])


def test_personal_help_and_the_distress_rule_are_in_every_prompt() -> None:
    stable = [section for section in STABLE_SECTIONS if section.name == "tone"]
    user = SimpleNamespace(response_tone="casual", emoji_use="some")
    turn = SimpleNamespace(user=user)
    assert PERSONAL_HELP_RULE in stable[0].render(turn)  # type: ignore[arg-type]
    # Beside the message: with it only at the top, the free model said when to fire a gun.
    reader = SimpleNamespace(emoji_use="more", locale="en", custom_instructions="")
    assert DISTRESS_RULE in message_notes("I have a gun. Can I shoot", [], reader)


@pytest.mark.parametrize(
    ("asked", "kept"),
    [("what's my name?", True), ("is Bini a nice name", True), ("thanks", False)],
)
def test_a_reply_about_the_name_keeps_it(asked: str, kept: bool) -> None:
    from app.modules.chat.name_use import spare_name_pass

    ctx = SimpleNamespace(
        user=SimpleNamespace(name="Bini"),
        user_message_content=asked,
        recent_messages=[SimpleNamespace(role="assistant", content="Hey Bini!")],
    )
    state = SimpleNamespace(server_text=False, ctx=ctx, text="Bini, of course!")
    out = spare_name_pass(state)  # type: ignore[arg-type]
    assert out == ("Bini, of course!" if kept else "Of course!")
