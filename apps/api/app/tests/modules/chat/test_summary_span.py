"""What the chat's summary stands for, and what it records as shown.

A 53-turn Grade 8 chat (2026-11-18): "What was the first question I asked you?" named the
oldest message the reply could see, the 76th of 97, though the summary's first topic was the
first question; and the summary recorded "graphs provided" and "diagram drawn" where the
replies only said so.
"""

from __future__ import annotations

from app.modules.chat.compaction import summary_text
from app.modules.chat.context_window import SUMMARY_SYSTEM_PROMPT
from app.modules.chat.prompt_constants.conversation import SUMMARY_LEAD, summary_lead


def test_the_summary_says_it_stands_for_the_start_of_the_chat() -> None:
    lead = summary_lead(75)
    assert lead.startswith(SUMMARY_LEAD)
    assert "the first 75 messages of this chat" in lead
    assert "never in the first message you can see" in lead
    # Not known: the lead as it was.
    assert summary_lead(0) == SUMMARY_LEAD


def test_a_picture_is_shown_only_where_its_fence_was_saved() -> None:
    drawn = 'Here is the graph:\n\n```graph\n{"curves": []}\n```\n\nThe speed rises.'
    assert summary_text(drawn) == "Here is the graph:\n\n[shown: a graph]\nThe speed rises."
    # Said but not drawn: nothing marks it.
    said = "Here is the graph of speed against time. The speed rises."
    assert summary_text(said) == said
    assert "[shown: …]" in SUMMARY_SYSTEM_PROMPT


def test_the_prompts_own_fences_still_leave_the_summary() -> None:
    reply = "Done.\n\n```sources\n[1] example.com\n```"
    assert "example.com" not in summary_text(reply)
