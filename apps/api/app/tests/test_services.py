"""Coverage booster: unit tests for services, gateways and background jobs."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services import chat_titles, memory_llm
from app.services.memory import embedding_text_hash


class _FakeSessionCM:
    def __init__(self, session: AsyncMock | None = None) -> None:
        self._session = session or AsyncMock()

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        return None


def _memory_extraction_sessions(*, count: int = 1) -> tuple[AsyncMock, list[_FakeSessionCM]]:
    session = AsyncMock()
    session.commit = AsyncMock()
    return session, [_FakeSessionCM(session) for _ in range(count)]


@pytest.fixture(autouse=True)
def _memory_write_lock_always_free():
    """extract_and_store_memories now acquires memwrite:{user_id} before its
    read-modify-write section (guards against a concurrent consolidation
    pass racing it). These tests exercise extraction logic, not Redis
    locking, so default the lock to always-acquired;
    test_extract_and_store_skips_when_write_lock_held overrides this to test
    the lock-held path specifically."""
    with (
        patch(
            "app.background.memory_extraction.acquire_memory_write_lock",
            AsyncMock(return_value=True),
        ),
        patch("app.background.memory_extraction.release_memory_write_lock", AsyncMock()),
    ):
        yield


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
    assert "Preferences" in out
    assert "Likes coffee" in out


def test_select_memories_priority_order():
    settings = Settings(memory_min_confidence=0.0, memory_inject_limit=10)
    mems = [
        _mem("fact", "works at ACME"),
        _mem("profile", "Name is Sam"),
        _mem("preference", "Night owl"),
    ]
    result = select_memories_for_prompt(mems, settings)
    # Non-semantic fallback keeps identity/style only — facts need similarity.
    assert [m.type for m in result] == ["profile", "preference"]


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
    with (
        patch.object(memories_repo, "delete_by_id", delete_by_id),
        patch.object(memory_service, "acquire_memory_write_lock", AsyncMock(return_value=True)),
        patch.object(memory_service, "release_memory_write_lock", AsyncMock()),
    ):
        result = await memory_service.delete_memory(AsyncMock(), uuid4(), uuid4())
    assert result is True
    delete_by_id.assert_awaited_once()


# ── quota service ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_remaining_when_nothing_used(fake_redis):
    from app.services import quota as quota_service

    settings = Settings(daily_token_limit=30_000)
    rem = await quota_service.remaining(fake_redis, "u1", daily_limit=settings.daily_token_limit)
    assert rem == 30_000


@pytest.mark.asyncio
async def test_record_usage_accumulates(fake_redis):
    from app.services import quota as quota_service

    await quota_service.record_usage(fake_redis, "u1", 500)
    await quota_service.record_usage(fake_redis, "u1", 300)
    settings = Settings(daily_token_limit=30_000)
    rem = await quota_service.remaining(fake_redis, "u1", daily_limit=settings.daily_token_limit)
    assert rem == 30_000 - 800


# ── litellm gateway (mock path) ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stream_chat_completion_mock():
    from app.gateways import litellm_gateway

    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
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

    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    result = await litellm_gateway.complete_structured(
        settings=settings,
        model_alias="title-model",
        messages=[{"role": "user", "content": "hi"}],
        schema=TitleGenerationResult,
    )
    assert result is None


@pytest.mark.asyncio
async def test_generate_title_mock():
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    title = await chat_titles.generate_title(settings, "Hello", "Hi there")
    assert title is not None
    assert isinstance(title, str)


@pytest.mark.asyncio
async def test_revise_memory_sections_mock():
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    result = await memory_llm.revise_memory_sections(
        settings, "User likes Python", existing_sections={}
    )
    assert result is None or hasattr(result, "sections")


@pytest.mark.asyncio
async def test_revise_memory_sections_prompt_user_stated_only():
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="test-key")
    captured: dict[str, object] = {}

    async def _capture(**kwargs):
        captured["messages"] = kwargs["messages"]
        return None

    with patch(
        "app.services.memory_llm.litellm_gateway.complete_structured",
        _capture,
    ):
        await memory_llm.revise_memory_sections(
            settings,
            "User: I work at Acme\nAssistant: Congrats on the new role!",
            existing_sections={},
        )

    system = captured["messages"][0]["content"]  # type: ignore[index]
    assert "explicitly stated or confirmed by the User line" in system
    assert "never from assistant inferences" in system


@pytest.mark.asyncio
async def test_stream_chat_completion_handles_exception():
    from app.gateways import litellm_gateway
    from app.gateways.litellm_gateway import ModelUnavailableError

    settings = Settings(mock_llm_enabled=False, openrouter_api_key="bad-key")

    async def _fail(**_kwargs):
        raise RuntimeError("network down")

    with patch("app.gateways.litellm_gateway.acompletion", _fail):
        with pytest.raises(ModelUnavailableError) as exc_info:
            async for _t in litellm_gateway.stream_chat_completion(
                settings=settings,
                model_alias="free-chat",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
            ):
                pass
    assert "isn't responding" in exc_info.value.message


# ── background: memory extraction ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_and_store_no_result():
    from app.background.memory_extraction import extract_and_store_memories

    settings = Settings(memory_min_confidence=0.5)
    _, session_locals = _memory_extraction_sessions()
    with (
        patch(
            "app.background.memory_extraction.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=True)),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_sections",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.background.memory_extraction.memories_repo.list_for_user",
            AsyncMock(return_value=[]),
        ),
    ):
        # should not raise
        await extract_and_store_memories(
            settings, user_id=uuid4(), chat_id=uuid4(), transcript="hello"
        )


@pytest.mark.asyncio
async def test_extract_and_store_filters_confidence():
    from app.background.memory_extraction import extract_and_store_memories
    from app.models.schemas import MemorySectionItem, MemorySectionUpdateResult

    settings = Settings(memory_min_confidence=0.7)
    extraction = MemorySectionUpdateResult(
        sections=[
            MemorySectionItem(type="fact", summary="Uses Vim daily.", confidence=0.9),
            MemorySectionItem(type="fact", summary="Low conf fact.", confidence=0.3),
        ]
    )
    upsert = AsyncMock()
    _, session_locals = _memory_extraction_sessions(count=2)
    with (
        patch(
            "app.background.memory_extraction.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=True)),
        ),
        patch(
            "app.background.memory_extraction.memories_repo.list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_sections",
            AsyncMock(return_value=extraction),
        ),
        patch("app.background.memory_extraction.memories_repo.upsert_sections", upsert),
        patch("app.services.memory.invalidate_memory_block", AsyncMock()),
    ):
        await extract_and_store_memories(
            settings, user_id=uuid4(), chat_id=uuid4(), transcript="chat"
        )
    upsert.assert_awaited_once()
    items = upsert.call_args.kwargs["items"]
    assert len(items) == 1
    assert items[0][1].startswith("As of ")
    assert items[0][1].endswith("Uses Vim daily")


@pytest.mark.asyncio
async def test_extract_and_store_swallows_exception():
    from app.background.memory_extraction import extract_and_store_memories

    settings = Settings()
    _, session_locals = _memory_extraction_sessions()
    with (
        patch(
            "app.background.memory_extraction.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=True)),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_sections",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
        patch(
            "app.background.memory_extraction.memories_repo.list_for_user",
            AsyncMock(return_value=[]),
        ),
    ):
        # must not raise
        await extract_and_store_memories(settings, user_id=uuid4(), chat_id=uuid4(), transcript="t")


@pytest.mark.asyncio
async def test_extract_and_store_skips_when_memory_disabled():
    from app.background.memory_extraction import extract_and_store_memories

    settings = Settings()
    _, session_locals = _memory_extraction_sessions()
    with (
        patch(
            "app.background.memory_extraction.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=False)),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_sections",
            AsyncMock(side_effect=AssertionError("should not be called")),
        ),
    ):
        await extract_and_store_memories(settings, user_id=uuid4(), chat_id=uuid4(), transcript="t")


@pytest.mark.asyncio
async def test_extract_and_store_skips_when_write_lock_held():
    """BUG FIX: without a lock, extraction and a concurrently-running
    consolidation pass for the same user can both read the same prior
    section text and whichever commits last silently discards the other's
    write. When memwrite:{user_id} is already held (by consolidation or
    another extraction), this run must skip entirely — no LLM call, no DB
    write — rather than proceed unprotected.

    Uses plain (non-raising) mocks and asserts they were never awaited,
    rather than side_effect=AssertionError, because extract_and_store_memories
    swallows all internal exceptions (Golden Rule 4) — a raised AssertionError
    would just be caught and logged, silently passing even pre-fix."""
    from app.background.memory_extraction import extract_and_store_memories

    settings = Settings()
    get_by_id = AsyncMock()
    revise = AsyncMock()
    upsert = AsyncMock()
    with (
        patch(
            "app.background.memory_extraction.acquire_memory_write_lock",
            AsyncMock(return_value=False),
        ),
        patch("app.background.memory_extraction.users_repo.get_by_id", get_by_id),
        patch("app.background.memory_extraction.memory_llm.revise_memory_sections", revise),
        patch("app.background.memory_extraction.memories_repo.upsert_sections", upsert),
    ):
        await extract_and_store_memories(settings, user_id=uuid4(), chat_id=uuid4(), transcript="t")

    get_by_id.assert_not_awaited()
    revise.assert_not_awaited()
    upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_and_store_reembeds_when_text_changed():
    """Stale-embedding fix: a section whose text changed must be re-embedded,
    even if it already had an embedding."""
    from app.background.memory_extraction import extract_and_store_memories
    from app.models.schemas import MemorySectionItem, MemorySectionUpdateResult

    settings = Settings(memory_min_confidence=0.4)
    extraction = MemorySectionUpdateResult(
        sections=[MemorySectionItem(type="preference", summary="likes TypeScript", confidence=0.9)]
    )

    # Existing memory: has an embedding + old text. Text will change after upsert.
    existing = MagicMock()
    existing.type = "preference"
    existing.text = "likes Python"
    existing.embedding_json = "[0.1,0.2]"

    # After upsert, the "updated" row has new text and still the old embedding.
    updated = MagicMock()
    updated.type = "preference"
    updated.text = "likes TypeScript"
    updated.embedding_json = "[0.1,0.2]"

    embed_calls = AsyncMock(return_value=[0.9, 0.8])
    _, session_locals = _memory_extraction_sessions(count=2)

    with (
        patch(
            "app.background.memory_extraction.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=True)),
        ),
        patch(
            "app.background.memory_extraction.memories_repo.list_for_user",
            AsyncMock(side_effect=[[existing], [updated]]),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_sections",
            AsyncMock(return_value=extraction),
        ),
        patch("app.background.memory_extraction.memories_repo.upsert_sections", AsyncMock()),
        patch("app.services.memory.invalidate_memory_block", AsyncMock()),
        patch("app.gateways.embedding_gateway.embed_text", embed_calls),
        patch("app.gateways.embedding_gateway.serialize_embedding", return_value="[0.9,0.8]"),
    ):
        await extract_and_store_memories(settings, user_id=uuid4(), chat_id=uuid4(), transcript="t")

    embed_calls.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_and_store_reembeds_when_pgvector_missing():
    """A row with embedding_json present but the pgvector `embedding` column
    null must be re-embedded — the DB semantic search filters on `embedding`,
    so a null pgvector makes the memory invisible to DB-side recall even when
    the JSON fallback has a vector."""
    from app.background.memory_extraction import extract_and_store_memories
    from app.models.schemas import MemorySectionItem, MemorySectionUpdateResult

    settings = Settings(memory_min_confidence=0.4)
    extraction = MemorySectionUpdateResult(
        sections=[MemorySectionItem(type="preference", summary="likes TypeScript", confidence=0.9)]
    )

    existing = MagicMock()
    existing.type = "preference"
    existing.text = "likes TypeScript"
    existing.embedding_json = "[0.1,0.2]"

    # After upsert: JSON present but pgvector column null — previously this
    # skipped re-embed (needs_embed checked embedding_json only).
    updated = MagicMock()
    updated.type = "preference"
    updated.text = "likes TypeScript"
    updated.embedding_json = "[0.1,0.2]"
    updated.embedding = None

    embed_calls = AsyncMock(return_value=[0.9, 0.8])
    _, session_locals = _memory_extraction_sessions(count=2)

    with (
        patch(
            "app.background.memory_extraction.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=True)),
        ),
        patch(
            "app.background.memory_extraction.memories_repo.list_for_user",
            AsyncMock(side_effect=[[existing], [updated]]),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_sections",
            AsyncMock(return_value=extraction),
        ),
        patch("app.background.memory_extraction.memories_repo.upsert_sections", AsyncMock()),
        patch("app.services.memory.invalidate_memory_block", AsyncMock()),
        patch("app.gateways.embedding_gateway.embed_text", embed_calls),
        patch("app.gateways.embedding_gateway.serialize_embedding", return_value="[0.9,0.8]"),
    ):
        await extract_and_store_memories(settings, user_id=uuid4(), chat_id=uuid4(), transcript="t")

    embed_calls.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_and_store_reembeds_stale_hash_even_when_text_unchanged_this_pass():
    """BUG FIX regression: if a prior embed attempt failed right after a text
    change, the embedding stays paired with the OLD text while the new text
    is already persisted. A later pass — where the text doesn't change again
    — must still detect and retry that mismatch via embedding_text_hash,
    not just when comparing against the immediately-prior snapshot."""
    from app.background.memory_extraction import extract_and_store_memories
    from app.models.schemas import MemorySectionItem, MemorySectionUpdateResult

    settings = Settings(memory_min_confidence=0.4)
    extraction = MemorySectionUpdateResult(
        sections=[MemorySectionItem(type="preference", summary="likes TypeScript", confidence=0.9)]
    )

    # Existing + updated both already have the new text (unchanged by this
    # pass) but the embedding hash was computed from stale text — as would
    # happen after a previously failed embed_text call.
    existing = MagicMock()
    existing.type = "preference"
    existing.text = "likes TypeScript"
    existing.embedding_json = "[0.1,0.2]"

    updated = MagicMock()
    updated.type = "preference"
    updated.text = "likes TypeScript"
    updated.embedding = [0.1, 0.2]
    updated.embedding_json = "[0.1,0.2]"
    updated.embedding_text_hash = "stale-hash-from-a-failed-embed"

    embed_calls = AsyncMock(return_value=[0.9, 0.8])
    _, session_locals = _memory_extraction_sessions(count=2)

    with (
        patch(
            "app.background.memory_extraction.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=True)),
        ),
        patch(
            "app.background.memory_extraction.memories_repo.list_for_user",
            AsyncMock(side_effect=[[existing], [updated]]),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_sections",
            AsyncMock(return_value=extraction),
        ),
        patch("app.background.memory_extraction.memories_repo.upsert_sections", AsyncMock()),
        patch("app.services.memory.invalidate_memory_block", AsyncMock()),
        patch("app.gateways.embedding_gateway.embed_text", embed_calls),
        patch("app.gateways.embedding_gateway.serialize_embedding", return_value="[0.9,0.8]"),
    ):
        await extract_and_store_memories(settings, user_id=uuid4(), chat_id=uuid4(), transcript="t")

    embed_calls.assert_awaited_once()
    assert updated.embedding_text_hash == embedding_text_hash("likes TypeScript")
    from app.background.memory_extraction import extract_and_store_memories

    session = AsyncMock()
    session.commit = AsyncMock()
    db_open_during_extract: list[bool] = []

    class _FakeSessionCM:
        def __init__(self) -> None:
            self.open = False

        async def __aenter__(self) -> AsyncMock:
            self.open = True
            return session

        async def __aexit__(self, *args: object) -> None:
            self.open = False
            return None

    load_cm = _FakeSessionCM()
    apply_cm = _FakeSessionCM()

    async def fake_revise(*_args: object, **_kwargs: object) -> None:
        db_open_during_extract.append(load_cm.open or apply_cm.open)
        return None

    with (
        patch("app.background.memory_extraction.SessionLocal", side_effect=[load_cm, apply_cm]),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=True)),
        ),
        patch(
            "app.background.memory_extraction.memories_repo.list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_sections",
            AsyncMock(side_effect=fake_revise),
        ),
    ):
        await extract_and_store_memories(
            Settings(),
            user_id=uuid4(),
            chat_id=uuid4(),
            transcript="User: hi\nAssistant: hello",
        )

    assert db_open_during_extract == [False]
    assert session.commit.await_count == 1


# ── topic service ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_topic_service_skips_when_title_none():
    from app.services import topic as topic_service

    mock_set = AsyncMock()
    with (
        patch(
            "app.services.topic.chat_titles.generate_title",
            AsyncMock(return_value=None),
        ),
        patch("app.services.topic.chats_repo.set_title", mock_set),
    ):
        await topic_service.generate_chat_title(Settings(), uuid4(), "hi", "hello")
    mock_set.assert_not_awaited()


@pytest.mark.asyncio
async def test_topic_service_saves_when_title_returned():
    from app.models.orm import Chat
    from app.services import topic as topic_service

    mock_set = AsyncMock()
    chat = MagicMock(spec=Chat)
    chat.title = None
    session = AsyncMock()
    session.commit = AsyncMock()
    session.get = AsyncMock(return_value=chat)

    with (
        patch("app.services.topic.SessionLocal", side_effect=[_FakeSessionCM(session)]),
        patch(
            "app.services.topic.chat_titles.generate_title",
            AsyncMock(return_value="Cool chat title"),
        ),
        patch("app.services.topic.chats_repo.set_title", mock_set),
    ):
        await topic_service.generate_chat_title(Settings(), uuid4(), "hi", "hello")
    mock_set.assert_awaited_once()


@pytest.mark.asyncio
async def test_topic_service_rejects_boring_title():
    from app.services import topic as topic_service

    mock_set = AsyncMock()
    with (
        patch(
            "app.services.topic.chat_titles.generate_title",
            AsyncMock(return_value="New chat"),
        ),
        patch("app.services.topic.chats_repo.set_title", mock_set),
    ):
        await topic_service.generate_chat_title(Settings(), uuid4(), "hi", "hello")
    mock_set.assert_not_awaited()


@pytest.mark.asyncio
async def test_topic_service_skips_empty_messages():
    from app.services import topic as topic_service

    with patch(
        "app.services.topic.chat_titles.generate_title",
        AsyncMock(return_value="Valid title here"),
    ) as mock_gen:
        await topic_service.generate_chat_title(Settings(), uuid4(), "  ", "hello")
    mock_gen.assert_not_awaited()


@pytest.mark.asyncio
async def test_topic_service_skips_when_chat_already_titled():
    from app.models.orm import Chat
    from app.services import topic as topic_service

    mock_set = AsyncMock()
    chat = MagicMock(spec=Chat)
    chat.title = "Existing title"
    session = AsyncMock()
    session.commit = AsyncMock()
    session.get = AsyncMock(return_value=chat)

    with (
        patch("app.services.topic.SessionLocal", side_effect=[_FakeSessionCM(session)]),
        patch(
            "app.services.topic.chat_titles.generate_title",
            AsyncMock(return_value="Fresh title"),
        ) as mock_gen,
        patch("app.services.topic.chats_repo.set_title", mock_set),
    ):
        await topic_service.generate_chat_title(Settings(), uuid4(), "hi", "hello")
    mock_gen.assert_awaited_once()
    mock_set.assert_not_awaited()


@pytest.mark.asyncio
async def test_topic_generate_chat_title_releases_db_before_llm():
    from app.services import topic as topic_service

    session = AsyncMock()
    session.commit = AsyncMock()
    db_open_during_generate: list[bool] = []

    class _TrackingSessionCM(_FakeSessionCM):
        def __init__(self) -> None:
            super().__init__(session)
            self.open = False

        async def __aenter__(self) -> AsyncMock:
            self.open = True
            return await super().__aenter__()

        async def __aexit__(self, *args: object) -> None:
            self.open = False
            await super().__aexit__(*args)

    apply_cm = _TrackingSessionCM()

    async def fake_generate(*_args: object, **_kwargs: object) -> str:
        db_open_during_generate.append(apply_cm.open)
        return "Generated title"

    with (
        patch("app.services.topic.SessionLocal", side_effect=[apply_cm]),
        patch(
            "app.services.topic.chat_titles.generate_title",
            AsyncMock(side_effect=fake_generate),
        ),
        patch("app.services.topic.chats_repo.set_title", AsyncMock()),
        patch.object(session, "get", AsyncMock(return_value=MagicMock(title=None))),
    ):
        await topic_service.generate_chat_title(Settings(), uuid4(), "hi", "hello")

    assert db_open_during_generate == [False]
    assert session.commit.await_count == 1


# ── chat service: quota guard ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stream_chat_response_quota_exceeded():
    from app.exceptions import QuotaExceededError
    from app.services import chat as chat_service

    user_id = uuid4()
    fake_user = MagicMock()
    fake_user.response_style = "balanced"
    with (
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=fake_user)),
        patch("app.services.chat.stream.SessionLocal", lambda: _FakeSessionCM()),
        patch("app.services.quota.reserve_usage", AsyncMock(return_value=False)),
    ):
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
        patch(
            "app.services.auth.tokens_service.issue_token_pair",
            AsyncMock(return_value=("tok", "refresh")),
        ),
        patch("app.services.auth.UserOut.model_validate", return_value=fake_user_out),
    ):
        result = await auth_service.login_dev(
            AsyncMock(), settings, email="dev@test.local", name="Dev", redis=AsyncMock()
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
        patch(
            "app.services.auth.tokens_service.issue_token_pair",
            AsyncMock(return_value=("tok", "refresh")),
        ),
        patch("app.services.auth.UserOut.model_validate", return_value=fake_user_out),
    ):
        result = await auth_service.login_dev(
            AsyncMock(), settings, email="existing@test.local", name="Old", redis=AsyncMock()
        )
    assert result.user.email == "existing@test.local"


@pytest.mark.asyncio
async def test_login_dev_updates_name_for_existing_user():
    from app.models.schemas import UserOut
    from app.services import auth as auth_service

    settings = Settings(dev_auth_enabled=True, jwt_secret="test-secret-long-enough-32-chars!!")
    existing = MagicMock()
    existing.name = "Dev User"
    uid = uuid4()
    fake_user_out = UserOut(
        id=uid,
        email="dev@recall.local",
        name="bini",
        avatar_url=None,
        default_model="free-chat",
        response_style="balanced",
        memory_enabled=True,
        created_at="2024-01-01T00:00:00",
    )

    with (
        patch(
            "app.services.auth.users_repo.get_by_google_sub",
            AsyncMock(return_value=existing),
        ),
        patch(
            "app.services.auth.users_repo.update",
            AsyncMock(return_value=existing),
        ) as mock_update,
        patch(
            "app.services.auth.tokens_service.issue_token_pair",
            AsyncMock(return_value=("tok", "refresh")),
        ),
        patch("app.services.auth.UserOut.model_validate", return_value=fake_user_out),
    ):
        result = await auth_service.login_dev(
            AsyncMock(),
            settings,
            email="dev@recall.local",
            name="bini",
            redis=AsyncMock(),
        )
    mock_update.assert_awaited_once()
    assert result.user.name == "bini"


@pytest.mark.asyncio
async def test_get_current_user_returns_none_for_unknown():
    from app.services import auth as auth_service

    with patch("app.services.auth.users_repo.get_by_id", AsyncMock(return_value=None)):
        user = await auth_service.get_current_user(AsyncMock(), uuid4())
    assert user is None
