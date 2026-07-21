from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.memory import (
    accept_memory_section_rewrite,
    consolidation_rewrite_preserves_facts,
    extract_consolidation_anchors,
    normalize_memory_text,
    section_needs_consolidation,
    sections_need_consolidation,
    select_memories_for_prompt,
    select_memories_semantic,
)


def _closing_background_task(coro, **_kwargs) -> MagicMock:
    """Test double for create_background_task: discards the coroutine
    without actually running it, but closes it so pytest doesn't warn
    "coroutine was never awaited" in tests that aren't exercising the
    background-task behavior itself (see
    test_get_memory_block_warms_semantic_cache_via_tracked_background_task
    for that dedicated test)."""
    coro.close()
    return MagicMock()


def _memory(type_: str, text: str, confidence: float | None):
    m = AsyncMock()
    m.type = type_
    m.text = text
    m.confidence = confidence
    m.updated_at = 0
    return m


class _FakeSessionCM:
    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        return None


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


def test_extract_consolidation_anchors_names_and_orgs():
    prior = "User's name is Bini. User works at Hooh on Recall. Contact: dev@example.com"
    anchors = extract_consolidation_anchors(prior)
    assert "bini" in anchors
    assert "hooh" in anchors
    assert "recall" in anchors
    assert "dev@example.com" in anchors


def test_consolidation_rewrite_preserves_facts_accepts_good_rewrite():
    prior = "User's name is Bini. User works at Hooh. User is a developer."
    summary = "Bini is a developer at Hooh building mobile apps."
    assert consolidation_rewrite_preserves_facts(prior, summary) is True


def test_consolidation_rewrite_preserves_facts_rejects_dropped_anchor():
    prior = "User's name is Bini. User works at Hooh. User is a developer."
    summary = "Bini is a software developer building mobile apps."
    assert consolidation_rewrite_preserves_facts(prior, summary) is False


def test_consolidation_rewrite_preserves_facts_rejects_exactly_20_percent_drop():
    """BUG FIX (off-by-one): "drop >= 20% of anchors" must reject at exactly
    the 20%-dropped / 80%-preserved boundary, not just past it. 5 anchors,
    1 dropped = exactly 80% preserved."""
    prior = "Alice likes Boston, Chicago, Denver, and Everett."
    summary_drops_one = "Alice likes Boston, Chicago, and Denver."
    assert extract_consolidation_anchors(prior) == frozenset(
        {"alice", "boston", "chicago", "denver", "everett"}
    )
    assert consolidation_rewrite_preserves_facts(prior, summary_drops_one) is False
    # Sanity check the gate isn't just always-False now: preserving all 5
    # (dropping none) still passes.
    summary_keeps_all = "Alice loves Boston, Chicago, Denver, and Everett."
    assert consolidation_rewrite_preserves_facts(prior, summary_keeps_all) is True


def test_accept_memory_section_rewrite_rejects_dropped_anchors():
    prior = "User's name is Bini. User works at Hooh. User is a developer."
    bad = "Bini is a software developer building mobile apps."
    assert (
        accept_memory_section_rewrite(
            section_type="profile",
            prior=prior,
            summary=bad,
            confidence=0.9,
            min_confidence=0.4,
        )
        is None
    )


def test_accept_memory_section_rewrite_keeps_expanding_rewrite():
    prior = "User's name is Bini. User works at Hooh. User is a developer."
    good = "Bini is a developer at Hooh building Recall."
    assert (
        accept_memory_section_rewrite(
            section_type="profile",
            prior=prior,
            summary=good,
            confidence=0.9,
            min_confidence=0.4,
        )
        == "Bini is a developer at Hooh building Recall"
    )


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
        ) as embed_mock,
    ):
        result = await load_relevant_memories(session, user, settings, query_vec=[0.1, 0.2, 0.3])

    assert result == [db_hit]
    db_search.assert_awaited_once()
    embed_mock.assert_not_awaited()
    kwargs = db_search.await_args.kwargs
    assert kwargs["min_confidence"] == settings.memory_min_confidence
    assert kwargs["limit"] == settings.memory_inject_limit


