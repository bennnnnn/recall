"""A conversation about the user's own life, answered as one (an 80-message chat, 2026-11-19).

"Friend getting married" went from a girlfriend's wedding to her mother, money and sex.
The replies offered help in 36 of 80, read news as a yes to their own offer, raised the bank
and the $500,000 in nearly every reply, ended on 💛 at "Lots", refused things never asked,
and told the user to call 911 twelve times while he said it felt good. The model judges what
a turn is; these rules say what it does then, and each sits where the model reads it.

Wording is the golden test's to hold (``test_prompt_golden``, ``test_prompt_rule_text``): these
check where each rule sits, what it no longer says, and the safety promises, which stay word
for word whatever else is reworded. The measured replies are
``docs/qa/2026-11-19-natural-chat-replay.md``.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.modules.chat.context_window import ASSISTANT_CONCERNS_RULE, SUMMARY_SYSTEM_PROMPT
from app.modules.chat.message_notes import message_notes
from app.modules.chat.prompt_constants.care import DISTRESS_RULE
from app.modules.chat.prompt_constants.conversation import (
    NO_RECAP_NOTE,
    OWN_MISTAKE_HINT,
    SUMMARY_LEAD,
)
from app.modules.chat.prompt_constants.unclear import UNCLEAR_MESSAGE_HINT
from app.modules.chat.response_tone import _EMOJI_FITS, EMOJI_HINTS, emoji_note

_READER = SimpleNamespace(emoji_use="more", locale="en", custom_instructions="")


def _after_a_reply(message: str) -> list[str]:
    exchange = [
        SimpleNamespace(role="user", content="My gf is getting married"),
        SimpleNamespace(role="assistant", content="Oh wow, that's big news. How are you?"),
    ]
    return message_notes(message, exchange, _READER)


def test_news_is_not_a_yes_to_an_offer() -> None:
    # "She bought me a house …" after "Would it help to plan what to ask your bank?" got
    # "Yes, let's work out what to ask the bank".
    assert "A message after a question you asked is its answer" not in UNCLEAR_MESSAGE_HINT


def test_the_concern_and_fact_rules_sit_beside_the_message() -> None:
    # Told once in the system prompt, far from the message, a small model loses a rule; both
    # sit beside every message that follows a reply.
    notes = _after_a_reply("She bought me a house, a car and shoes")
    assert NO_RECAP_NOTE in notes
    assert OWN_MISTAKE_HINT in notes
    assert DISTRESS_RULE in notes
    # Never at the cost of someone's safety: a topic is dropped unless safety depends on it,
    # and a crisis line or a safety step is never "said already".
    assert "unless someone's safety depends on it" in NO_RECAP_NOTE  # safety phrase
    assert (
        "A crisis line or a safety step is given again whenever suicide" in NO_RECAP_NOTE
    )  # safety phrase


def test_a_hard_situation_gets_one_check_and_911_or_a_crisis_line_only_for_its_cases() -> None:
    # Main, replayed the same evening, gave 988 in 54 of 80 replies with no word of self-harm;
    # the branch's first wording still said "call 911 if the threats get worse" nine times.
    # The cases stay word for word: a stated threat, violence, an injury, being kept in, not
    # feeling safe, and suicide or self-harm.
    assert (
        "to call 911 or to call a crisis line is for a stated threat" in DISTRESS_RULE
    )  # safety phrase
    assert "being kept from leaving, their saying they don't" in DISTRESS_RULE  # safety phrase
    assert "or talk of suicide or self-harm" in DISTRESS_RULE  # safety phrase
    # Self-harm keeps its own rule: never dropped, the crisis line given again after a "jk".
    assert "Talk of suicide or self-harm is never dropped" in DISTRESS_RULE  # safety phrase
    assert 'after a "jk", check in once, gently, and give 988' in DISTRESS_RULE  # safety phrase


def test_the_summary_keeps_the_users_facts_not_the_assistants_warnings() -> None:
    # Every fold wrote "Assistant advises getting a lawyer" again, and the summary sits above
    # every later turn: its Facts and its Topics both leave the assistant's warnings out.
    assert SUMMARY_SYSTEM_PROMPT.count(ASSISTANT_CONCERNS_RULE) == 2
    # A warning it records is never a reason to hold back a crisis line.
    assert "unless it is a crisis line or a safety step" in SUMMARY_LEAD  # safety phrase


def test_lots_of_emoji_still_fit_their_line() -> None:
    # A 💛 opened 58 of 80 replies at "Lots", whatever the line said.
    assert _EMOJI_FITS in EMOJI_HINTS["more"]
    note = emoji_note("more", "")
    assert note is not None and _EMOJI_FITS in note
    # "A few" already allows none in a sentence; its line is unchanged.
    assert _EMOJI_FITS not in EMOJI_HINTS["some"]
