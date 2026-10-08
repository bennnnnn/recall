from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.gateways.web_search_gateway import WebSearchHit, search_web
from app.modules.web_search import augment_prompt_messages


@pytest.mark.asyncio
async def test_augment_prompt_injects_results_before_user():
    settings = Settings(mock_llm_enabled=True, tavily_api_key="", mcp_tool_loop_enabled=False)
    messages = [
        {"role": "system", "content": "base"},
        {"role": "user", "content": "old"},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "search the web for latest AI news"},
    ]
    with patch(
        "app.modules.web_search.search_cache.web_search_gateway.search_web",
        AsyncMock(
            return_value=[
                WebSearchHit(title="Hit", url="https://x.com", snippet="info"),
            ]
        ),
    ):
        out, hits = await augment_prompt_messages(
            messages,
            "search the web for latest AI news",
            settings,
        )
    assert out[-1]["role"] == "user"
    assert out[-2]["role"] == "system"
    assert "Web search results" in out[-2]["content"]
    assert len(hits) == 1


@pytest.mark.asyncio
async def test_augment_prompt_emits_searching_status_with_query_detail():
    settings = Settings(mock_llm_enabled=True, tavily_api_key="", mcp_tool_loop_enabled=False)
    messages = [
        {"role": "user", "content": "search the web for latest AI news"},
    ]
    statuses: list[tuple[str, str | None]] = []

    async def on_status(phase: str, detail: str | None = None) -> None:
        statuses.append((phase, detail))

    with patch(
        "app.modules.web_search.search_cache.web_search_gateway.search_web",
        AsyncMock(
            return_value=[
                WebSearchHit(title="Hit", url="https://x.com", snippet="info"),
            ]
        ),
    ):
        await augment_prompt_messages(
            messages,
            "search the web for latest AI news",
            settings,
            on_status=on_status,
        )

    assert len(statuses) == 1
    phase, detail = statuses[0]
    assert phase == "searching"
    # The first search query rides along so the client can show what
    # is being looked up.
    assert detail
    assert "ai news" in detail.lower()


@pytest.mark.asyncio
async def test_augment_prompt_injects_empty_block_when_no_hits():
    settings = Settings(
        mock_llm_enabled=False, web_search_fallback_enabled=False, mcp_tool_loop_enabled=False
    )
    messages = [
        {"role": "system", "content": "base"},
        {"role": "user", "content": "what's happening in the world today"},
    ]
    with patch(
        "app.modules.web_search.search_cache.web_search_gateway.search_web",
        AsyncMock(return_value=[]),
    ):
        out, hits = await augment_prompt_messages(
            messages,
            "what's happening in the world today",
            settings,
        )
    assert out[-1]["role"] == "user"
    assert out[-2]["role"] == "system"
    assert "returned no usable results" in out[-2]["content"]
    assert hits == []


@pytest.mark.asyncio
async def test_augment_prompt_follow_up_look_it_up(fake_redis):
    settings = Settings(mcp_tool_loop_enabled=False)
    messages = [
        {"role": "system", "content": "base"},
        {"role": "user", "content": "Show me yesterdays game"},
        {"role": "assistant", "content": "I don't have live scores."},
        {"role": "user", "content": "Look it up"},
    ]
    with (
        patch("app.modules.web_search.search_cache.get_redis_client", return_value=fake_redis),
        patch(
            "app.modules.web_search.search_cache.web_search_gateway.search_web",
            AsyncMock(
                return_value=[
                    WebSearchHit(title="Scores", url="https://scores.example", snippet="2-1"),
                ]
            ),
        ) as search_mock,
    ):
        out, hits = await augment_prompt_messages(
            messages, "Look it up", settings, user_timezone="UTC"
        )
    assert search_mock.await_count >= 1
    first_query = search_mock.await_args_list[0].args[1]
    assert first_query.lower() != "look it up"
    assert "Web search results" in out[-2]["content"]
    assert len(hits) == 1


