from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.services.solving import VerifiedMathBlock
from app.services.subject_solving import SubjectAugmentation


@pytest.mark.asyncio
async def test_augment_web_and_tools_runs_web_and_subject_solver_concurrently():
    """Search and deterministic solving overlap, so TTFT pays the slower one."""
    import asyncio

    from app.tests.modules.chat.chat_test_support import augment_web_and_tools

    settings = Settings(
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
            "app.modules.chat.prompt_builder.build_subject_augmentation",
            side_effect=slow_subject,
        ),
    ):
        updated, _hits, _verified = await augment_web_and_tools(messages, "q", settings)

    assert overlap["web_saw_math_waiting"]
    assert [m["content"] for m in updated if m["role"] == "system"] == [
        "base",
        "web-block",
        "math-block",
    ]


@pytest.mark.asyncio
async def test_closed_math_does_not_run_web_search() -> None:
    from app.tests.modules.chat.chat_test_support import augment_web_and_tools

    settings = Settings(
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
            "app.modules.chat.prompt_builder.build_subject_augmentation",
            AsyncMock(return_value=SubjectAugmentation("math", "math", None, unverified=True)),
        ),
    ):
        updated, hits, _verified = await augment_web_and_tools(messages, query, settings)

    web_mock.assert_not_awaited()
    assert hits == []
    assert any(message.get("content") == "math" for message in updated)


@pytest.mark.asyncio
async def test_augment_web_and_tools_injects_math_block_only_once():
    """End-to-end regression for the duplicate verified-block injection bug:
    with the tool loop off, a math-intent turn must get exactly one
    verified-math system message, not two."""
    from app.tests.modules.chat.chat_test_support import augment_web_and_tools

    settings = Settings(
        math_tools_enabled=True,
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
        updated, _hits, verified_math = await augment_web_and_tools(
            messages,
            user_text,
            settings,
        )

    matches = [m for m in updated if fake_block.text in m.get("content", "")]
    assert len(matches) == 1
    assert verified_math is not None and verified_math.text == fake_block.text


def test_owned_tool_loop_defaults_on():
    assert Settings().mcp_tool_loop_enabled is True


@pytest.mark.asyncio
async def test_augment_web_and_tools_keeps_math_when_tool_loop_on():
    """Enabling the loop must not skip heuristic SymPy — homework cannot
    wait on the model choosing the sympy tool."""
    from app.tests.modules.chat.chat_test_support import augment_web_and_tools

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
        updated, _hits, verified_math = await augment_web_and_tools(
            messages,
            user_text,
            settings,
        )

    matches = [m for m in updated if fake_block.text in m.get("content", "")]
    assert len(matches) == 1
    assert verified_math is not None and verified_math.text == fake_block.text
