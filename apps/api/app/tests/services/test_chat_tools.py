from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.chat import tools as chat_tools
from app.services.solving import VerifiedMathBlock
from app.services.subject_solving import SubjectAugmentation


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
    settings = Settings(mcp_tools_enabled=True, mcp_tool_loop_enabled=False)
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
            "app.services.chat.tools.augment_prompt_with_mcp_tools",
            AsyncMock(return_value=after_mcp),
        ) as mcp_mock,
        patch(
            "app.modules.web_search.build_search_augmentation",
            AsyncMock(return_value=("web", [web_hit])),
        ) as web_mock,
        patch(
            "app.services.chat.prompt_builder.build_subject_augmentation",
            AsyncMock(return_value=SubjectAugmentation(None, None, None)),
        ) as subject_mock,
    ):
        updated, hits, verified_math = await _augment_web_and_tools(
            messages,
            "latest news?",
            settings,
        )

    web_mock.assert_awaited_once()
    mcp_mock.assert_awaited_once()
    subject_mock.assert_awaited_once()
    assert updated == after_mcp
    assert hits == [web_hit]
    assert verified_math is None


@pytest.mark.asyncio
async def test_augment_web_and_tools_runs_web_and_subject_solver_concurrently():
    """Search and deterministic solving overlap, so TTFT pays the slower one."""
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

    async def slow_subject(*_a, **_k):
        await started.wait()
        overlap["web_saw_math_waiting"] = not released.is_set()
        released.set()
        return SubjectAugmentation("math", "math-block", None, unverified=True)

    with (
        patch("app.modules.web_search.build_search_augmentation", side_effect=slow_web),
        patch(
            "app.services.chat.prompt_builder.build_subject_augmentation",
            side_effect=slow_subject,
        ),
    ):
        updated, _hits, _verified = await _augment_web_and_tools(messages, "q", settings)

    assert overlap["web_saw_math_waiting"]
    assert [m["content"] for m in updated if m["role"] == "system"] == [
        "base",
        "web-block",
        "math-block",
    ]


@pytest.mark.asyncio
async def test_closed_math_does_not_run_web_search() -> None:
    from app.services.chat.prompt_builder import _augment_web_and_tools

    settings = Settings(
        mcp_tools_enabled=False,
        web_search_enabled=True,
        math_tools_enabled=True,
    )
    query = (
        "A class has mean score 72 and standard deviation 8. A student scored 88. "
        "What is the z-score? Then explain what it means, but do not assume "
        "the distribution is normal."
    )
    messages = [{"role": "user", "content": query}]
    with (
        patch(
            "app.modules.web_search.build_search_augmentation",
            AsyncMock(return_value=("unexpected web", [])),
        ) as web_mock,
        patch(
            "app.services.chat.prompt_builder.build_subject_augmentation",
            AsyncMock(
                return_value=SubjectAugmentation("math", "math", None, unverified=True)
            ),
        ),
    ):
        updated, hits, _verified = await _augment_web_and_tools(messages, query, settings)

    web_mock.assert_not_awaited()
    assert hits == []
    assert any(message.get("content") == "math" for message in updated)


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

    fake_block = VerifiedMathBlock(text="Verified (SymPy): d/dx(x^2) = 2x. Do NOT recompute.")

    with patch(
        "app.modules.math.tools._build_verified_block_async",
        AsyncMock(return_value=fake_block),
    ):
        updated, _hits, verified_math = await _augment_web_and_tools(
            messages,
            user_text,
            settings,
        )

    matches = [m for m in updated if fake_block.text in m.get("content", "")]
    assert len(matches) == 1
    assert verified_math is not None and verified_math.text == fake_block.text


def test_owned_tool_loop_defaults_on():
    assert Settings().mcp_tool_loop_enabled is True
    assert Settings().mcp_tools_enabled is False


@pytest.mark.asyncio
async def test_augment_web_and_tools_keeps_math_when_tool_loop_on():
    """Enabling the loop must not skip heuristic SymPy — homework cannot
    wait on the model choosing the sympy tool."""
    from app.services.chat.prompt_builder import _augment_web_and_tools

    settings = Settings(
        math_tools_enabled=True,
        mcp_tool_loop_enabled=True,
        web_search_enabled=False,
    )
    user_text = "differentiate x^2"
    messages = [{"role": "system", "content": "base"}, {"role": "user", "content": user_text}]
    fake_block = VerifiedMathBlock(text="Verified (SymPy): d/dx(x^2) = 2x. Do NOT recompute.")

    with patch(
        "app.modules.math.tools._build_verified_block_async",
        AsyncMock(return_value=fake_block),
    ):
        updated, _hits, verified_math = await _augment_web_and_tools(
            messages,
            user_text,
            settings,
        )

    matches = [m for m in updated if fake_block.text in m.get("content", "")]
    assert len(matches) == 1
    assert verified_math is not None and verified_math.text == fake_block.text
