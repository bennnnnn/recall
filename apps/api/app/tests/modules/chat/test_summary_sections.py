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
    # Facts are carried too (2026-11-07): the earlier ones in their order, "User is Bini." once.
    assert sections(text)["Facts"] == ["User is Bini. Trip in December. Savings plan dropped."]


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


def test_a_chat_with_more_topics_than_the_cap_holds_keeps_the_newest_and_open() -> None:
    # Review of #2305: lines shortened to 90 characters still overran the cap, and the cut
    # after it took the newest topics and the Open line.
    old = "Facts: f\nTopics:\n" + "\n".join(f"Topic {n}. " + "word " * 40 for n in range(200))
    fresh = "Facts: " + "fact " * 2000 + "\nTopics: Newest. Outcome: done.\nOpen: Pick a date."
    text = merged(old, fresh, 6000)
    read = sections(text)
    assert len(text) <= 6000
    assert read["Topics"][-1] == "Newest. Outcome: done."
    assert read["Open"] == ["Pick a date."]
    # The oldest are cut to a subject before any goes. Facts may fill half the cap first
    # (2026-11-07), so a summary whose facts overflow keeps about 70 subjects, not 100.
    assert len(read["Topics"]) > 60


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


_LAPTOP = (
    "Facts: User has a 2017 Dell Inspiron with Windows 10, an HDD and 8 GB of RAM. User drives "
    "a 2011 Honda Civic. User's take-home pay is $3,200 a month and rent is $1,100. User's rent "
    "is $1,100.\n\nTopics:\nSlow laptop. Outcome: SSD.\n\nOpen: None"
)


def test_a_fold_keeps_the_earlier_facts_whatever_the_model_writes() -> None:
    # Live, 2026-11-07: 70 turns on, "what laptop do I have" got "I don't have any record".
    fresh = "Facts: User asked for a reminder to call the Honda shop.\nTopics: Brakes.\nOpen: None"
    facts = sections(merged(_LAPTOP, fresh, 6000))["Facts"][0]
    assert "2017 Dell Inspiron" in facts
    assert "2011 Honda Civic" in facts
    assert facts.endswith("User asked for a reminder to call the Honda shop.")


def test_a_changed_fact_is_kept_after_the_old_one() -> None:
    # SUMMARY_LEAD tells the reader the later one holds; code never guesses a restatement.
    fresh = "Facts: User's rent is $1,250 now.\nTopics: Rent.\nOpen: None"
    facts = sections(merged(_LAPTOP, fresh, 6000))["Facts"][0]
    assert facts.index("rent is $1,100") < facts.index("User's rent is $1,250 now.")
    assert "take-home pay is $3,200" in facts


@pytest.mark.parametrize(
    ("earlier", "later"),
    [
        # Review, 2026-11-07: a word-overlap test dropped each first fact.
        ("User earns $3,200 a month.", "User's wife earns $2,800 a month."),
        ("User's son is 7 years old.", "User's daughter is 4 years old."),
        ("Assistant taught the idiom 'touch base'.", "Assistant taught the idiom 'bandwidth'."),
        ("User is Bini.", "Bini's sister is Hana."),
    ],
)
def test_two_facts_that_share_words_are_both_kept(earlier: str, later: str) -> None:
    prior = f"Facts: {earlier}\n\nTopics:\nA.\n\nOpen: None"
    facts = sections(merged(prior, f"Facts: {later}\nTopics: B.\nOpen: None", 6000))["Facts"][0]
    assert earlier in facts and later in facts


def test_a_fact_written_again_is_kept_once() -> None:
    prior = "Facts: User drives a 2011 Honda Civic.\n\nTopics:\nA.\n\nOpen: None"
    fresh = "Facts: User drives a 2011 Honda Civic\nTopics: B.\nOpen: None"
    assert sections(merged(prior, fresh, 6000))["Facts"][0].count("Honda Civic") == 1


def test_over_their_share_narrations_go_before_short_facts() -> None:
    # The longest earlier fact goes first: a narration before a short durable fact.
    narration = (
        "User asked about renting versus buying in Columbus and got a long comparison of "
        "prices, rates and the break-even point."
    )
    old = f"Facts: User drives a 2011 Honda Civic. {narration}\n\nTopics:\nA.\n\nOpen: None"
    fresh = "Facts: User's rent is $1,100.\nTopics: B.\nOpen: None"
    facts = sections(merged(old, fresh, 2 * 70))["Facts"][0]
    assert "2011 Honda Civic" in facts and "rent is $1,100" in facts
    assert "renting versus buying" not in facts


def test_a_new_fact_is_never_dropped_the_fold_it_arrives() -> None:
    # Review, 2026-11-07: with a full share of short facts, longest-first eviction dropped a
    # longer new fact at once and left the stale rent as the only figure.
    short = " ".join(f"User said thanks {n}." for n in range(150))
    old = f"Facts: User's rent is $1,100. {short}\n\nTopics:\nA.\n\nOpen: None"
    fresh = (
        "Facts: User's rent went up to $1,250 a month starting in October.\nTopics: B.\nOpen: None"
    )
    facts = sections(merged(old, fresh, 6000))["Facts"][0]
    assert facts.endswith("User's rent went up to $1,250 a month starting in October.")
    assert "rent is $1,100" not in facts  # the longest earlier fact went instead


def test_facts_split_in_other_scripts_and_keep_titles_whole() -> None:
    from app.modules.chat.summary_sections import _fact_sentences

    line = "User's doctor is Dr. Smith. Аренда 40 000. Аренда теперь 45 000. ቤት አለኝ። መኪና አለኝ።"
    assert _fact_sentences([line]) == [
        "User's doctor is Dr. Smith.",
        "Аренда 40 000.",
        "Аренда теперь 45 000.",
        "ቤት አለኝ።",
        "መኪና አለኝ።",
    ]
