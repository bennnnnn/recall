"""A conversation about the user's own life, answered as one (an 80-message chat, 2026-11-19).

"Friend getting married" went from a girlfriend's wedding to her mother, money and sex.
The replies offered help in 36 of 80, read news as a yes to their own offer, raised the bank
and the $500,000 in nearly every reply, ended on 💛 at "Lots", refused things never asked,
and told the user to call 911 twelve times while he said it felt good. The model judges what
a turn is; these rules say what it does then, and each sits where the model reads it.
"""

from __future__ import annotations

from app.modules.chat.prompt_constants.care import DISTRESS_RULE, PERSONAL_HELP_RULE
from app.modules.chat.prompt_constants.conversation import NO_RECAP_NOTE
from app.modules.chat.prompt_constants.unclear import UNCLEAR_MESSAGE_HINT
from app.modules.chat.response_tone import EMOJI_HINTS, emoji_note


def test_news_is_not_a_yes_to_an_offer() -> None:
    # "She bought me a house …" after "Would it help to plan what to ask your bank?" got
    # "Yes, let's work out what to ask the bank".
    assert "A message that answers a question you asked is its answer" in UNCLEAR_MESSAGE_HINT
    assert "is not a yes to your offer" in UNCLEAR_MESSAGE_HINT
    assert "never take up your own offer for them" in UNCLEAR_MESSAGE_HINT
    assert "A message after a question you asked is its answer" not in UNCLEAR_MESSAGE_HINT


def test_a_concern_is_said_once_and_a_topic_dropped_when_asked() -> None:
    assert "Say a concern, a warning or a piece of advice once" in NO_RECAP_NOTE
    assert "do not raise it again unless something new changes it" in NO_RECAP_NOTE
    # "Can u forget about the wedding!" got "I can't just forget about it".
    assert "When they ask you to drop a topic, drop it" in NO_RECAP_NOTE
    # Never at the cost of someone's safety: talk of self-harm is never dropped.
    assert "unless someone's safety depends on it" in NO_RECAP_NOTE


def test_a_hard_situation_gets_one_safety_check_and_911_only_for_a_threat() -> None:
    assert "is not an emergency by itself" in DISTRESS_RULE
    assert "ask once whether they're okay and feel safe" in DISTRESS_RULE
    assert "Telling them to leave or to call 911 is for a stated threat" in DISTRESS_RULE
    assert "once they have answered that they're okay, do not ask again" in DISTRESS_RULE
    # Self-harm keeps its own rule: never dropped, the crisis line given again.
    assert "Talk of suicide or self-harm is never dropped" in DISTRESS_RULE
    assert "988" in DISTRESS_RULE


def test_a_choice_of_theirs_gets_one_view_and_no_refusal_of_what_was_not_asked() -> None:
    assert "gets your honest view once, then your help with what they chose" in PERSONAL_HELP_RULE
    assert "say in a few words that you'll skip that part" in PERSONAL_HELP_RULE
    assert "Never refuse or decline something they did not ask for" in PERSONAL_HELP_RULE
    # The rule this joins still holds: real personal help, never a refusal.
    assert "never a refusal or a turn to something else" in PERSONAL_HELP_RULE


def test_lots_of_emoji_still_fit_their_line() -> None:
    # A 💛 opened 58 of 80 replies at "Lots", whatever the line said.
    rule = "never the same one reply after reply as a sign-off"
    assert rule in EMOJI_HINTS["more"]
    note = emoji_note("more", "")
    assert note is not None and rule in note
    # "A few" already allows none in a sentence; its line is unchanged.
    assert rule not in EMOJI_HINTS["some"]