@pytest.mark.asyncio
async def test_load_relevant_memories_applies_similarity_cutoff_to_db_path():
    """The DB semantic path must receive max_distance derived from
    memory_min_similarity, so it behaves like the in-memory path (which
    filters low-similarity matches out). Also asserts on the returned
    memories, not just the kwargs passed to search_semantic — when no
    memory has a populated embedding yet, an empty db_hits list must still
    fall back to type-priority selection rather than silently discarding
    every memory (the fix in
    test_load_relevant_memories_returns_empty_when_vectors_populated_but_no_match
    only applies once at least one memory IS embedded)."""
    from app.services.memory import load_relevant_memories

    user = AsyncMock()
    user.id = uuid4()
    user.memory_enabled = True
    session = AsyncMock()
    settings = Settings(
        semantic_memory_enabled=True,
        memory_min_confidence=0.4,
        memory_min_similarity=0.15,
    )

    unembedded = _memory("fact", "Hikes every weekend", 0.9)
    unembedded.embedding = None
    unembedded.embedding_json = None

    with (
        patch(
            "app.repositories.memories.has_any_embedding",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.repositories.memories.list_for_user",
            AsyncMock(return_value=[unembedded]),
        ),
        patch(
            "app.repositories.memories.search_semantic",
            AsyncMock(return_value=[]),
        ) as db_search,
        patch(
            "app.gateways.embedding_gateway.embed_text",
            AsyncMock(return_value=[0.1, 0.2, 0.3]),
        ),
    ):
        result = await load_relevant_memories(session, user, settings, query_vec=[0.1, 0.2, 0.3])

    kwargs = db_search.await_args.kwargs
    # cosine_distance = 1 - cosine_similarity → 1 - 0.15 = 0.85
    assert kwargs["max_distance"] == pytest.approx(0.85)
    assert result == [unembedded]


@pytest.mark.asyncio
async def test_load_relevant_memories_skips_max_distance_when_cutoff_disabled():
    """When memory_min_similarity is 0, no max_distance filter is applied
    (preserves the prior behaviour for configs that disable the cutoff)."""
    from app.services.memory import load_relevant_memories

    user = AsyncMock()
    user.id = uuid4()
    user.memory_enabled = True
    session = AsyncMock()
    settings = Settings(
        semantic_memory_enabled=True,
        memory_min_confidence=0.4,
        memory_min_similarity=0.0,
    )

    with (
        patch(
            "app.repositories.memories.has_any_embedding",
            AsyncMock(return_value=False),
        ),
        patch("app.repositories.memories.list_for_user", AsyncMock(return_value=[])),
        patch(
            "app.repositories.memories.search_semantic",
            AsyncMock(return_value=[]),
        ) as db_search,
        patch(
            "app.gateways.embedding_gateway.embed_text",
            AsyncMock(return_value=[0.1, 0.2, 0.3]),
        ),
    ):
        await load_relevant_memories(session, user, settings, query_vec=[0.1, 0.2, 0.3])

    assert db_search.await_args.kwargs["max_distance"] is None


