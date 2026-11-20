"""A conversation about the user's own life, answered as one (an 80-message chat, 2026-11-19).

"Friend getting married" went from a girlfriend's wedding to her mother, money and sex.
The replies offered help in 36 of 80, read news as a yes to their own offer, raised the bank
and the $500,000 in nearly every reply, ended on 💛 at "Lots", refused things never asked,
and told the user to call 911 twelve times while he said it felt good. Each rule came from the
prompt itself, and the replay (``docs/qa/2026-11-19-natural-chat-replay.md``) found the rest in
the chat's summary. These tests hold that the rules that asked for it are gone and that what
replaced them sits where the model reads it; the wording itself is the golden prompt's
(``test_prompt_golden``) to hold, except the safety promises, which stay word for word.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.modules.chat.context_window import ASSISTANT_CONCERNS_RULE, SUMMARY_SYSTEM_PROMPT
from app.modules.chat.message_notes import message_notes
from app.modules.chat.prompt_constants.care import DISTRESS_RULE, PERSONAL_HELP_RULE, TONE_RULES
from app.modules.chat.prompt_constants.conversation import (
    NO_RECAP_NOTE,
    OWN_MISTAKE_HINT,
    SUMMARY_LEAD,
)
from app.modules.chat.prompt_constants.format import FORMAT_CONTRACT, READER_NOTE
from app.modules.chat.prompt_constants.unclear import UNCLEAR_MESSAGE_HINT
from app.modules.chat.response_tone import EMOJI_FITS, EMOJI_HINTS, emoji_note
from app.services.time_context import KNOWN_DAY_RULE, format_now_awareness

_USER = SimpleNamespace(emoji_use="more", locale="en", custom_instructions=None)
_AFTER_A_REPLY = [
    SimpleNamespace(role="user", content="Her mom is buying me cars, shoes etc."),
    SimpleNamespace(role="assistant", content="That's a lot coming very fast."),
]


def _beside(message: str) -> list[str]:
    """The notes beside a message that follows a reply in this chat."""
    return message_notes(message, _AFTER_A_REPLY, _USER)


def test_the_rules_that_asked_for_it_are_gone() -> None:
    # An offer at the end of every reply; news read as a yes to it; the full date with every
    # weekday; any "story told as real" an emergency.
    assert "a question or an offer of one concrete next step" not in FORMAT_CONTRACT
    assert "A message after a question you asked is its answer" not in UNCLEAR_MESSAGE_HINT
    assert "When you name the weekday of a date, write the full date" not in KNOWN_DAY_RULE


def test_what_replaced_them_sits_beside_every_message_after_a_reply() -> None:
    notes = _beside("I don't want to talk to her anymore. I love the mom")
    # A conversation is answered as one; a concern is said once; news is answered as news,
    # not checked like a sum; a hard situation is met with one safety check.
    assert READER_NOTE in notes
    assert NO_RECAP_NOTE in notes
    assert OWN_MISTAKE_HINT in notes
    assert DISTRESS_RULE in notes
    assert PERSONAL_HELP_RULE in TONE_RULES


def test_a_hard_situation_keeps_the_safety_promises() -> None:
    # Main, replayed the same evening, gave 988 in 54 of 80 replies with no word of self-harm;
    # 911 and a crisis line keep their cases word for word.
    assert "to call 911 or to call a crisis line is for a" in DISTRESS_RULE  # safety phrase
    assert "being kept from leaving, their saying they don't" in DISTRESS_RULE  # safety phrase
    assert "or talk of suicide or self-harm" in DISTRESS_RULE  # safety phrase
    assert "Talk of suicide or self-harm is never dropped" in DISTRESS_RULE  # safety phrase
    assert "988" in DISTRESS_RULE
    # Dropping a topic when asked never drops someone's safety, and a crisis line or a safety
    # step is never "said already", whether the chat or its summary said it.
    assert "unless someone's safety depends on it" in NO_RECAP_NOTE  # safety phrase
    assert (
        "A crisis line or a safety step is given again whenever" in NO_RECAP_NOTE
    )  # safety phrase
    assert "unless it is a crisis line or a safety step" in SUMMARY_LEAD  # safety phrase


def test_the_summary_keeps_the_users_facts_not_the_assistants_warnings() -> None:
    # Every fold wrote "Assistant advises getting a lawyer" again, and the summary sits above
    # every later turn: its Facts and its Topics both leave the assistant's warnings out.
    assert SUMMARY_SYSTEM_PROMPT.count(ASSISTANT_CONCERNS_RULE) == 2


def test_a_day_the_chat_named_is_not_dated_again_unless_asked() -> None:
    # "tomorrow, Friday, November 20, 2026" in 50 of 80 replies; asked for the date, still whole.
    assert KNOWN_DAY_RULE in format_now_awareness("Africa/Nairobi", "en")
    assert KNOWN_DAY_RULE.endswith("unless they ask for it.")


def test_lots_of_emoji_still_fit_their_line() -> None:
    # A 💛 opened 58 of 80 replies at "Lots", whatever the line said.
    assert EMOJI_FITS in EMOJI_HINTS["more"]
    note = emoji_note("more", "")
    assert note is not None and EMOJI_FITS in note
    # "A few" already allows none in a sentence; its line is unchanged.
    assert EMOJI_FITS not in EMOJI_HINTS["some"]
