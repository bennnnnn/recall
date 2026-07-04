from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.services import chat_tools


@pytest.mark.asyncio
async def test_mcp_tools_disabled_returns_unchanged():
    messages = [{"role": "user", "content": "hello"}]
    result = await chat_tools.augment_prompt_with_mcp_tools(
        messages,
        "hello",
        Settings(mcp_tools_enabled=False),
    )
    assert result == messages


@pytest.mark.asyncio
async def test_mcp_tools_calendar_create_hint():
    settings = Settings(mcp_tools_enabled=True)
    user_text = "Schedule a team sync tomorrow at 3pm"
    messages = [{"role": "user", "content": user_text}]
    result = await chat_tools.augment_prompt_with_mcp_tools(
        messages,
        user_text,
        settings,
        has_calendar_write=True,
    )
    assert len(result) == 2
    assert result[0]["role"] == "system"
    assert "calendar_proposal" in result[0]["content"]


@pytest.mark.asyncio
async def test_augment_web_and_tools_uses_mcp_when_enabled():
    from app.services.chat import _augment_web_and_tools

    settings = Settings(mcp_tools_enabled=True, web_search_enabled=True)
    messages = [{"role": "system", "content": "base"}, {"role": "user", "content": "latest news?"}]
    web_hit = MagicMock()
    web_hit.title = "News"
    web_hit.url = "https://news.example"
    web_hit.snippet = "story"

    with (
        patch(
            "app.services.chat.chat_tools_service.augment_prompt_with_mcp_tools",
            AsyncMock(return_value=[{"role": "system", "content": "mcp"}]),
        ) as mcp_mock,
        patch(
            "app.services.chat.web_search_service.augment_prompt_messages",
            AsyncMock(return_value=([{"role": "system", "content": "web"}], [web_hit])),
        ) as web_mock,
        patch(
            "app.services.chat.math_tools_service.augment_prompt_messages",
            AsyncMock(return_value=[{"role": "system", "content": "mcp"}]),
        ) as math_mock,
    ):
        updated, hits = await _augment_web_and_tools(
            messages,
            "latest news?",
            settings,
        )

    web_mock.assert_awaited_once()
    mcp_mock.assert_awaited_once()
    math_mock.assert_awaited_once()
    assert updated == [{"role": "system", "content": "mcp"}]
    assert hits == [web_hit]