@pytest.mark.asyncio
async def test_load_relevant_memories_falls_back_to_in_memory_when_db_empty():
    """Represents the transitional state where the pgvector column isn't
    populated yet but the JSON fallback vector is — search_semantic filters
    on Memory.embedding.isnot(None), so an unpopulated pgvector column is
    exactly why db_hits comes back empty even though this memory IS
    semantically embeddable via the JSON path."""
    from app.services.memory import load_relevant_memories

    user = AsyncMock()
    user.id = uuid4()
    user.memory_enabled = True
    session = AsyncMock()
    settings = Settings(
        semantic_memory_enabled=True, memory_min_confidence=0.0, memory_inject_limit=5
    )

    in_memory_hit = _memory("fact", "Python programming", 1.0)
    in_memory_hit.embedding = None
    in_memory_hit.embedding_json = "[1.0, 0.0, 0.0]"

    with (
        patch(
            "app.repositories.memories.has_any_embedding",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.repositories.memories.list_for_user",
            AsyncMock(return_value=[in_memory_hit]),
        ),
        patch("app.repositories.memories.search_semantic", AsyncMock(return_value=[])),
        patch(
            "app.gateways.embedding_gateway.embed_text",
            AsyncMock(return_value=[0.95, 0.05, 0.0]),
        ) as embed_mock,
    ):
        result = await load_relevant_memories(session, user, settings, query_vec=[0.95, 0.05, 0.0])

    assert result == [in_memory_hit]
    embed_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_relevant_memories_returns_empty_when_vectors_populated_but_no_match():
    """BUG FIX: an empty db_hits list is ambiguous — it means either "no row
    has a populated vector yet" or "vectors are populated but none cleared
    the similarity cutoff" (a genuine no-match). This used to treat both
    identically and fall back to type-priority selection, injecting an
    arbitrary "known facts" block even for a query that's actually
    unrelated. When any memory already has a populated pgvector embedding,
    an empty db_hits must mean the second case — return [], not a fallback."""
    from app.services.memory import load_relevant_memories

    user = AsyncMock()
    user.id = uuid4()
    user.memory_enabled = True
    session = AsyncMock()
    settings = Settings(
        semantic_memory_enabled=True, memory_min_confidence=0.0, memory_inject_limit=5
    )

    list_mock = AsyncMock(return_value=[])
    with (
        patch(
            "app.repositories.memories.has_any_embedding",
            AsyncMock(return_value=True),
        ),
        patch("app.repositories.memories.list_for_user", list_mock),
        patch("app.repositories.memories.search_semantic", AsyncMock(return_value=[])),
    ):
        result = await load_relevant_memories(session, user, settings, query_vec=[0.0, 1.0, 0.0])

    assert result == []
    list_mock.assert_not_awaited()


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
@pytest.mark.parametrize("query_vec", [None, [0.1, 0.2, 0.3]])
async def test_load_relevant_memories_returns_empty_on_db_exception(query_vec):
    """BUG FIX: a transient Neon/pgvector failure here used to propagate out
    of load_relevant_memories and, via build_prompt_messages's
    asyncio.gather(...), fail the ENTIRE chat turn over a memory lookup.
    Must degrade to an empty list instead, same as every Redis call in this
    file already does on failure."""
    from app.services.memory import load_relevant_memories

    user = AsyncMock()
    user.id = uuid4()
    user.memory_enabled = True
    session = AsyncMock()
    settings = Settings(semantic_memory_enabled=True)

    with (
        patch(
            "app.repositories.memories.list_for_user",
            AsyncMock(side_effect=RuntimeError("db unavailable")),
        ),
        patch(
            "app.repositories.memories.search_semantic",
            AsyncMock(side_effect=RuntimeError("db unavailable")),
        ),
    ):
        result = await load_relevant_memories(session, user, settings, query_vec=query_vec)

    assert result == []


@pytest.mark.asyncio
async def test_get_memory_block_degrades_to_empty_on_db_exception(fake_redis):
    """End-to-end through the caching layer prompt_builder.py actually
    calls: a DB failure inside load_relevant_memories must not propagate out
    of get_memory_block either, so a simulated chat-turn prompt build still
    completes instead of raising."""
    from app.services.memory import get_memory_block

    user = AsyncMock()
    user.id = uuid4()
    user.memory_enabled = True
    session = AsyncMock()
    settings = Settings(semantic_memory_enabled=False)

    with (
        patch("app.services.memory.get_redis_client", return_value=fake_redis),
        patch(
            "app.repositories.memories.list_for_user",
            AsyncMock(side_effect=RuntimeError("db unavailable")),
        ),
    ):
        block = await get_memory_block(session, user, settings)

    assert block == ""


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
async def test_get_memory_block_warms_semantic_cache_via_tracked_background_task(fake_redis):
    """BUG FIX: the semantic-cache warm task used to be scheduled via bare
    asyncio.create_task, held only by the local `warm_task` variable that
    goes out of scope the instant get_memory_block returns — per asyncio's
    own docs, an unreferenced task is eligible for GC before it completes.
    Must go through create_background_task (a module-level strong-reference
    set), the same primitive chat/stream.py already uses correctly for its
    own fire-and-forget tasks."""
    from app.services.memory import get_memory_block

    user = AsyncMock()
    user.id = uuid4()
    user.memory_enabled = True
    session = AsyncMock()
    settings = Settings(semantic_memory_enabled=True, memory_query_cache_ttl=120)

    fake_task = MagicMock()

    def _create_task_stub(coro, **_kwargs) -> MagicMock:
        # Don't actually run the coroutine (this test only cares which
        # scheduling primitive is used, not the warm-cache logic itself —
        # see test_warm_semantic_cache_write_racing_invalidation_is_never_served
        # for that) — close it so pytest doesn't warn "never awaited".
        coro.close()
        return fake_task

    create_task_mock = MagicMock(side_effect=_create_task_stub)

    with (
        patch("app.services.memory.get_redis_client", return_value=fake_redis),
        patch("app.services.memory.load_relevant_memories", AsyncMock(return_value=[])),
        patch("app.services.memory.create_background_task", create_task_mock),
        # Live embed fails → fall through to type-priority + background warm.
        patch(
            "app.gateways.embedding_gateway.embed_text",
            AsyncMock(return_value=None),
        ),
    ):
        await get_memory_block(session, user, settings, query_text="outdoor hobbies")

    create_task_mock.assert_called_once()
    assert create_task_mock.call_args.kwargs.get("name") == "warm_semantic_memory_cache"
    fake_task.add_done_callback.assert_called_once()


