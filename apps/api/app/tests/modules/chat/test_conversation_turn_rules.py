"""A conversation about the user's own life, answered as one (an 80-message chat, 2026-11-19).

"Friend getting married" went from a girlfriend's wedding to her mother, money and sex.
The replies offered help in 36 of 80, read news as a yes to their own offer, raised the bank
and the $500,000 in nearly every reply, ended on 💛 at "Lots", refused things never asked,
and told the user to call 911 twelve times while he said it felt good. The model judges what
a turn is; these rules say what it does then, and each sits where the model reads it.
"""

from __future__ import annotations

from app.modules.chat.context_window import ASSISTANT_CONCERNS_RULE, SUMMARY_SYSTEM_PROMPT
from app.modules.chat.prompt_constants.care import DISTRESS_RULE, PERSONAL_HELP_RULE
from app.modules.chat.prompt_constants.conversation import (
    NO_RECAP_NOTE,
    OWN_MISTAKE_HINT,
    SUMMARY_LEAD,
)
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
    # Main replayed (2026-11-19) gave 988 in 54 of 80 replies, with no word of self-harm.
    assert "to call 911 or to call a crisis line is for a stated threat" in DISTRESS_RULE
    assert "or talk of suicide or self-harm" in DISTRESS_RULE
    assert "once they have answered that they're okay, do not ask again" in DISTRESS_RULE
    # The replay (2026-11-19): after "Are you safe right now?", "She is asking me to get on
    # bad" and "No it feels good" got "call 911 if the threats get worse" nine times, and
    # "the threats you mentioned", which he never had.
    # "Is the friend or family member you mentioned with you right now?" eleven turns running.
    assert "Asked once, it is asked, in any words" in DISTRESS_RULE
    assert "enjoying it or carrying on is their answer" in DISTRESS_RULE
    assert 'or a crisis line, not even as an "if", until they state one of the' in DISTRESS_RULE
    assert "Never say they mentioned a threat, a danger or a fear they did not" in DISTRESS_RULE
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


def test_advice_once_said_is_not_tied_to_each_new_detail() -> None:
    # The replay of the 80 messages (2026-11-19): "a lawyer" in 46 replies, each tied to the
    # new detail ("it makes the lawyer step even more important"), and "Did you book a lawyer
    # yet?" five turns running.
    assert "Once one of your earlier replies has said it, it is said" in NO_RECAP_NOTE
    assert "not the same advice tied to it" in NO_RECAP_NOTE
    assert "never a question about whether they followed it" in NO_RECAP_NOTE


def test_news_about_their_life_is_not_checked_like_a_sum() -> None:
    # "When they add a fact (a date, an amount) … say plainly what it changes" made every
    # gift and transfer "That makes this more serious, not less".
    assert "to something this chat worked out (a plan, a budget, a sum)" in OWN_MISTAKE_HINT
    assert "news about their own life is answered as news" in OWN_MISTAKE_HINT


def test_the_summary_keeps_the_users_facts_not_the_assistants_warnings() -> None:
    # Every fold wrote "Assistant advises getting a lawyer" again, and the summary sits above
    # every later turn.
    assert ASSISTANT_CONCERNS_RULE in SUMMARY_SYSTEM_PROMPT
    assert SUMMARY_SYSTEM_PROMPT.count(ASSISTANT_CONCERNS_RULE) == 2
    assert "never written again because a new message repeats it" in SUMMARY_SYSTEM_PROMPT
    assert "do not give it again" in SUMMARY_LEAD
    # Never at the cost of the crisis line: self-harm talk gets 988 again (review).
    assert "unless it is a crisis line or a safety step" in SUMMARY_LEAD
    assert "A crisis line or a safety step is given again whenever suicide" in NO_RECAP_NOTE
    # A pick the assistant gave (a laptop, a savings amount) is still a fact to keep.
    assert "never the assistant's own warnings, cautions, concerns or reminders" in (
        SUMMARY_SYSTEM_PROMPT
    )