@pytest.mark.asyncio
async def test_augment_prompt_skips_personal_planning():
    settings = Settings()
    messages = [{"role": "system", "content": "base"}]
    with patch(
        "app.modules.web_search.search_cache.web_search_gateway.search_web",
        AsyncMock(),
    ) as search_mock:
        out, hits = await augment_prompt_messages(
            messages, "What am I trying to get done today?", settings
        )
    search_mock.assert_not_called()
    assert out == messages
    assert hits == []


@pytest.mark.asyncio
async def test_augment_prompt_skips_when_not_needed():
    settings = Settings()
    messages = [{"role": "system", "content": "base"}]
    with patch(
        "app.modules.web_search.search_cache.web_search_gateway.search_web",
        AsyncMock(),
    ) as search_mock:
        out, hits = await augment_prompt_messages(messages, "explain recursion", settings)
    search_mock.assert_not_called()
    assert out == messages
    assert hits == []


@pytest.mark.asyncio
async def test_search_web_uses_mock_without_api_key():
    settings = Settings(mock_llm_enabled=True, tavily_api_key="", web_search_fallback_enabled=False)
    hits = await search_web(settings, "test query")
    assert len(hits) == 1
    assert "Mock search" in hits[0].title


@pytest.mark.asyncio
async def test_run_search_parallelizes_queries():
    import asyncio
    import time

    from app.modules.web_search.search_cache import _run_search

    settings = Settings(web_search_max_results=10, mock_llm_enabled=True)

    async def mock_search(_settings, query, *, max_results, budget=None, redis=None):
        await asyncio.sleep(0.04 if query == "slow" else 0.01)
        return [
            WebSearchHit(
                title=f"{query} hit",
                url=f"https://example.com/{query}",
                snippet="snippet",
            )
        ]

    with patch("app.modules.web_search.search_cache._search_with_cache", side_effect=mock_search):
        start = time.monotonic()
        merged, tried = await _run_search(settings, ["slow", "fast-a", "fast-b"])
        elapsed = time.monotonic() - start

    assert tried == ["slow", "fast-a", "fast-b"]
    assert len(merged) == 3
    assert elapsed < 0.08


@pytest.mark.asyncio
async def test_run_search_reserves_tavily_once_per_turn(fake_redis):
    """A multi-query turn must spend at most ONE daily Tavily search, not one
    per fanned-out query — the whole point of the shared per-turn budget."""
    from unittest.mock import MagicMock
    from uuid import uuid4

    from app.modules.web_search.search_cache import _run_search

    settings = Settings(web_search_max_results=10, mock_llm_enabled=True, tavily_api_key="test-key")
    user = MagicMock()
    user.id = uuid4()
    user.plan = "free"

    reserve_calls = 0

    async def counting_reserve(_redis, _user_id, *, limit):
        nonlocal reserve_calls
        reserve_calls += 1
        return True

    async def fake_search(_settings, query, *, max_results=10, skip_tavily=False):
        return [WebSearchHit(title=query, url=f"https://ex/{query}", snippet="s")]

    with (
        patch("app.modules.web_search.search_cache.get_redis_client", return_value=fake_redis),
        patch(
            "app.modules.web_search.search_cache.quota_service.reserve_tavily_search",
            counting_reserve,
        ),
        patch("app.modules.web_search.search_cache.web_search_gateway.search_web", fake_search),
    ):
        merged, _tried = await _run_search(
            settings,
            ["q1", "q2", "q3", "q4"],
            user=user,
            redis=fake_redis,
        )

    assert reserve_calls == 1
    assert len(merged) == 4


