"""Everyday reply shape: examples, endings, headings and short social turns."""

from __future__ import annotations

from app.modules.chat.prompt_constants.format import (
    FORMAT_CONTRACT,
    READER_NOTE,
    TONE_FORMAT_GUARD,
)
from app.modules.chat.prompt_constants.routing import LIGHTWEIGHT_REPLY_HINT


def test_an_example_is_a_sentence_not_a_quote_or_a_fence() -> None:
    assert "*For example,*" in FORMAT_CONTRACT
    assert "Never a `>`, a callout, or a code fence for an example" in FORMAT_CONTRACT


def test_a_reply_ends_on_its_point_and_offers_only_a_concrete_next_step() -> None:
    # An 80-message chat ended 65 replies on a question or an offer (2026-11-19).
    assert "Ending: end on your last point" in FORMAT_CONTRACT
    assert "A closing question only when you need their answer" in FORMAT_CONTRACT
    assert "never the same offer again after they let it go" in FORMAT_CONTRACT
    assert "A reply about their own life or feelings ends without an offer" in FORMAT_CONTRACT
    assert "never bold" in FORMAT_CONTRACT
    assert "Let me know if you have any other questions" in FORMAT_CONTRACT
    assert "a question or an offer of one concrete next step" not in FORMAT_CONTRACT


def test_a_message_about_their_own_life_is_answered_as_a_conversation() -> None:
    # "I love the mom" got three numbered steps and a bold verdict (2026-11-19).
    assert "is a conversation, not a question to scan" in READER_NOTE
    assert "no list, heading or bold" in READER_NOTE


def test_headings_rule_does_not_contradict_the_short_how_to() -> None:
    # The contract says a short how-to is one numbered list; the tone guard
    # used to tell every how-to to lead with ## headings.
    assert "Short how-to: one numbered list" in FORMAT_CONTRACT
    assert "a short how-to is one numbered list" in TONE_FORMAT_GUARD
    assert "learning plan / how-to leads with ## headings" not in TONE_FORMAT_GUARD


def test_a_greeting_gets_no_closing_offer() -> None:
    assert "no closing offer" in LIGHTWEIGHT_REPLY_HINT


def test_an_answer_that_rests_on_an_unstated_detail_names_its_assumption() -> None:
    assert "state the assumption in one short clause and answer" in FORMAT_CONTRACT
    assert "(budget, platform, version)" in FORMAT_CONTRACT
    assert "no stacked disclaimers" in FORMAT_CONTRACT


def test_no_hint_asks_for_a_generic_offer_line() -> None:
    from app.modules.chat.prompt_constants import FACT_GROUNDING_HINT
    from app.modules.chat.prompt_constants.writing import EMAIL_DRAFT_HINT

    # A draft ends at its fence; a line after it only names a gap or an assumption.
    assert "offering to adjust tone or length" not in EMAIL_DRAFT_HINT
    assert "No offer to adjust tone or length" in EMAIL_DRAFT_HINT
    # The "may be out of date" line is for facts that change, never for settled ones.
    assert "a settled one (a capital, a formula, history) gets no disclaimer" in (
        FACT_GROUNDING_HINT
    )
