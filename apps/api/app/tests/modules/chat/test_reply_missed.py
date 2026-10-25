""" "What?" right after a reply means the user did not follow it.

After a Spanish reply in an English app, "What?" got "Gd: good, or something else?": the
model read it as a message it could not make out and copied the unclear-message example.
"""

from __future__ import annotations

import pytest

from app.modules.chat.prompt_constants.message_notes import message_notes
from app.modules.chat.prompt_constants.reply_missed import REPLY_MISSED_HINT, reply_missed_hint
from app.modules.chat.prompt_constants.shared_numbers import SHARED_NUMBERS_HINT
from app.modules.chat.prompt_constants.unclear import UNCLEAR_MESSAGE_HINT

_AFTER_A_REPLY = [
    ("user", "Explícame la fotosíntesis en dos frases"),
    ("assistant", "La fotosíntesis es el proceso por el cual las plantas convierten la luz..."),
]


@pytest.mark.parametrize(
    "query",
    [
        "What?",
        "what",
        "huh?",
        "??",
        "what do you mean?",
        "I don't get it",
        "i dont understand",
        "come again?",
        "Sorry?",
        "I'm lost",
        "that makes no sense",
    ],
)
def test_what_after_a_reply_asks_for_it_again(query: str) -> None:
    hint = reply_missed_hint(query, _AFTER_A_REPLY)
    assert hint is not None and hint.startswith(REPLY_MISSED_HINT)
    # Typed in English, so the reply comes back in English, not the language of the reply.
    assert hint.endswith("English, the language of their message.") or query == "??"


@pytest.mark.parametrize(
    "query",
    [
        # A question of its own, a remark, or a follow-up about the reply.
        "What time is it?",
        "what is photosynthesis",
        "huh, interesting",
        "sorry for the late reply",
        "What a game!",
        "what about the roots?",
        "I don't get why plants need light",
    ],
)
def test_a_question_of_its_own_is_not_a_missed_reply(query: str) -> None:
    assert reply_missed_hint(query, _AFTER_A_REPLY) is None


def test_with_no_reply_before_there_is_nothing_to_follow() -> None:
    assert reply_missed_hint("What?", []) is None
    assert reply_missed_hint("What?", [("user", "hi")]) is None


def test_the_notes_sit_in_order_and_only_when_they_apply() -> None:
    rain = "Monthly rainfall: Jan 15, Feb 30, Mar 60, Apr 85"
    assert message_notes("??", _AFTER_A_REPLY) == [REPLY_MISSED_HINT]
    assert message_notes(rain, [])[0].startswith(SHARED_NUMBERS_HINT)
    assert message_notes("Teach me python", _AFTER_A_REPLY) == []


def test_the_unclear_rule_gives_no_reply_to_copy() -> None:
    """Its examples were whole replies a small model sent as they were."""
    assert "Gd:" not in UNCLEAR_MESSAGE_HINT
    assert "Were you still typing?" not in UNCLEAR_MESSAGE_HINT
