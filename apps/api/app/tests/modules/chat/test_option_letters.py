"""Lettered options in one plain style, and the question they answer.

The owner's Greeting chat (2026-11-15): "🅰️ Roman Empire / 🅱️ Greek Empire / 🅲 Ottoman
Empire". 🅰️ and 🅱️ drew as colour emoji and 🅲 as a plain glyph, the emoji pass left
"🅰Roman Empire" at "A few", and the phone ran the three lines together.
"""

from __future__ import annotations

import pytest

from app.modules.chat.emoji_placement import place_emoji
from app.modules.chat.option_letters import asked_options, plain_option_letters

_PLAIN = "A) Roman Empire\n\nB) Greek Empire\n\nC) Ottoman Empire"


@pytest.mark.parametrize(
    "options",
    [
        # As the chat wrote them, and without the variation marks.
        "\U0001f170️ Roman Empire\n\U0001f171️ Greek Empire\n\U0001f172 Ottoman Empire",
        "\U0001f170 Roman Empire\n\U0001f171 Greek Empire\n\U0001f172 Ottoman Empire",
        "A) Roman Empire\nB) Greek Empire\nC) Ottoman Empire",
        "A. Roman Empire\nB. Greek Empire\nC. Ottoman Empire",
        "(A) Roman Empire\n(B) Greek Empire\n(C) Ottoman Empire",
        "**A.** Roman Empire\n**B.** Greek Empire\n**C.** Ottoman Empire",
        "**A) Roman Empire**\n**B) Greek Empire**\n**C) Ottoman Empire**",
        "- A) Roman Empire\n- B) Greek Empire\n- C) Ottoman Empire",
        # Blank lines between them already.
        "\U0001f170️ Roman Empire\n\n\U0001f171️ Greek Empire\n\n\U0001f172 Ottoman Empire",
    ],
)
def test_every_option_style_becomes_one_plain_paragraph_each(options: str) -> None:
    reply = f"**Which empire built the Colosseum?**\n{options}\nType A, B, or C."
    assert plain_option_letters(reply) == (
        f"**Which empire built the Colosseum?**\n\n{_PLAIN}\n\nType A, B, or C."
    )


def test_an_options_markup_stays_and_the_emoji_pass_leaves_the_letters() -> None:
    reply = "Q?\n\n\U0001f170️ **Mars** 🪐\n\U0001f171️ $x_1$\n\U0001f172 Jupiter"
    plain = plain_option_letters(reply)
    assert plain == "Q?\n\nA) **Mars** 🪐\n\nB) $x_1$\n\nC) Jupiter"
    # At "A few" the emoji pass used to leave "🅰Roman Empire"; the letters are text now.
    assert "A) **Mars**" in place_emoji(plain, "some", user_wrote_emoji=False)


@pytest.mark.parametrize(
    "text",
    [
        # One option is no run, and a run starts at A.
        "A. Smith wrote it.",
        "B) Paris\nC) Rome",
        # A dialogue's speakers.
        "A: Hi there\nB: Hello",
        # Inside a fence: code or a card.
        "```\nA) one\nB) two\n```",
    ],
)
def test_text_that_is_not_a_run_of_options_is_left_alone(text: str) -> None:
    assert plain_option_letters(text) == text


def test_the_question_above_the_options_is_read() -> None:
    reply = (
        "**B is correct!** The Seine.\n\nNext question: **Which planet is closest to the "
        "Sun?** 🪐\n\n\U0001f170️ Venus\n\U0001f171️ Mercury\n\U0001f172 Mars\n\n"
        "Type A, B, or C. 🎯"
    )
    asked = asked_options(reply)
    assert asked is not None
    assert asked.question == "Which planet is closest to the Sun?"
    assert [(o.letter, o.plain) for o in asked.options] == [
        ("A", "Venus"),
        ("B", "Mercury"),
        ("C", "Mars"),
    ]


@pytest.mark.parametrize(
    "reply",
    [
        # A lettered outline under no question.
        "Here's the plan:\n\nA) Book the flights\nB) Reserve a hotel\n\nWant dates next?",
        # The reply goes on well past the options.
        "Which?\n\nA) One\nB) Two\n\n" + "More about it. " * 30 + "\n\nAnd more.\n\nAnd more.",
        # In a code fence.
        "```\nWhich?\nA) One\nB) Two\n```",
        "Python is a language. Want to learn more?",
    ],
)
def test_a_reply_that_asks_no_lettered_question_has_none(reply: str) -> None:
    assert asked_options(reply) is None
