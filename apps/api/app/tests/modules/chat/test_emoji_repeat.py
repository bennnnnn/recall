"""The same sign-off emoji reply after reply goes; every other emoji stays.

The 80-message "Friend getting married" chat at "Lots" (2026-11-19): 💛 closed the opening
line of 58 replies, and replayed with the prompt asking for an emoji that fits, one run still
had it in 40, and dropped only when both of the last two had it, in 24, alternating.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.chat.emoji_repeat import closing_emoji, repeated_emoji_pass, without_closing


def _state(text: str, *replies: str, instant: str | None = None) -> SimpleNamespace:
    recent = []
    for reply in replies:
        recent += [
            SimpleNamespace(role="user", content="and then?"),
            SimpleNamespace(role="assistant", content=reply),
        ]
    ctx = SimpleNamespace(recent_messages=recent, instant_reply=instant)
    return SimpleNamespace(text=text, ctx=ctx, server_text=instant is not None)


@pytest.mark.parametrize(
    ("text", "closing"),
    [
        ("That's a big step. 💛 Her mom is 62.", {"💛"}),
        ("Congrats! 🎉", {"🎉"}),
        ("That's exciting 💍 Do you know when?", {"💍"}),
        # Leading a heading, a list item or a label is where "Lots" puts one: not a sign-off.
        ("## 💛 Heading\n1. 💧 **Drink water** — every day.\n**💛 Label:** text", set()),
        ("😂 Ha, okay.", set()),
        # Inside a sentence, in a table row, in code or a fence: not closing anything.
        ("I love 💛 you all.", set()),
        ("| a 💛 |\n`x 💛`\n```\nok 💛\n```", set()),
        # A list item, a quote, and a mark that grades or compares (review, 2026-11-19).
        ("- Battery: 20 hours ✅\n- Price: $999 ❌\n> Nice. 💛", set()),
        ("Step one is right. ✓ Step two is not. ✗", set()),
    ],
)
def test_closing_emoji_reads_only_sentence_ends(text: str, closing: set[str]) -> None:
    assert closing_emoji(text) == closing


def test_without_closing_drops_only_the_repeated_one() -> None:
    text = "That's a big step. 💛 Her mom is 62. 🎉\n\n1. 💛 **Ask her** — today."
    assert without_closing(text, {"💛"}) == (
        "That's a big step. Her mom is 62. 🎉\n\n1. 💛 **Ask her** — today."
    )


@pytest.mark.parametrize(
    "replies",
    [
        ("Okay. 💛 Take care.", "I hear you. 💛"),
        # One of the last two is enough: the replay alternated it.
        ("Okay. 💛 Take care.", "I hear you."),
        ("I hear you.", "Okay. 💛"),
    ],
)
def test_a_sign_off_one_of_the_last_two_replies_used_goes(replies: tuple[str, ...]) -> None:
    state = _state("Wow, that's big. 💛 Enjoy it.", *replies)
    assert repeated_emoji_pass(state) == "Wow, that's big. Enjoy it."  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "replies",
    [
        # Another emoji each time.
        ("Okay. 🎉", "I hear you. 💍"),
        # Three replies back is long enough ago.
        ("Fine. 💛", "Okay.", "I hear you."),
        # One leading a label or heading is not a sign-off.
        ("1. 💛 **Ask her** — today.", "## 💛 Plans"),
        # No reply yet.
        (),
    ],
)
def test_an_emoji_not_repeated_stays(replies: tuple[str, ...]) -> None:
    state = _state("Wow, that's big. 💛", *replies)
    assert repeated_emoji_pass(state) == "Wow, that's big. 💛"  # type: ignore[arg-type]


def test_two_words_an_emoji_joined_keep_a_space() -> None:
    assert without_closing("Wow💛Enjoy it.", {"💛"}) == "Wow Enjoy it."


def test_a_lesson_keeps_its_own_emoji() -> None:
    lesson = "### Lesson 2: Loops\n\nNice work, that's loops. 🎉"
    state = _state(lesson, "### Lesson 1: Names\n\nWell done. 🎉", "Ready? 🎉")
    assert repeated_emoji_pass(state) == lesson  # type: ignore[arg-type]


def test_server_text_is_never_touched() -> None:
    state = _state("Done. 💛", "Okay. 💛", "Sure. 💛", instant="Done. 💛")
    assert repeated_emoji_pass(state) == "Done. 💛"  # type: ignore[arg-type]
