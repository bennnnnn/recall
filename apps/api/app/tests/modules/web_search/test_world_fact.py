"""A question about the world reaches the search classifier; chat, maths and writing do not.

Before, only a live word (current, latest, price…) did: "what's the population of
Ethiopia", "who won the champions league", "best restaurants in Addis" and a claim
about Abiy Ahmed were answered from memory.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import User
from app.models.schemas import WebSearchClassification
from app.modules.chat.prompt_builder import build_prompt_messages
from app.modules.chat.prompt_constants import FACT_GROUNDING_HINT
from app.modules.web_search import should_web_search
from app.modules.web_search.world_fact import asks_about_the_world

_ASKS = [
    "what's the population of Ethiopia",
    "who won the champions league",
    "best restaurants in Addis",
    "is Abiy Ahmed responsible for the Tigray war",
    "how old is Elon Musk",
    "what is the tallest building in Africa",
    "how many people live in Nairobi",
    "can you tell me the minimum wage in Kenya",
    "But Ahmed is a genocider. He caused all the war",
]
_DOES_NOT_ASK = [
    "what is photosynthesis",
    "what's a prime minister",
    "write a poem about rain",
    "explain recursion",
    "solve 2x+5=17",
    "how do I make tea",
    "why is the sky blue",
    "what causes weather",
    "what are the benefits of drinking water",
    "what time is it in Tokyo",
    "how many minutes in a good nap",
    "where is kenya",
    "what can you do",
    "hey! how are you?",
    "what is my dog's name?",
    "I'm new to python, where should I start?",
    "give me 5 tips to sleep better",
    "translate good morning to french",
    "hi",
]


@pytest.mark.parametrize("text", _ASKS)
def test_asks_about_the_world(text: str) -> None:
    assert asks_about_the_world(text)


@pytest.mark.parametrize("text", _DOES_NOT_ASK)
def test_not_a_question_about_the_world(text: str) -> None:
    assert not asks_about_the_world(text)


@pytest.mark.asyncio
async def test_a_world_question_with_no_live_word_reaches_the_classifier() -> None:
    settings = Settings(web_search_enabled=True, web_search_classifier_enabled=True)
    verdict = WebSearchClassification(needs_search=True, query="Ethiopia population")
    with patch(
        "app.modules.web_search.detection.classify_web_search", AsyncMock(return_value=verdict)
    ) as classify:
        assert await should_web_search("what's the population of Ethiopia", settings) is True
    classify.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text", ["what is photosynthesis", "how do I make tea", "explain recursion"]
)
async def test_no_classifier_round_for_a_turn_with_nothing_to_look_up(text: str) -> None:
    settings = Settings(web_search_enabled=True, web_search_classifier_enabled=True)
    with patch("app.modules.web_search.detection.classify_web_search", AsyncMock()) as classify:
        assert await should_web_search(text, settings) is False
    classify.assert_not_awaited()


@pytest.mark.asyncio
async def test_classifier_rubric_leans_to_searching_named_facts() -> None:
    from app.modules.web_search import classify as classify_module

    complete = AsyncMock(return_value=WebSearchClassification(needs_search=True))
    with (
        patch.object(classify_module.litellm_gateway, "complete_structured", complete),
        patch.object(
            classify_module.quota_service, "global_spend_exceeded", AsyncMock(return_value=False)
        ),
        patch.object(classify_module.quota_service, "record_global_spend", AsyncMock()),
        patch.object(classify_module, "get_redis_client", MagicMock()),
    ):
        await classify_module.classify_web_search_need(
            Settings(), "what's the population of Ethiopia"
        )
    assert complete.await_args is not None
    rubric = complete.await_args.kwargs["messages"][0]["content"]
    assert "When unsure about a specific named real-world fact, choose true." in rubric
    assert "prefer false" not in rubric
    assert "asserts something about a real public figure" in rubric


def _user() -> User:
    user = MagicMock()
    user.id = uuid4()
    user.name = "Bini"
    user.email = "bini@example.com"
    user.location = None
    user.response_style = "balanced"
    user.response_tone = None
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = None
    user.custom_instructions = None
    return cast(User, user)


async def _system_prompt(query: str, *, lightweight: bool) -> str:
    current = SimpleNamespace(id=uuid4(), role="user", content=query)
    with (
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=None)),
        patch("app.modules.memory.get_memory_block", AsyncMock(return_value="")),
        patch("app.modules.todos.build_todos_system_section", AsyncMock(return_value="")),
        patch("app.repositories.messages.list_recent", AsyncMock(return_value=[current])),
    ):
        messages = await build_prompt_messages(
            _user(),
            uuid4(),
            Settings(attachment_rag_enabled=False, chat_history_rag_enabled=False),
            query_text=query,
            rich_context=False,
            lightweight=lightweight,
            current_user_message_id=current.id,
        )
    return messages[0]["content"]


@pytest.mark.asyncio
async def test_every_answer_turn_is_told_not_to_guess_a_changing_fact() -> None:
    assert FACT_GROUNDING_HINT in await _system_prompt("who is the president", lightweight=False)
    assert "offer to look it up" in FACT_GROUNDING_HINT
    assert "even-handedly" in FACT_GROUNDING_HINT


@pytest.mark.asyncio
async def test_a_greeting_carries_no_fact_rule() -> None:
    assert FACT_GROUNDING_HINT not in await _system_prompt("hi", lightweight=True)
