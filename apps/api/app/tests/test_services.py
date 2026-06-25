"""Coverage booster: unit tests for services, gateways and background jobs."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings

# ── memory service ─────────────────────────────────────────────────────────────
from app.services.memory import format_memory_block, select_memories_for_prompt


def _mem(type_: str, text: str, confidence: float | None = 0.9):
    m = MagicMock()
    m.type = type_
    m.text = text
    m.confidence = confidence
    m.updated_at = 0
    return m


def test_format_memory_block_empty():
    assert format_memory_block([]) == ""


def test_format_memory_block_nonempty():
    out = format_memory_block([_mem("preference", "Likes coffee")])
    assert "preference" in out
    assert "Likes coffee" in out


def test_select_memories_priority_order():
    settings = Settings(memory_min_confidence=0.0, memory_inject_limit=10)
    mems = [
        _mem("fact", "works at ACME"),
        _mem("profile", "Name is Sam"),
        _mem("preference", "Night owl"),
    ]
    result = select_memories_for_prompt(mems, settings)
    assert result[0].type == "profile"
    assert result[1].type == "preference"
    assert result[2].type == "fact"


@pytest.mark.asyncio
async def test_load_relevant_memories_disabled():
    from app.services.memory import load_relevant_memories

    user = MagicMock(memory_enabled=False)
    result = await load_relevant_memories(AsyncMock(), user, Settings())
    assert result == []


@pytest.mark.asyncio
async def test_delete_memory_delegates():
    from app.repositories import memories as memories_repo
    from app.services import memory as memory_service

    delete_by_id = AsyncMock(return_value=True)
    with patch.object(memories_repo, "delete_by_id", delete_by_id):
        result = await memory_service.delete_memory(AsyncMock(), uuid4(), uuid4())
    assert result is True
    delete_by_id.assert_awaited_once()


# ── quota service ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_remaining_when_nothing_used(fake_redis):
    from app.services import quota as quota_service

    settings = Settings(daily_token_limit=30_000)
    rem = await quota_service.remaining(fake_redis, "u1", settings)
    assert rem == 30_000


@pytest.mark.asyncio
async def test_record_usage_accumulates(fake_redis):
    from app.services import quota as quota_service

    await quota_service.record_usage(fake_redis, "u1", 500)
    await quota_service.record_usage(fake_redis, "u1", 300)
    settings = Settings(daily_token_limit=30_000)
    rem = await quota_service.remaining(fake_redis, "u1", settings)
    assert rem == 30_000 - 800


# ── litellm gateway (mock path) ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stream_chat_completion_mock():
    from app.gateways import litellm_gateway

    settings = Settings(mock_llm_enabled=True)
    tokens = []
    async for t in litellm_gateway.stream_chat_completion(
        settings=settings,
        model_alias="free-chat",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=100,
    ):
        tokens.append(t)
    assert len(tokens) > 0
    assert all(isinstance(t, str) for t in tokens)


@pytest.mark.asyncio
async def test_complete_structured_mock_returns_none():
    from app.gateways import litellm_gateway
    from app.models.schemas import TitleGenerationResult

    settings = Settings(mock_llm_enabled=True)
    result = await litellm_gateway.complete_structured(
        settings=settings,
        model_alias="title-model",
        messages=[{"role": "user", "content": "hi"}],
        schema=TitleGenerationResult,
    )
    assert result is None


@pytest.mark.asyncio
async def test_generate_title_mock():
    from app.gateways import litellm_gateway

    settings = Settings(mock_llm_enabled=True)
    title = await litellm_gateway.generate_title(settings, "Hello", "Hi there")
    assert title is not None
    assert isinstance(title, str)


@pytest.mark.asyncio
async def test_extract_memories_mock():
    from app.gateways import litellm_gateway

    settings = Settings(mock_llm_enabled=True)
    result = await litellm_gateway.extract_memories(settings, "User likes Python")
    # mock returns None or MemoryExtractionResult
    assert result is None or hasattr(result, "memories")


@pytest.mark.asyncio
async def test_stream_chat_completion_handles_exception():
    from app.gateways import litellm_gateway
    from app.gateways.litellm_gateway import ModelUnavailableError

    settings = Settings(mock_llm_enabled=False, deepseek_api_key="bad-key")

    async def _fail(**_kwargs):
        raise RuntimeError("network down")

    with patch("app.gateways.litellm_gateway.acompletion", _fail):
        with pytest.raises(ModelUnavailableError):
            async for _t in litellm_gateway.stream_chat_completion(
                settings=settings,
                model_alias="free-chat",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
            ):
                pass


# ── background: memory extraction ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_and_store_no_result():
    from app.background.memory_extraction import extract_and_store_memories

    settings = Settings(memory_min_confidence=0.5)
    with patch(
        "app.background.memory_extraction.litellm_gateway.extract_memories",
        AsyncMock(return_value=None),
    ):
        # should not raise
        await extract_and_store_memories(
            AsyncMock(), settings, user_id=uuid4(), chat_id=uuid4(), transcript="hello"
        )


@pytest.mark.asyncio
async def test_extract_and_store_filters_confidence():
    from app.background.memory_extraction import extract_and_store_memories
    from app.models.schemas import MemoryExtractionItem, MemoryExtractionResult

    settings = Settings(memory_min_confidence=0.7)
    extraction = MemoryExtractionResult(
        memories=[
            MemoryExtractionItem(type="fact", text="uses Vim", confidence=0.9),
            MemoryExtractionItem(type="fact", text="low conf", confidence=0.3),
        ]
    )
    upsert = AsyncMock()
    with (
        patch(
            "app.background.memory_extraction.litellm_gateway.extract_memories",
            AsyncMock(return_value=extraction),
        ),
        patch("app.background.memory_extraction.memories_repo.upsert_many", upsert),
    ):
        await extract_and_store_memories(
            AsyncMock(), settings, user_id=uuid4(), chat_id=uuid4(), transcript="chat"
        )
    upsert.assert_awaited_once()
    items = upsert.call_args.kwargs["items"]
    assert len(items) == 1
    assert items[0][1] == "uses Vim"


@pytest.mark.asyncio
async def test_extract_and_store_swallows_exception():
    from app.background.memory_extraction import extract_and_store_memories

    settings = Settings()
    with patch(
        "app.background.memory_extraction.litellm_gateway.extract_memories",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        # must not raise
        await extract_and_store_memories(
            AsyncMock(), settings, user_id=uuid4(), chat_id=uuid4(), transcript="t"
        )


# ── topic service ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_topic_service_skips_when_title_none():
    from app.services import topic as topic_service

    mock_set = AsyncMock()
    with (
        patch(
            "app.services.topic.litellm_gateway.generate_title",
            AsyncMock(return_value=None),
        ),
        patch("app.services.topic.chats_repo.set_title", mock_set),
    ):
        await topic_service.generate_chat_title(AsyncMock(), Settings(), uuid4(), "hi", "hello")
    mock_set.assert_not_awaited()


@pytest.mark.asyncio
async def test_topic_service_saves_when_title_returned():
    from app.models.orm import Chat
    from app.services import topic as topic_service

    mock_set = AsyncMock()
    chat = MagicMock(spec=Chat)
    chat.title = None
    session = AsyncMock()
    session.get = AsyncMock(return_value=chat)

    with (
        patch(
            "app.services.topic.litellm_gateway.generate_title",
            AsyncMock(return_value="Cool chat title"),
        ),
        patch("app.services.topic.chats_repo.set_title", mock_set),
    ):
        await topic_service.generate_chat_title(session, Settings(), uuid4(), "hi", "hello")
    mock_set.assert_awaited_once()


# ── chat service: quota guard ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stream_chat_response_quota_exceeded():
    from app.exceptions import QuotaExceededError
    from app.services import chat as chat_service

    user_id = uuid4()
    with patch("app.services.chat.quota_service.reserve_usage", AsyncMock(return_value=False)):
        with pytest.raises(QuotaExceededError):
            async for _t in chat_service.stream_chat_response(
                AsyncMock(),
                Settings(),
                user_id=user_id,
                chat_id=uuid4(),
                content="hi",
            ):
                pass


# ── auth service ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_dev_creates_user():
    from app.models.schemas import UserOut
    from app.services import auth as auth_service

    settings = Settings(dev_auth_enabled=True, jwt_secret="test-secret-long-enough-32-chars!!")
    uid = uuid4()
    fake_user_out = UserOut(
        id=uid,
        email="dev@test.local",
        name="Dev",
        avatar_url=None,
        default_model="free-chat",
        response_style="balanced",
        memory_enabled=True,
        created_at="2024-01-01T00:00:00",
    )
    with (
        patch("app.services.auth.users_repo.get_by_google_sub", AsyncMock(return_value=None)),
        patch("app.services.auth.users_repo.create", AsyncMock(return_value=MagicMock())),
        patch("app.services.auth.create_access_token", return_value="tok"),
        patch("app.services.auth.UserOut.model_validate", return_value=fake_user_out),
    ):
        result = await auth_service.login_dev(
            AsyncMock(), settings, email="dev@test.local", name="Dev"
        )
    assert result.access_token == "tok"
    assert result.user.email == "dev@test.local"


@pytest.mark.asyncio
async def test_login_dev_returns_existing_user():
    from app.models.schemas import UserOut
    from app.services import auth as auth_service

    settings = Settings(dev_auth_enabled=True, jwt_secret="test-secret-long-enough-32-chars!!")
    uid = uuid4()
    fake_user_out = UserOut(
        id=uid,
        email="existing@test.local",
        name="Old",
        avatar_url=None,
        default_model="free-chat",
        response_style="balanced",
        memory_enabled=True,
        created_at="2024-01-01T00:00:00",
    )

    with (
        patch(
            "app.services.auth.users_repo.get_by_google_sub",
            AsyncMock(return_value=MagicMock()),
        ),
        patch("app.services.auth.create_access_token", return_value="tok"),
        patch("app.services.auth.UserOut.model_validate", return_value=fake_user_out),
    ):
        result = await auth_service.login_dev(
            AsyncMock(), settings, email="existing@test.local", name="Old"
        )
    assert result.user.email == "existing@test.local"


@pytest.mark.asyncio
async def test_get_current_user_returns_none_for_unknown():
    from app.services import auth as auth_service

    with patch("app.services.auth.users_repo.get_by_id", AsyncMock(return_value=None)):
        user = await auth_service.get_current_user(AsyncMock(), uuid4())
    assert user is None
