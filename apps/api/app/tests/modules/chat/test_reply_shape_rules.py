"""Everyday reply shape: examples, endings, headings and short social turns."""

from __future__ import annotations

from app.modules.chat.prompt_constants.format import FORMAT_CONTRACT, TONE_FORMAT_GUARD
from app.modules.chat.prompt_constants.routing import LIGHTWEIGHT_REPLY_HINT


def test_an_example_is_a_sentence_not_a_quote_or_a_fence() -> None:
    assert "*For example,*" in FORMAT_CONTRACT
    assert "Never a `>`, a callout, or a code fence for an example" in FORMAT_CONTRACT


def test_a_reply_ends_with_at_most_one_plain_short_line() -> None:
    assert "Ending: at most one short plain line" in FORMAT_CONTRACT
    assert "never bold" in FORMAT_CONTRACT
    assert "Let me know if you have any other questions" in FORMAT_CONTRACT


def test_headings_rule_does_not_contradict_the_short_how_to() -> None:
    # The contract says a short how-to is one numbered list; the tone guard
    # used to tell every how-to to lead with ## headings.
    assert "Short how-to: one numbered list" in FORMAT_CONTRACT
    assert "a short how-to is one numbered list" in TONE_FORMAT_GUARD
    assert "learning plan / how-to leads with ## headings" not in TONE_FORMAT_GUARD


def test_a_greeting_gets_no_emoji_or_offer_unless_the_user_used_one() -> None:
    assert "No emoji unless the user used one" in LIGHTWEIGHT_REPLY_HINT
    assert "no closing offer" in LIGHTWEIGHT_REPLY_HINT
