from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.memory import (
    normalize_memory_text,
    section_needs_consolidation,
    sections_need_consolidation,
    select_memories_for_prompt,
    select_memories_semantic,
)


def _memory(type_: str, text: str, confidence: float | None):
    m = AsyncMock()
    m.type = type_
    m.text = text
    m.confidence = confidence
    m.updated_at = 0
    return m


def test_normalize_memory_text_strips_trailing_period():
    assert normalize_memory_text("User's name is Bini.") == "User's name is Bini"


def test_section_needs_consolidation_detects_repetition():
    text = (
        "User's name is Binalfew. User's name is Bini. User is a software engineer. "
        "User is a developer."
    )
    assert section_needs_consolidation(text) is True


def test_section_needs_consolidation_accepts_short_summary():
    assert section_needs_consolidation("Bini is a software engineer at Hooh.") is False


def test_section_needs_consolidation_accepts_long_clean_summary():
    text = (
        "Bini prefers short answers, turn-by-turn vocabulary quizzes, and dark glass-morphism UI. "
        "He enjoys Python, clean code, and learning English grammar through practice."
    )
    assert section_needs_consolidation(text) is False


def test_sections_need_consolidation_any_section():
    assert sections_need_consolidation({"profile": "Short.", "preference": "Also short."}) is False


def test_select_memories_filters_low_confidence():
    settings = Settings(memory_min_confidence=0.5, memory_inject_limit=10)
    memories = [
        _memory("fact", "Likes Python", 0.9),
        _memory("focus", "Debugging API", 0.3),
    ]
    selected = select_memories_for_prompt(memories, settings)
    assert len(selected) == 1
    assert selected[0].text == "Likes Python"


def test_select_memories_respects_limit_and_priority():
    settings = Settings(memory_min_confidence=0.0, memory_inject_limit=2)
    memories = [
        _memory("focus", "Low priority", 1.0),
        _memory("profile", "Name is Sam", 0.7),
        _memory("preference", "Short answers", 0.6),
    ]
    selected = select_memories_for_prompt(memories, settings)
    assert len(selected) == 2
    assert selected[0].type == "profile"
    assert selected[1].type == "preference"


def test_select_memories_semantic_ranks_by_similarity():
    settings = Settings(memory_min_confidence=0.0, memory_inject_limit=2)
    python = _memory("fact", "Python programming", 1.0)
    python.embedding_json = "[1.0, 0.0, 0.0]"
    cooking = _memory("fact", "Cooking recipes", 1.0)
    cooking.embedding_json = "[0.0, 1.0, 0.0]"
    selected = select_memories_semantic([python, cooking], [0.95, 0.05, 0.0], settings)
    assert selected[0].text == "Python programming"


@pytest.mark.asyncio
async def test_load_relevant_memories_prefers_db_semantic_search():
    from app.services.memory import load_relevant_memories

    user = AsyncMock()
    user.id = uuid4()
    user.memory_enabled = True
    session = AsyncMock()
    settings = Settings(semantic_memory_enabled=True, memory_min_confidence=0.4)

    db_hit = _memory("fact", "Hikes every weekend", 0.9)

    with (
        patch("app.repositories.memories.list_for_user", AsyncMock(return_value=[])),
        patch(
            "app.repositories.memories.search_semantic",
            AsyncMock(return_value=[db_hit]),
        ) as db_search,
        patch(
            "app.gateways.embedding_gateway.embed_text",
            AsyncMock(return_value=[0.1, 0.2, 0.3]),
        ),
    ):
        result = await load_relevant_memories(session, user, settings, query_text="outdoors")

    assert result == [db_hit]
    db_search.assert_awaited_once()
    kwargs = db_search.await_args.kwargs
    assert kwargs["min_confidence"] == settings.memory_min_confidence
    assert kwargs["limit"] == settings.memory_inject_limit


@pytest.mark.asyncio
async def test_load_relevant_memories_falls_back_to_in_memory_when_db_empty():
    from app.services.memory import load_relevant_memories

    user = AsyncMock()
    user.id = uuid4()
    user.memory_enabled = True
    session = AsyncMock()
    settings = Settings(
        semantic_memory_enabled=True, memory_min_confidence=0.0, memory_inject_limit=5
    )

    in_memory_hit = _memory("fact", "Python programming", 1.0)
    in_memory_hit.embedding_json = "[1.0, 0.0, 0.0]"

    with (
        patch(
            "app.repositories.memories.list_for_user",
            AsyncMock(return_value=[in_memory_hit]),
        ),
        patch("app.repositories.memories.search_semantic", AsyncMock(return_value=[])),
        patch(
            "app.gateways.embedding_gateway.embed_text",
            AsyncMock(return_value=[0.95, 0.05, 0.0]),
        ),
    ):
        result = await load_relevant_memories(session, user, settings, query_text="coding")

    assert result == [in_memory_hit]


