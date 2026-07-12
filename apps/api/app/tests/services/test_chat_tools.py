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
async def test_mcp_tools_math_uses_async_verified_block_not_sync():
    """BUG FIX (was silent): this call site used to invoke the synchronous
    _build_verified_block directly, bypassing the timeout + off-event-loop
    wrapper every other chat-path caller uses. Must call the async version."""
    settings = Settings(math_tools_enabled=True, mcp_tools_enabled=True)
    user_text = "differentiate x^2"
    messages = [{"role": "user", "content": user_text}]

    fake_block = MagicMock()
    fake_block.text = "verified: 2x"

    with (
        patch(
            "app.services.chat_tools.math_tools_service.needs_symbolic_math",
            return_value=True,
        ),
        patch(
            "app.services.chat_tools.math_tools_service.extract_math_intent",
            return_value=MagicMock(operation="diff", lhs="x^2", rhs=None, expr=None),
        ),
        patch(
            "app.services.chat_tools.math_tools_service._build_verified_block_async",
            AsyncMock(return_value=fake_block),
        ) as verified_async,
        patch(
            "app.services.chat_tools.math_tools_service._build_verified_block",
        ) as verified_sync,
    ):
        result = await chat_tools.augment_prompt_with_mcp_tools(messages, user_text, settings)

    verified_async.assert_awaited_once()
    verified_sync.assert_not_called()
    assert any("verified: 2x" in m["content"] for m in result)


@pytest.mark.asyncio
async def test_mcp_tools_math_fallback_uses_validated_invoke():
    """BUG FIX: this call site used mcp_registry.invoke (no Pydantic bounds
    checking) instead of invoke_validated, unlike the model-driven tool-loop
    path calling the same adapter — inconsistent validation for the same
    entry point."""
    settings = Settings(math_tools_enabled=True, mcp_tools_enabled=True)
    user_text = "differentiate x^2"
    messages = [{"role": "user", "content": user_text}]

    with (
        patch(
            "app.services.chat_tools.math_tools_service.needs_symbolic_math",
            return_value=True,
        ),
        patch(
            "app.services.chat_tools.math_tools_service.extract_math_intent",
            return_value=MagicMock(operation="diff", lhs="x^2", rhs=None, expr=None),
        ),
        patch(
            "app.services.chat_tools.math_tools_service._build_verified_block_async",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.chat_tools.mcp_registry.invoke_validated",
            AsyncMock(return_value=None),
        ) as invoke_validated,
        patch("app.services.chat_tools.mcp_registry.invoke", AsyncMock()) as invoke_unvalidated,
    ):
        await chat_tools.augment_prompt_with_mcp_tools(messages, user_text, settings)

    invoke_validated.assert_awaited_once()
    invoke_unvalidated.assert_not_awaited()


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
            AsyncMock(return_value=([{"role": "system", "content": "mcp"}], None)),
        ) as math_mock,
    ):
        updated, hits, verified_math = await _augment_web_and_tools(
            messages,
            "latest news?",
            settings,
        )

    web_mock.assert_awaited_once()
    mcp_mock.assert_awaited_once()
    math_mock.assert_awaited_once()
    assert updated == [{"role": "system", "content": "mcp"}]
    assert hits == [web_hit]
    assert verified_math is None
