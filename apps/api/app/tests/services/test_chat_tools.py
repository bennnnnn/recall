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
async def test_mcp_tools_does_not_handle_math_itself():
    """BUG FIX (duplicate verified-block injection): this function used to
    also build and inject its own verified-math block for math-intent turns.
    But math_tools_service.build_math_augmentation — the single owner of math
    augmentation — is gathered/injected in the only production call site
    (_augment_web_and_tools), so a math-intent turn got
    the same "verified, do NOT recompute" block injected twice whenever
    mcp_tools_enabled=True and mcp_tool_loop_enabled=False. This function must
    not touch math intent at all; see test_augment_web_and_tools_injects_math_block_only_once
    for the end-to-end no-duplicate assertion."""
    settings = Settings(math_tools_enabled=True, mcp_tools_enabled=True)
    user_text = "differentiate x^2"
    messages = [{"role": "user", "content": user_text}]

    result = await chat_tools.augment_prompt_with_mcp_tools(messages, user_text, settings)

    assert result == messages


@pytest.mark.asyncio
async def test_augment_web_and_tools_uses_mcp_when_enabled():
    from app.services.chat.prompt_builder import _augment_web_and_tools

    settings = Settings(mcp_tools_enabled=True, web_search_enabled=True)
    messages = [{"role": "system", "content": "base"}, {"role": "user", "content": "latest news?"}]
    web_hit = MagicMock()
    web_hit.title = "News"
    web_hit.url = "https://news.example"
    web_hit.snippet = "story"
    after_mcp = [
        {"role": "system", "content": "base"},
        {"role": "system", "content": "web"},
        {"role": "system", "content": "mcp"},
        {"role": "user", "content": "latest news?"},
    ]

    with (
        patch(
            "app.services.chat_tools.augment_prompt_with_mcp_tools",
            AsyncMock(return_value=after_mcp),
        ) as mcp_mock,
        patch(
            "app.services.web_search.build_search_augmentation",
            AsyncMock(return_value=("web", [web_hit])),
        ) as web_mock,
        patch(
            "app.services.math_tools.build_math_augmentation",
            AsyncMock(return_value=(None, None)),
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
    assert updated == after_mcp
    assert hits == [web_hit]
    assert verified_math is None


@pytest.mark.asyncio
async def test_augment_web_and_tools_runs_web_and_math_concurrently():
    """Web search and SymPy must overlap — TTFT pays max(search, math), not sum."""
    import asyncio

    from app.services.chat.prompt_builder import _augment_web_and_tools

    settings = Settings(
        mcp_tools_enabled=False,
        web_search_enabled=True,
        math_tools_enabled=True,
    )
    messages = [{"role": "system", "content": "base"}, {"role": "user", "content": "q"}]
    started = asyncio.Event()
    released = asyncio.Event()
    overlap = {"web_saw_math_waiting": False}

    async def slow_web(*_a, **_k):
        started.set()
        await released.wait()
        return "web-block", []

    async def slow_math(*_a, **_k):
        await started.wait()
        overlap["web_saw_math_waiting"] = not released.is_set()
        released.set()
        return "math-block", None

    with (
        patch("app.services.web_search.build_search_augmentation", side_effect=slow_web),
        patch("app.services.math_tools.build_math_augmentation", side_effect=slow_math),
    ):
        updated, _hits, _verified = await _augment_web_and_tools(messages, "q", settings)

    assert overlap["web_saw_math_waiting"]
    assert [m["content"] for m in updated if m["role"] == "system"] == [
        "base",
        "web-block",
        "math-block",
    ]


@pytest.mark.asyncio
async def test_augment_web_and_tools_injects_math_block_only_once():
    """End-to-end regression for the duplicate verified-block injection bug:
    with mcp_tools_enabled=True and mcp_tool_loop_enabled=False (the exact
    flag combination that used to trigger it), a math-intent turn must get
    exactly one verified-math system message, not two."""
    from app.services.chat.prompt_builder import _augment_web_and_tools

    settings = Settings(
        math_tools_enabled=True,
        mcp_tools_enabled=True,
        mcp_tool_loop_enabled=False,
        web_search_enabled=False,
    )
    user_text = "differentiate x^2"
    messages = [{"role": "system", "content": "base"}, {"role": "user", "content": user_text}]

    fake_block = MagicMock()
    fake_block.text = "Verified (SymPy): d/dx(x^2) = 2x. Do NOT recompute."

    with patch(
        "app.services.math_tools._build_verified_block_async",
        AsyncMock(return_value=fake_block),
    ):
        updated, _hits, verified_math = await _augment_web_and_tools(
            messages,
            user_text,
            settings,
        )

    matches = [m for m in updated if fake_block.text in m.get("content", "")]
    assert len(matches) == 1
    assert verified_math is fake_block
