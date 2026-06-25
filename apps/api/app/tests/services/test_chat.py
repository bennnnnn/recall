from unittest.mock import AsyncMock, MagicMock, patch

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
    from app.services import chat as chat_module

    tokens = ["Hello", " there"]

    async def fake_stream(**kwargs):
        for t in tokens:
            yield t

    user_id = AsyncMock()
    chat_id = AsyncMock()

    mock_build = AsyncMock(
        return_value=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "question"},
        ]
    )

    fake_user = MagicMock()
    fake_user.id = user_id
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"

    with (
        patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True)),
        patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=1)),
        patch("app.services.chat.messages_repo.create", AsyncMock()),
        patch("app.services.chat.build_prompt_messages", mock_build),
        patch("app.services.chat.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.chat.quota_service.adjust_usage", AsyncMock()),
        patch("app.services.chat.usage_repo.add_tokens", AsyncMock()),
        patch("app.services.chat.jobs.enqueue", AsyncMock()),
    ):
        collected = []
        async for tok in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100),
            user_id=user_id,
            chat_id=chat_id,
            content="question",
        ):
            collected.append(tok)

    assert collected == tokens
    assert mock_build.await_count == 1


@pytest.mark.asyncio
async def test_memory_extraction_runs_on_later_turn():
    from app.services import chat as chat_module

    async def fake_stream(**kwargs):
        yield "answer"

    fake_user = MagicMock()
    fake_user.id = MagicMock()
    fake_user.default_model = "free-chat"
    fake_user.response_style = "balanced"

    fake_chat = MagicMock()
    fake_chat.model = "free-chat"

    with (
        patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=True)),
        patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.services.chat.chats_repo.get_by_id", AsyncMock(return_value=fake_chat)),
        patch("app.services.chat.messages_repo.count_for_chat", AsyncMock(return_value=3)),
        patch("app.services.chat.messages_repo.create", AsyncMock()),
        patch(
            "app.services.chat.build_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "sys"}]),
        ),
        patch("app.services.chat.litellm_gateway.stream_chat_completion", fake_stream),
        patch("app.services.chat.quota_service.adjust_usage", AsyncMock()),
        patch("app.services.chat.usage_repo.add_tokens", AsyncMock()),
        patch("app.services.chat.jobs.enqueue", AsyncMock()) as enqueue_job,
    ):
        async for _ in chat_module.stream_chat_response(
            AsyncMock(),
            Settings(max_output_tokens=100),
            user_id=fake_user.id,
            chat_id=MagicMock(),
            content="second turn info",
        ):
            pass

    # Memory is enqueued every turn; the title job is first-turn only.
    job_types = [call.args[1] for call in enqueue_job.call_args_list]
    assert job_types.count("memory") == 1
    assert "topic" not in job_types
