""" "Bo" is not "hi": an unclear word gets noticed, not greeted past.

"Bo" got "Hey Bini! How's it going?". ChatGPT answered "Bo! Did you mean 'bo' in
Amharic, or are you starting to type something?"
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import User
from app.modules.chat.prompt_builder import build_prompt_messages
from app.modules.chat.prompt_constants.unclear import (
    UNCLEAR_SHORT_TURN_HINT,
    is_unclear_short_turn,
)


@pytest.mark.parametrize(
    "text, unclear",
    [
        ("Bo", True),
        ("bo?", True),
        ("photosynthesis", True),  # the hint says a clear word is answered as usual
        ("hi", False),
        ("ok", False),
        ("yes", False),
        ("thanks", False),
        ("solve 2x=4", False),
        ("x^2", False),
        ("what is love", False),
        ("https://example.com", False),
        ("tell me about dogs", False),
        ("", False),
    ],
)
def test_is_unclear_short_turn_reads_a_lone_word(text: str, unclear: bool) -> None:
    assert is_unclear_short_turn(text) is unclear


def test_is_unclear_short_turn_leaves_an_answer_to_a_question() -> None:
    asked = [SimpleNamespace(role="assistant", content="Where should we go next?")]
    assert not is_unclear_short_turn("Paris", asked)


def test_unclear_short_turn_hint_guesses_instead_of_greeting() -> None:
    assert "do not treat it as a greeting" in UNCLEAR_SHORT_TURN_HINT
    assert "a language they may speak" in UNCLEAR_SHORT_TURN_HINT
    assert "still typing" in UNCLEAR_SHORT_TURN_HINT
    assert "answer it as usual" in UNCLEAR_SHORT_TURN_HINT


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


async def _system_prompt(query: str) -> str:
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
            current_user_message_id=current.id,
        )
    return messages[0]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("query, expected", [("Bo", True), ("hi", False), ("solve 2x=4", False)])
async def test_system_prompt_carries_the_hint_only_for_an_unclear_word(
    query: str, expected: bool
) -> None:
    assert (UNCLEAR_SHORT_TURN_HINT in await _system_prompt(query)) is expected