@pytest.mark.asyncio
async def test_get_memory_block_live_embed_on_cache_miss(fake_redis):
    """On embed-cache miss, try a short live embed before type-priority fallback."""
    from app.services.memory import get_memory_block

    user = AsyncMock()
    user.id = uuid4()
    user.memory_enabled = True
    session = AsyncMock()
    settings = Settings(semantic_memory_enabled=True, memory_query_cache_ttl=120)
    query_vec = [0.1, 0.2, 0.3]

    with (
        patch("app.services.memory.get_redis_client", return_value=fake_redis),
        patch(
            "app.gateways.embedding_gateway.embed_text",
            AsyncMock(return_value=query_vec),
        ) as embed_mock,
        patch(
            "app.services.memory.load_relevant_memories",
            AsyncMock(return_value=[_memory("fact", "Likes hiking", 0.9)]),
        ) as load_mock,
        patch("app.services.memory.create_background_task", side_effect=_closing_background_task),
    ):
        block = await get_memory_block(session, user, settings, query_text="outdoor hobbies")

    assert "Likes hiking" in block
    embed_mock.assert_awaited_once()
    assert load_mock.await_args.kwargs.get("query_vec") == query_vec


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
        patch("app.services.memory.create_background_task", side_effect=_closing_background_task),
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
        # This test doesn't exercise the warm-cache background task itself
        # (see test_get_memory_block_warms_semantic_cache_via_tracked_background_task
        # for that) — without this, the real task can outlive this test's
        # event loop and warn "coroutine was never awaited" on teardown.
        patch("app.services.memory.create_background_task", side_effect=_closing_background_task),
    ):
        # No query → per-user block cache (memblock); with query → per-query cache (memquery).
        await get_memory_block(session, user, settings)
        await get_memory_block(session, user, settings, query_text="outdoor hobbies")

    # Both the per-user block key and a per-query key should now exist.
    assert await fake_redis.exists(_memory_block_key(user.id)) == 1
    assert await fake_redis.exists(_memory_query_cache_key(user.id, None, "outdoor hobbies")) == 1

    with patch("app.services.memory.get_redis_client", return_value=fake_redis):
        await invalidate_memory_block(user.id)

    assert await fake_redis.exists(_memory_block_key(user.id)) == 0
    assert await fake_redis.exists(_memory_query_cache_key(user.id, None, "outdoor hobbies")) == 0


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
        patch("app.services.memory.create_background_task", side_effect=_closing_background_task),
    ):
        await get_memory_block(session, user, settings, query_text="outdoor hobbies")
        await get_memory_block(session, user, settings, query_text="weekend plans")

    assert await fake_redis.exists(_memory_query_cache_key(user.id, None, "outdoor hobbies")) == 1
    assert await fake_redis.exists(_memory_query_cache_key(user.id, None, "weekend plans")) == 1

    with patch("app.services.memory.get_redis_client", return_value=fake_redis):
        await invalidate_memory_block(user.id)

    assert await fake_redis.exists(_memory_query_cache_key(user.id, None, "outdoor hobbies")) == 0
    assert await fake_redis.exists(_memory_query_cache_key(user.id, None, "weekend plans")) == 0


