"""Every topic the running summary ever held stays in it: code keeps them, not the model.

Live 2026-11-06: four turns on a Zanzibar trip were gone from the summary ten turns later,
and "u forgot the zanzibar stuff" got "I don't have anything about Zanzibar from our chats".
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.modules.chat.summary_sections import merged, sections

_FIRST = (
    "Facts: User is Bini. Trip in December.\n\nTopics: Zanzibar trip. Outcome: December is dry "
    "season; budget about $600-900 with flights.\nDinner. Outcome: chicken, rice and spinach.\n\n"
    "Open: None"
)


def test_a_summary_reads_as_its_sections() -> None:
    read = sections(_FIRST)
    assert read["Facts"] == ["User is Bini. Trip in December."]
    assert read["Topics"][0].startswith("Zanzibar trip.")
    assert read["Open"] == ["None"]


def test_a_fold_keeps_the_earlier_topics_whatever_the_model_writes() -> None:
    fresh = (
        "Facts: User is Bini. Savings plan dropped.\nTopics: Roman Empire. Outcome: fell in 476 CE."
        "\nOpen: None"
    )
    text = merged(_FIRST, fresh, 6000)
    topics = sections(text)["Topics"]
    assert [line.split(".")[0] for line in topics] == ["Zanzibar trip", "Dinner", "Roman Empire"]
    assert sections(text)["Facts"] == ["User is Bini. Savings plan dropped."]


def test_a_topic_said_again_is_kept_once() -> None:
    fresh = "Facts: x\nTopics: Dinner. Outcome: chicken, rice and spinach.\nOpen: None"
    assert (
        sections(merged(_FIRST, fresh, 6000))["Topics"].count(
            "Dinner. Outcome: chicken, rice and spinach."
        )
        == 1
    )


def test_over_the_cap_the_oldest_lines_are_shortened_never_dropped() -> None:
    old = "Facts: f\nTopics:\n" + "\n".join(f"Topic {n}. " + "word " * 40 for n in range(10))
    text = merged(old, "Facts: f\nTopics: Newest. Outcome: done.\nOpen: None", 1500)
    topics = sections(text)["Topics"]
    assert len(topics) == 11
    assert topics[0].endswith("…") and topics[-1] == "Newest. Outcome: done."


@pytest.mark.asyncio
async def test_a_topic_outlives_many_folds() -> None:
    from app.modules.chat.summarize import summarize_conversation

    async def fake_complete(**kwargs):
        # A model that only ever writes the newest topic, as it is told to.
        newest = kwargs["messages"][1]["content"].rsplit("user: ", 1)[-1]
        return f"Facts: User is Bini.\nTopics: {newest}. Outcome: answered.\nOpen: None"

    settings = Settings(mock_llm_enabled=False, openrouter_api_key="test-key")
    summary = None
    with patch.object(litellm_gateway, "complete_text", fake_complete):
        for topic in ("Zanzibar trip", "Dinner", "Savings", "Roman Empire", "Jokes", "Books"):
            summary = await summarize_conversation(
                settings, summary, [{"role": "user", "content": topic}]
            )
    assert summary is not None
    assert [line.split(".")[0] for line in sections(summary)["Topics"]] == [
        "Zanzibar trip", "Dinner", "Savings", "Roman Empire", "Jokes", "Books",
    ]  # fmt: skip
