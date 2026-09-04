import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import fakeredis.aioredis
import pytest

from app.core.config import Settings
from app.gateways.mcp.base import ToolResult
from app.services.live_talk_tools import execute_tool, search_sources_for_turn


@pytest.mark.asyncio
async def test_voice_search_reserves_once_for_duplicate_tool_calls_and_keeps_sources():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    user = SimpleNamespace(id=uuid4(), memory_enabled=True)
    sources = [{"title": "Official score", "url": "https://example.com/score"}]
    invoke = AsyncMock(
        return_value=ToolResult(name="web_search", content="Score 2-1", data={"hits": sources})
    )
    with patch("app.services.live_talk_tools.WebSearchAdapter.invoke", invoke):
        args = dict(
            user=user, call_id="call", turn_id="turn", name="web_search", query="latest score"
        )
        await asyncio.gather(
            execute_tool(Settings(), redis, **args), execute_tool(Settings(), redis, **args)
        )
        cached = await execute_tool(Settings(), redis, **args)
    assert invoke.await_count == 1
    assert cached["sources"] == sources
    assert await search_sources_for_turn(redis, user.id, "call", "turn") == sources


@pytest.mark.asyncio
async def test_memory_disabled_does_not_call_memory_service():
    user = SimpleNamespace(id=uuid4(), memory_enabled=False)
    with patch(
        "app.services.live_talk_tools.memory_service.get_memory_block", AsyncMock()
    ) as memory:
        result = await execute_tool(
            Settings(),
            fakeredis.aioredis.FakeRedis(),
            user=user,
            call_id="call",
            turn_id="turn",
            name="memory_lookup",
            query="my diet",
        )
    assert "disabled" in result["content"]
    memory.assert_not_awaited()


@pytest.mark.asyncio
async def test_tools_fail_closed_if_reservation_store_is_down():
    redis = AsyncMock()
    redis.get.side_effect = RuntimeError("offline")
    with patch("app.services.live_talk_tools.WebSearchAdapter.invoke", AsyncMock()) as search:
        result = await execute_tool(
            Settings(),
            redis,
            user=SimpleNamespace(id=uuid4()),
            call_id="call",
            turn_id="turn",
            name="web_search",
            query="latest score",
        )
    assert "unavailable" in result["content"]
    search.assert_not_awaited()