@pytest.mark.asyncio
async def test_warm_semantic_cache_write_racing_invalidation_is_never_served(fake_redis):
    """BUG FIX regression: _warm_semantic_memory_cache checks the generation,
    then does a separate write — a concurrent invalidation landing in that
    gap used to be able to resurrect a stale block under the current
    generation. The write is now scoped to the generation it was computed
    under, so even if a write lands after the gap, no later reader can
    retrieve it."""
    from app.services.memory import (
        _memory_generation_key,
        _warm_semantic_memory_cache,
        get_memory_block,
    )

    user_id = uuid4()
    user = AsyncMock()
    user.id = user_id
    user.memory_enabled = True
    session = AsyncMock()
    settings = Settings(semantic_memory_enabled=True, memory_query_cache_ttl=120)

    stale_memories = [_memory("fact", "Stale — computed before invalidation", 0.9)]
    fresh_memories = [_memory("fact", "Fresh — computed after invalidation", 0.9)]

    real_set = fake_redis.set
    triggered = False

    async def racy_set(key: str, *args: object, **kwargs: object) -> object:
        # Fire exactly once, on the query-cache write — simulating a
        # concurrent memory write bumping the generation in the narrow gap
        # between _warm_semantic_memory_cache's gen_after check (which
        # already passed by the time .set() is called) and this write
        # actually landing.
        nonlocal triggered
        if not triggered and str(key).startswith("memquery:"):
            triggered = True
            await fake_redis.incr(_memory_generation_key(user_id))
        return await real_set(key, *args, **kwargs)

    fake_redis.set = racy_set

    with (
        patch("app.services.memory.get_redis_client", return_value=fake_redis),
        patch(
            "app.gateways.embedding_gateway.embed_text",
            AsyncMock(return_value=[0.1, 0.2, 0.3]),
        ),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=user)),
        patch(
            "app.services.memory._semantic_memories_from_vec",
            AsyncMock(return_value=stale_memories),
        ),
        patch("app.core.db.SessionLocal", return_value=_FakeSessionCM(session)),
    ):
        await _warm_semantic_memory_cache(settings, user_id, "outdoor hobbies")

        with patch(
            "app.services.memory.load_relevant_memories",
            AsyncMock(return_value=fresh_memories),
        ):
            block = await get_memory_block(session, user, settings, query_text="outdoor hobbies")

    assert "Stale — computed before invalidation" not in block
    assert "Fresh — computed after invalidation" in block
    # The stale write did land — just under a generation nothing reads anymore.
    current_gen = await fake_redis.get(_memory_generation_key(user_id))
    assert current_gen == "1"


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


def test_split_and_join_memory_facts():
    from app.services.memory import join_memory_facts, split_memory_facts

    text = "Likes hiking. Prefers morning runs. Lives in Austin."
    facts = split_memory_facts(text)
    assert len(facts) == 3
    assert join_memory_facts(facts) == text