@pytest.mark.asyncio
async def test_run_cached_search_shares_bound_tavily_budget(fake_redis):
    """Two MCP-style run_cached_search calls in one turn spend one Tavily slot."""
    from unittest.mock import MagicMock
    from uuid import uuid4

    from app.modules.web_search.search_cache import bind_tavily_turn_budget, run_cached_search

    settings = Settings(web_search_max_results=10, mock_llm_enabled=True, tavily_api_key="test-key")
    user = MagicMock()
    user.id = uuid4()
    user.plan = "free"

    reserve_calls = 0

    async def counting_reserve(_redis, _user_id, *, limit):
        nonlocal reserve_calls
        reserve_calls += 1
        return True

    async def fake_search(_settings, query, *, max_results=10, skip_tavily=False):
        return [WebSearchHit(title=query, url=f"https://ex/{query}", snippet="s")]

    with (
        patch("app.modules.web_search.search_cache.get_redis_client", return_value=fake_redis),
        patch(
            "app.modules.web_search.search_cache.quota_service.reserve_tavily_search",
            counting_reserve,
        ),
        patch("app.modules.web_search.search_cache.web_search_gateway.search_web", fake_search),
        bind_tavily_turn_budget(settings=settings, user=user),
    ):
        await run_cached_search(settings, ["q1"], user=user, redis=fake_redis)
        await run_cached_search(settings, ["q2"], user=user, redis=fake_redis)

    assert reserve_calls == 1


@pytest.mark.asyncio
async def test_run_search_skips_tavily_reservation_when_unconfigured(fake_redis):
    """No Tavily key → the turn uses free DuckDuckGo, so it must not spend a
    daily Tavily search reserving a call Tavily never performs."""
    from unittest.mock import MagicMock
    from uuid import uuid4

    from app.modules.web_search.search_cache import _run_search

    settings = Settings(web_search_max_results=10, mock_llm_enabled=True, tavily_api_key="")
    user = MagicMock()
    user.id = uuid4()
    user.plan = "free"

    reserve_calls = 0

    async def counting_reserve(_redis, _user_id, *, limit):
        nonlocal reserve_calls
        reserve_calls += 1
        return True

    async def fake_search(_settings, query, *, max_results=10, skip_tavily=False):
        return [WebSearchHit(title=query, url=f"https://ex/{query}", snippet="s")]

    with (
        patch("app.modules.web_search.search_cache.get_redis_client", return_value=fake_redis),
        patch(
            "app.modules.web_search.search_cache.quota_service.reserve_tavily_search",
            counting_reserve,
        ),
        patch("app.modules.web_search.search_cache.web_search_gateway.search_web", fake_search),
    ):
        merged, _tried = await _run_search(settings, ["q1", "q2"], user=user, redis=fake_redis)

    assert reserve_calls == 0
    assert len(merged) == 2


@pytest.mark.asyncio
async def test_skip_tavily_when_user_missing(fake_redis):
    """No user on the budget must not run uncapped Tavily."""
    from app.modules.web_search.search_cache import _TurnTavilyBudget

    settings = Settings(tavily_api_key="test-key")
    budget = _TurnTavilyBudget(settings=settings, user=None)
    reserve = AsyncMock(side_effect=AssertionError("must not reserve without a user"))
    with patch(
        "app.modules.web_search.search_cache.quota_service.reserve_tavily_search",
        reserve,
    ):
        assert await budget.skip_tavily(fake_redis) is True
        assert await budget.skip_tavily(fake_redis) is True
    reserve.assert_not_called()


@pytest.mark.asyncio
async def test_skip_tavily_on_redis_reserve_error(fake_redis):
    from unittest.mock import MagicMock
    from uuid import uuid4

    from app.exceptions import RedisUnavailableError
    from app.modules.web_search.search_cache import _TurnTavilyBudget

    settings = Settings(tavily_api_key="test-key")
    user = MagicMock()
    user.id = uuid4()
    user.plan = "free"
    budget = _TurnTavilyBudget(settings=settings, user=user)
    with patch(
        "app.modules.web_search.search_cache.quota_service.reserve_tavily_search",
        AsyncMock(side_effect=RedisUnavailableError()),
    ):
        assert await budget.skip_tavily(fake_redis) is True
        assert await budget.skip_tavily(fake_redis) is True


