"""Facts said in passing, two to a line: each saved, each on its own row (live QA, 2026-11-22).

"hey so i drive a 2015 honda civic and im vegetarian" saved only the car: "User is
vegetarian" read as a name the user never claimed ("im" has no apostrophe). The model also
wrote two facts as one ("User is a nurse and has a 7-year-old son"), or both ways at once.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.memory import extract_backlog
from app.modules.memory.grounding import joins_quotes
from app.modules.memory.name_claim import assigned_user_names, is_unclaimed_user_name
from app.modules.memory.pass_writes import Asks, MemorySnapshot, compose_writes
from app.modules.memory.schemas import MemoryFactOp


def _op(text: str, quote: str, **extra: object) -> MemoryFactOp:
    fields: dict[str, object] = {
        "op": "add",
        "type": "fact",
        "topic": "notes",
        "text": text,
        "quote": quote,
        "stated_as": "own_life",
        "confidence": 1.0,
        "importance": 0.5,
    }
    return MemoryFactOp.model_validate(fields | extra)


def _saved(line: str, ops: list[MemoryFactOp]) -> list[str]:
    lines = extract_backlog.format_user_memory_transcript([line])
    snapshot = MemorySnapshot(
        memory_enabled=True,
        include_sensitive=True,
        existing_facts={},
        prompt_facts=[],
        prompt_areas=[],
    )
    writes, _ = compose_writes(
        snapshot,
        lines,
        Asks.of(lines),
        ops,
        chat_id=uuid4(),
        from_history=False,
        min_confidence=0.4,
        sources=extract_backlog.source_lines([(uuid4(), line)]),
    )
    return [write.text for write in writes if write.op == "add"]


@pytest.mark.parametrize(
    "fact",
    ["User is vegetarian.", "User is retired", "The user is pregnant", "User is left-handed"],
)
def test_what_the_user_is_is_not_a_name(fact):
    assert assigned_user_names(fact) == []
    assert is_unclaimed_user_name(fact, "User: hey so im vegetarian") is False


@pytest.mark.parametrize("fact", ["User is Bebe", "The user is Bebe.", "User is ሳራ"])
def test_a_capitalised_or_uncased_word_is_still_a_name(fact):
    assert assigned_user_names(fact)


def test_a_name_typed_without_the_apostrophe_is_claimed():
    assert is_unclaimed_user_name("User is Sam", "User: im Sam btw") is False
    assert is_unclaimed_user_name("User is Sam", "User: Sam has 2 pens") is True


def test_both_facts_of_a_casual_line_are_saved():
    line = "hey so i drive a 2015 honda civic and im vegetarian"
    saved = _saved(
        line,
        [
            _op("User drives a 2015 Honda Civic", "i drive a 2015 honda civic"),
            _op("User is vegetarian", "im vegetarian", type="preference", topic="profile"),
        ],
    )
    assert saved == ["User drives a 2015 Honda Civic", "User is vegetarian"]


def test_a_fact_joined_from_two_others_is_dropped():
    line = "hey so im vegetarian and my dog is called Biscuit lol"
    saved = _saved(
        line,
        [
            _op("User is vegetarian", "im vegetarian"),
            _op("User has a dog named Biscuit", "my dog is called Biscuit"),
            _op(
                "User is vegetarian and has a dog named Biscuit",
                "im vegetarian and my dog is called Biscuit lol",
            ),
        ],
    )
    assert saved == ["User is vegetarian", "User has a dog named Biscuit"]


def test_a_quote_with_a_third_claim_joins_nothing():
    quotes = ["i work as a nurse", "my son is 7"]
    assert joins_quotes("hey so i work as a nurse and my son is 7", quotes)
    assert not joins_quotes("i work as a nurse, my son is 7 and i live in Denver", quotes)
    assert not joins_quotes("i work as a nurse", quotes)
    assert not joins_quotes(None, quotes)


async def test_the_extraction_prompt_asks_for_one_fact_an_op(monkeypatch):
    from app.core.config import Settings
    from app.modules.memory import llm as memory_llm

    captured: dict[str, object] = {}

    async def _capture(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(memory_llm.litellm_gateway, "complete_structured", _capture)
    await memory_llm.revise_memory_facts(
        Settings(mock_llm_enabled=False), "User: i work as a nurse and my son is 7"
    )
    system = captured["messages"][0]["content"]  # type: ignore[index]
    assert memory_llm.ONE_FACT_RULE in system
