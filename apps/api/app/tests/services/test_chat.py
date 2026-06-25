from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.services.chat import build_prompt_messages, estimate_tokens


def test_estimate_tokens_minimum():
    assert estimate_tokens("") == 1
    assert estimate_tokens("hello") == 1


@pytest.mark.asyncio
async def test_build_prompt_includes_memory_and_style():
    user = AsyncMock()
    user.response_style = "short"
    user.memory_enabled = True

    session = AsyncMock()

    with (
        patch(
            "app.services.chat.memory_service.load_relevant_memories",
            AsyncMock(return_value=[AsyncMock(type="preference", text="likes Python")]),
        ),
        patch(
            "app.services.chat.messages_repo.list_recent",
            return_value=[AsyncMock(role="user", content="Hi")],
        ),
        patch(
            "app.services.chat.memory_service.format_memory_block",
            return_value="Known facts:\n- [preference] likes Python",
        ),
    ):
        messages = await build_prompt_messages(session, user, AsyncMock(), Settings())

    assert messages[0]["role"] == "system"
    assert "short" in messages[0]["content"].lower() or "concise" in messages[0]["content"].lower()
    assert "Python" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "Hi"}


@pytest.mark.asyncio
async def test_stream_does_not_duplicate_user_message():
    """User message is saved once; prompt must not append it again."""
    from app.services import chat as chat_module

    tokens = ["Hello", " there"]

    async def fake_stream(**kwargs):
        for t in tokens:
            yield t

    user = AsyncMock()
    user.id = "user-1"
    user.default_model = "free-chat"
    user.response_style = "balanced"

    chat = AsyncMock()
    chat.model = "free-chat"

    session = AsyncMock()
    redis = AsyncMock()

    mock_build = AsyncMock(
        return_value=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "question"},
        ]
    )

    with (
        patch("app.services.chat.quota_service.can_spend", AsyncMock(return_value=True)),
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=chat)),
        patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=1)),
        patch("app.services.chat.messages_repo.create", AsyncMock()),
        patch("app.services.chat.build_prompt_messages", mock_build),
        patch("app.services.chat.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.chat.quota_service.record_usage", AsyncMock()),
        patch("app.services.chat.usage_repo.add_tokens", AsyncMock()),
    ):
        collected = []
        async for tok in chat_module.stream_chat_response(
            session,
            redis,
            AsyncMock(max_output_tokens=100),
            user=user,
            chat_id=AsyncMock(),
            content="question",
        ):
            collected.append(tok)

    assert collected == tokens
    assert mock_build.await_count == 1