@pytest.mark.asyncio
async def test_load_relevant_memories_priority_fallback_when_no_query():
    from app.services.memory import load_relevant_memories

    user = AsyncMock()
    user.id = uuid4()
    user.memory_enabled = True
    session = AsyncMock()
    settings = Settings(
        semantic_memory_enabled=True, memory_min_confidence=0.0, memory_inject_limit=5
    )

    profile = _memory("profile", "Name is Sam", 0.7)
    fact = _memory("fact", "Likes Python", 0.9)

    with (
        patch(
            "app.repositories.memories.list_for_user",
            AsyncMock(return_value=[fact, profile]),
        ),
        patch("app.repositories.memories.search_semantic", AsyncMock()) as db_search,
    ):
        result = await load_relevant_memories(session, user, settings, query_text=None)

    # No query → priority selection (profile first), DB search never called.
    assert result[0].type == "profile"
    db_search.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_semantic_repo_returns_ranked_rows():
    from app.repositories.memories import search_semantic

    session = AsyncMock()
    hit = _memory("fact", "Hikes every weekend", 0.9)
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [hit]
    session.execute = AsyncMock(return_value=result_mock)

    rows = await search_semantic(session, uuid4(), [0.1, 0.2, 0.3], min_confidence=0.4, limit=5)
    assert rows == [hit]


@pytest.mark.asyncio
async def test_get_memory_block_query_cache(fake_redis):
    from app.services.memory import get_memory_block

    user = AsyncMock()
    user.id = uuid4()
    user.memory_enabled = True
    session = AsyncMock()
    settings = Settings(semantic_memory_enabled=True, memory_query_cache_ttl=120)

    with (
        patch("app.services.memory.get_redis_client", return_value=fake_redis),
        patch(
            "app.services.memory.load_relevant_memories",
            AsyncMock(return_value=[_memory("fact", "Likes hiking", 0.9)]),
        ) as load_mock,
    ):
        first = await get_memory_block(session, user, settings, query_text="outdoor hobbies")
        second = await get_memory_block(session, user, settings, query_text="outdoor hobbies")
    assert "Likes hiking" in first
    assert second == first
    load_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalidate_memory_block_clears_block_and_query_cache(fake_redis):
    from app.services.memory import (
        _memory_block_key,
        _memory_query_cache_key,
        get_memory_block,
        invalidate_memory_block,
    )

    user = AsyncMock()
    user.id = uuid4()
    user.memory_enabled = True
    session = AsyncMock()
    settings = Settings(semantic_memory_enabled=True, memory_query_cache_ttl=120)

    with (
        patch("app.services.memory.get_redis_client", return_value=fake_redis),
        patch(
            "app.services.memory.load_relevant_memories",
            AsyncMock(return_value=[_memory("fact", "Likes hiking", 0.9)]),
        ),
    ):
        # No query → per-user block cache (memblock); with query → per-query cache (memquery).
        await get_memory_block(session, user, settings)
        await get_memory_block(session, user, settings, query_text="outdoor hobbies")

    # Both the per-user block key and a per-query key should now exist.
    assert await fake_redis.exists(_memory_block_key(user.id)) == 1
    assert await fake_redis.exists(_memory_query_cache_key(user.id, "outdoor hobbies")) == 1

    with patch("app.services.memory.get_redis_client", return_value=fake_redis):
        await invalidate_memory_block(user.id)

    assert await fake_redis.exists(_memory_block_key(user.id)) == 0
    assert await fake_redis.exists(_memory_query_cache_key(user.id, "outdoor hobbies")) == 0


@pytest.mark.asyncio
async def test_invalidate_memory_block_clears_multiple_query_keys(fake_redis):
    from app.services.memory import (
        _memory_query_cache_key,
        get_memory_block,
        invalidate_memory_block,
    )

    user = AsyncMock()
    user.id = uuid4()
    user.memory_enabled = True
    session = AsyncMock()
    settings = Settings(semantic_memory_enabled=True, memory_query_cache_ttl=120)

    with (
        patch("app.services.memory.get_redis_client", return_value=fake_redis),
        patch(
            "app.services.memory.load_relevant_memories",
            AsyncMock(return_value=[_memory("fact", "Likes hiking", 0.9)]),
        ),
    ):
        await get_memory_block(session, user, settings, query_text="outdoor hobbies")
        await get_memory_block(session, user, settings, query_text="weekend plans")

    assert await fake_redis.exists(_memory_query_cache_key(user.id, "outdoor hobbies")) == 1
    assert await fake_redis.exists(_memory_query_cache_key(user.id, "weekend plans")) == 1

    with patch("app.services.memory.get_redis_client", return_value=fake_redis):
        await invalidate_memory_block(user.id)

    assert await fake_redis.exists(_memory_query_cache_key(user.id, "outdoor hobbies")) == 0
    assert await fake_redis.exists(_memory_query_cache_key(user.id, "weekend plans")) == 0


@pytest.mark.asyncio
async def test_memory_reenable_loads_fresh_after_invalidation(fake_redis):
    from app.services.memory import get_memory_block, invalidate_memory_block

    user = AsyncMock()
    user.id = uuid4()
    user.memory_enabled = True
    session = AsyncMock()
    settings = Settings(memory_cache_ttl=120)

    load_mock = AsyncMock(
        side_effect=[
            [_memory("fact", "Old fact", 0.9)],
            [_memory("fact", "New fact", 0.9)],
        ]
    )
    with (
        patch("app.services.memory.get_redis_client", return_value=fake_redis),
        patch("app.services.memory.load_relevant_memories", load_mock),
    ):
        first = await get_memory_block(session, user, settings)
        user.memory_enabled = False
        assert await get_memory_block(session, user, settings) == ""
        await invalidate_memory_block(user.id)
        user.memory_enabled = True
        second = await get_memory_block(session, user, settings)

    assert "Old fact" in first
    assert "New fact" in second
    assert load_mock.await_count == 2