@pytest.mark.asyncio
async def test_search_cache_is_per_user(fake_redis):
    from unittest.mock import MagicMock
    from uuid import uuid4

    from app.modules.web_search.search_cache import _search_with_cache, _TurnTavilyBudget

    settings = Settings(web_search_cache_ttl=300, mock_llm_enabled=True, tavily_api_key="")
    u1 = MagicMock()
    u1.id = uuid4()
    u1.plan = "free"
    u2 = MagicMock()
    u2.id = uuid4()
    u2.plan = "free"
    hit = WebSearchHit(title="Hit", url="https://example.com", snippet="snippet")
    search_mock = AsyncMock(return_value=[hit])
    with (
        patch("app.modules.web_search.search_cache.get_redis_client", return_value=fake_redis),
        patch("app.modules.web_search.search_cache.web_search_gateway.search_web", search_mock),
    ):
        await _search_with_cache(
            settings,
            "same query",
            max_results=3,
            budget=_TurnTavilyBudget(settings=settings, user=u1),
            redis=fake_redis,
        )
        await _search_with_cache(
            settings,
            "same query",
            max_results=3,
            budget=_TurnTavilyBudget(settings=settings, user=u2),
            redis=fake_redis,
        )
    assert search_mock.call_count == 2


@pytest.mark.asyncio
async def test_run_search_dedupes_across_queries_and_respects_limit():
    from app.modules.web_search.search_cache import _run_search

    settings = Settings(web_search_max_results=2, mock_llm_enabled=True)

    async def mock_search(_settings, query, *, max_results, budget=None, redis=None):
        if query == "q1":
            return [
                WebSearchHit(title="A", url="https://dup", snippet="1"),
                WebSearchHit(title="B", url="https://b", snippet="2"),
            ]
        return [WebSearchHit(title="A dup", url="https://dup", snippet="3")]

    with patch("app.modules.web_search.search_cache._search_with_cache", side_effect=mock_search):
        merged, tried = await _run_search(settings, ["q1", "q2"])

    assert tried == ["q1", "q2"]
    assert len(merged) == 2
    assert merged[0].url == "https://dup"
    assert merged[1].url == "https://b"


@pytest.mark.asyncio
async def test_search_web_falls_back_to_duckduckgo():
    settings = Settings(mock_llm_enabled=False, tavily_api_key="", web_search_fallback_enabled=True)
    ddg_hit = WebSearchHit(title="DDG", url="https://news.example", snippet="story")
    with patch(
        "app.gateways.web_search_gateway._search_duckduckgo",
        AsyncMock(return_value=[ddg_hit]),
    ):
        hits = await search_web(settings, "top news today")
    assert hits[0].title == "DDG"


@pytest.mark.asyncio
async def test_search_web_returns_empty_when_all_providers_fail():
    settings = Settings(mock_llm_enabled=False, tavily_api_key="", web_search_fallback_enabled=True)
    with patch(
        "app.gateways.web_search_gateway._search_duckduckgo",
        AsyncMock(return_value=[]),
    ):
        hits = await search_web(settings, "test query")
    assert hits == []


@pytest.mark.asyncio
async def test_search_duckduckgo_timeout_returns_empty():
    """Stalled DDG must not hang the turn — wait_for returns []."""
    import asyncio

    from app.gateways import web_search_gateway as gw

    async def never_finishes(*_args: object, **_kwargs: object) -> list[WebSearchHit]:
        await asyncio.sleep(3600)
        return []

    with (
        patch.object(gw, "_DDG_TIMEOUT_SECONDS", 0.05),
        patch.object(gw.asyncio, "to_thread", side_effect=never_finishes),
    ):
        hits = await gw._search_duckduckgo("slow query", max_results=3)
    assert hits == []