@pytest.mark.asyncio
async def test_delete_memory_fact_removes_one_sentence():
    from app.services.memory import delete_memory_fact

    user_id = uuid4()
    session = AsyncMock()
    settings = Settings(mock_llm_enabled=True)
    memory = _memory("fact", "Alpha. Beta. Gamma.", 0.9)
    memory.id = uuid4()

    with (
        patch(
            "app.repositories.memories.get_by_id",
            AsyncMock(return_value=memory),
        ),
        patch(
            "app.gateways.embedding_gateway.embed_text",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.repositories.memories.update_text",
            AsyncMock(return_value=memory),
        ),
        patch(
            "app.services.memory.invalidate_memory_block",
            AsyncMock(),
        ) as invalidate,
        patch(
            "app.services.memory.acquire_memory_write_lock",
            AsyncMock(return_value=True),
        ) as acquire_lock,
        patch(
            "app.services.memory.release_memory_write_lock",
            AsyncMock(),
        ) as release_lock,
    ):
        ok = await delete_memory_fact(session, settings, user_id, memory.id, 1)

    assert ok is True
    invalidate.assert_awaited_once()
    acquire_lock.assert_awaited_once_with(user_id)
    release_lock.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_memory_fact_re_embeds_updated_text():
    """After a fact delete, the remaining text must be re-embedded so semantic
    recall doesn't rank on the stale pre-delete vector."""
    from app.services.memory import delete_memory_fact

    user_id = uuid4()
    session = AsyncMock()
    settings = Settings(mock_llm_enabled=True)
    memory = _memory("fact", "Alpha. Beta. Gamma.", 0.9)
    memory.id = uuid4()

    fake_vec = [0.1, 0.2, 0.3]
    with (
        patch(
            "app.repositories.memories.get_by_id",
            AsyncMock(return_value=memory),
        ),
        patch(
            "app.gateways.embedding_gateway.embed_text",
            AsyncMock(return_value=fake_vec),
        ) as embed,
        patch(
            "app.gateways.embedding_gateway.serialize_embedding",
            return_value="[0.1,0.2,0.3]",
        ) as serialize,
        patch(
            "app.repositories.memories.update_text_and_embedding",
            AsyncMock(return_value=memory),
        ) as update_embed,
        patch(
            "app.repositories.memories.update_text",
            AsyncMock(),
        ) as update_text_only,
        patch(
            "app.services.memory.invalidate_memory_block",
            AsyncMock(),
        ),
        patch(
            "app.services.memory.acquire_memory_write_lock",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.services.memory.release_memory_write_lock",
            AsyncMock(),
        ),
    ):
        ok = await delete_memory_fact(session, settings, user_id, memory.id, 1)

    assert ok is True
    embed.assert_awaited_once()
    serialize.assert_called_once_with(fake_vec)
    update_embed.assert_awaited_once()
    # The text-only fallback must NOT be used when an embedding is available.
    update_text_only.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_memory_fact_matches_by_content_when_index_is_stale():
    """BUG FIX (was silent): a background job can rewrite the section between
    when the client loaded it (computing fact_index from its own copy) and
    when the user taps delete. If the fact the user saw has since moved to a
    different index, the content match must find and delete the fact at its
    CURRENT position, not whatever the stale index now points at."""
    from app.services.memory import delete_memory_fact

    user_id = uuid4()
    session = AsyncMock()
    settings = Settings(mock_llm_enabled=True)
    # Client saw "Beta" at index 1; server's current text has an extra
    # sentence prepended, so "Beta" is now at index 2.
    memory = _memory("fact", "Zeta. Alpha. Beta. Gamma.", 0.9)
    memory.id = uuid4()

    captured: dict = {}

    async def fake_update_text(session, user_id, memory_id, text):
        captured["text"] = text
        return memory

    with (
        patch("app.repositories.memories.get_by_id", AsyncMock(return_value=memory)),
        patch("app.gateways.embedding_gateway.embed_text", AsyncMock(return_value=None)),
        patch(
            "app.repositories.memories.update_text",
            AsyncMock(side_effect=fake_update_text),
        ),
        patch("app.services.memory.invalidate_memory_block", AsyncMock()),
        patch(
            "app.services.memory.acquire_memory_write_lock",
            AsyncMock(return_value=True),
        ),
        patch("app.services.memory.release_memory_write_lock", AsyncMock()),
    ):
        ok = await delete_memory_fact(
            session, settings, user_id, memory.id, 1, expected_text="Beta"
        )

    assert ok is True
    # "Beta" (found at its real position, index 2) is gone; "Alpha" (the
    # stale index 1 pointed at it) survives.
    assert "Beta" not in captured["text"]
    assert "Alpha" in captured["text"]


@pytest.mark.asyncio
async def test_delete_memory_fact_refuses_when_expected_text_is_gone():
    """The fact the client saw was already removed/reworded by a background
    job — refuse rather than guess and delete something else."""
    from app.services.memory import delete_memory_fact

    user_id = uuid4()
    session = AsyncMock()
    settings = Settings(mock_llm_enabled=True)
    memory = _memory("fact", "Alpha. Gamma.", 0.9)
    memory.id = uuid4()

    with (
        patch("app.repositories.memories.get_by_id", AsyncMock(return_value=memory)),
        patch("app.repositories.memories.update_text", AsyncMock()) as update_text,
        patch("app.services.memory.invalidate_memory_block", AsyncMock()) as invalidate,
        patch(
            "app.services.memory.acquire_memory_write_lock",
            AsyncMock(return_value=True),
        ),
        patch("app.services.memory.release_memory_write_lock", AsyncMock()) as release_lock,
    ):
        ok = await delete_memory_fact(
            session, settings, user_id, memory.id, 1, expected_text="Beta"
        )

    assert ok is False
    update_text.assert_not_awaited()
    invalidate.assert_not_awaited()
    # The lock must still be released on the early "refuse" path, not just
    # the success path — otherwise a refused delete would strand the lock
    # for the rest of its TTL.
    release_lock.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_memory_fact_uses_index_among_duplicate_matches():
    """Two identical facts exist — the client's index disambiguates which
    occurrence to remove instead of always taking the first."""
    from app.services.memory import delete_memory_fact

    user_id = uuid4()
    session = AsyncMock()
    settings = Settings(mock_llm_enabled=True)
    memory = _memory("fact", "Alpha. Alpha. Gamma.", 0.9)
    memory.id = uuid4()

    captured: dict = {}

    async def fake_update_text(session, user_id, memory_id, text):
        captured["text"] = text
        return memory

    with (
        patch("app.repositories.memories.get_by_id", AsyncMock(return_value=memory)),
        patch("app.gateways.embedding_gateway.embed_text", AsyncMock(return_value=None)),
        patch(
            "app.repositories.memories.update_text",
            AsyncMock(side_effect=fake_update_text),
        ),
        patch("app.services.memory.invalidate_memory_block", AsyncMock()),
        patch(
            "app.services.memory.acquire_memory_write_lock",
            AsyncMock(return_value=True),
        ),
        patch("app.services.memory.release_memory_write_lock", AsyncMock()),
    ):
        ok = await delete_memory_fact(
            session, settings, user_id, memory.id, 1, expected_text="Alpha"
        )

    assert ok is True
    # One "Alpha" removed, one remains (plus Gamma) — proves it didn't
    # collapse both matches or pick the wrong one arbitrarily.
    assert captured["text"].count("Alpha") == 1
    assert "Gamma" in captured["text"]


@pytest.mark.asyncio
async def test_delete_memory_fact_raises_when_write_lock_stays_busy():
    """A background extraction/consolidation pass is actively rewriting this
    user's memories — the delete must not silently no-op or race it; it
    should surface a distinct busy error the router can turn into a 409
    ("try again"), not a misleading 404."""
    from app.services.memory import MemoryWriteLockBusyError, delete_memory_fact

    user_id = uuid4()
    session = AsyncMock()
    settings = Settings(mock_llm_enabled=True)

    with (
        patch(
            "app.services.memory.acquire_memory_write_lock",
            AsyncMock(return_value=False),
        ) as acquire_lock,
        patch("app.services.memory.release_memory_write_lock", AsyncMock()) as release_lock,
        patch("app.repositories.memories.get_by_id", AsyncMock()) as get_by_id,
        patch("asyncio.sleep", AsyncMock()),
    ):
        with pytest.raises(MemoryWriteLockBusyError):
            await delete_memory_fact(session, settings, user_id, uuid4(), 0)

    # Retried a bounded number of times, never touched the row, and never
    # released a lock it never held.
    assert acquire_lock.await_count == 4
    get_by_id.assert_not_awaited()
    release_lock.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_memory_releases_lock_even_when_delete_fails():
    """delete_memory / delete_memory_section share the same lock-then-finally
    shape as delete_memory_fact — verify the simpler two also acquire and
    always release, including when the row is already gone."""
    from app.services.memory import delete_memory, delete_memory_section

    user_id = uuid4()
    session = AsyncMock()

    with (
        patch(
            "app.services.memory.acquire_memory_write_lock",
            AsyncMock(return_value=True),
        ) as acquire_lock,
        patch("app.services.memory.release_memory_write_lock", AsyncMock()) as release_lock,
        patch("app.repositories.memories.delete_by_id", AsyncMock(return_value=False)),
        patch("app.services.memory.invalidate_memory_block", AsyncMock()) as invalidate,
    ):
        ok = await delete_memory(session, user_id, uuid4())

    assert ok is False
    invalidate.assert_not_awaited()
    acquire_lock.assert_awaited_once_with(user_id)
    release_lock.assert_awaited_once()

    acquire_lock.reset_mock()
    release_lock.reset_mock()
    with (
        patch(
            "app.services.memory.acquire_memory_write_lock",
            AsyncMock(return_value=True),
        ) as acquire_lock,
        patch("app.services.memory.release_memory_write_lock", AsyncMock()) as release_lock,
        patch("app.repositories.memories.delete_by_type", AsyncMock(return_value=0)),
        patch("app.services.memory.invalidate_memory_block", AsyncMock()) as invalidate,
    ):
        ok = await delete_memory_section(session, user_id, "fact")

    assert ok is False
    invalidate.assert_not_awaited()
    acquire_lock.assert_awaited_once_with(user_id)
    release_lock.assert_awaited_once()