@pytest.mark.asyncio
async def test_search_with_cache_reuses_redis(fake_redis):
    from app.modules.web_search.search_cache import _search_with_cache

    settings = Settings(web_search_cache_ttl=300, mock_llm_enabled=True)
    with patch("app.modules.web_search.search_cache.get_redis_client", return_value=fake_redis):
        first = await _search_with_cache(settings, "cached query", max_results=3)
        second = await _search_with_cache(settings, "cached query", max_results=3)
    assert len(first) >= 1
    assert second == first


@pytest.mark.asyncio
async def test_search_with_cache_honors_injected_redis():
    from app.modules.web_search.search_cache import _search_with_cache

    injected = AsyncMock()
    injected.get = AsyncMock(return_value=None)
    injected.set = AsyncMock(return_value=True)
    injected.delete = AsyncMock(return_value=1)

    settings = Settings(web_search_cache_ttl=300, mock_llm_enabled=True)
    hit = WebSearchHit(title="Hit", url="https://example.com", snippet="snippet")
    with (
        patch(
            "app.modules.web_search.search_cache.get_redis_client",
            side_effect=AssertionError("should use injected redis"),
        ),
        patch(
            "app.modules.web_search.search_cache.web_search_gateway.search_web",
            AsyncMock(return_value=[hit]),
        ),
    ):
        results = await _search_with_cache(
            settings,
            "injected query",
            max_results=3,
            redis=injected,
        )

    assert results == [hit]
    injected.get.assert_awaited()
    injected.set.assert_awaited()
    injected.delete.assert_awaited()


def test_search_cache_key_includes_max_results():
    from app.modules.web_search.search_cache import _search_cache_key

    assert _search_cache_key("Foo", 3) != _search_cache_key("Foo", 5)
    assert _search_cache_key("Foo", 3) == _search_cache_key("foo", 3)


def test_search_cache_key_includes_user_id():
    from app.modules.web_search.search_cache import _search_cache_key

    assert _search_cache_key("Foo", 3, user_id="a") != _search_cache_key("Foo", 3, user_id="b")
    assert _search_cache_key("Foo", 3) == _search_cache_key("Foo", 3, user_id="anon")


@pytest.mark.asyncio
async def test_search_with_cache_separate_entries_per_max_results(fake_redis):
    from app.modules.web_search.search_cache import _search_with_cache

    settings = Settings(web_search_cache_ttl=300, mock_llm_enabled=True)
    hit = WebSearchHit(title="Hit", url="https://example.com", snippet="snippet")
    search_mock = AsyncMock(return_value=[hit])
    with (
        patch("app.modules.web_search.search_cache.get_redis_client", return_value=fake_redis),
        patch("app.modules.web_search.search_cache.web_search_gateway.search_web", search_mock),
    ):
        await _search_with_cache(settings, "same query", max_results=1)
        await _search_with_cache(settings, "same query", max_results=5)

    assert search_mock.call_count == 2
    assert search_mock.call_args_list[0].kwargs["max_results"] == 1
    assert search_mock.call_args_list[1].kwargs["max_results"] == 5


@pytest.mark.asyncio
async def test_search_with_cache_single_flight_on_miss(fake_redis):
    import asyncio

    from app.modules.web_search.search_cache import _search_with_cache

    settings = Settings(web_search_cache_ttl=300, mock_llm_enabled=True)
    call_count = 0

    async def slow_search(_settings, _query, *, max_results=5, skip_tavily=False):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.25)
        return [
            WebSearchHit(title="Hit", url="https://example.com", snippet="snippet"),
        ]

    with (
        patch("app.modules.web_search.search_cache.get_redis_client", return_value=fake_redis),
        patch("app.modules.web_search.search_cache.web_search_gateway.search_web", slow_search),
    ):
        results = await asyncio.gather(
            *[_search_with_cache(settings, "same query", max_results=3) for _ in range(3)]
        )

    assert call_count == 1
    assert all(result == results[0] for result in results)
