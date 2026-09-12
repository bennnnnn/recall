from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.services import tool_loop


@pytest.mark.asyncio
@pytest.mark.parametrize("budget", [0, 300])
async def test_tool_selection_uses_own_budget_and_preserves_visible_cap(budget):
    settings = Settings(mcp_tool_loop_probe_max_tokens=budget, max_output_tokens=8192)
    complete = AsyncMock(return_value={"content": None, "tool_calls": [], "finish_reason": "stop"})
    with patch.object(tool_loop.litellm_gateway, "complete_with_tools", complete):
        await tool_loop._run_tool_rounds_bound(
            settings=settings,
            model_alias="smart-chat",
            messages=[{"role": "user", "content": "Solve this"}],
            usage={},
            tools=[],
            on_status=None,
            should_cancel=None,
        )
    assert complete.await_args.kwargs["max_tokens"] == max(1, budget)
    assert complete.await_args.kwargs["model_alias"] == "free-chat"
    assert settings.max_output_tokens == 8192


@pytest.mark.asyncio
async def test_truncated_complete_json_never_invokes_a_tool():
    call = {
        "id": "calendar_1",
        "type": "function",
        "function": {"name": "calendar", "arguments": '{"action":"create"}'},
    }
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="length",
                message=SimpleNamespace(content="I have created it", tool_calls=[call]),
            )
        ],
        usage=SimpleNamespace(prompt_tokens=50, completion_tokens=1024),
    )
    usage = {}
    messages = [{"role": "user", "content": "Create an event"}]
    invoke = AsyncMock()
    with (
        patch.object(tool_loop.litellm_gateway, "acompletion", AsyncMock(return_value=response)),
        patch.object(tool_loop.mcp_registry, "invoke_validated", invoke),
    ):
        out, verified, terminal, hits = await tool_loop._run_tool_rounds_bound(
            settings=Settings(mock_llm_enabled=False, openrouter_api_key="test-only"),
            model_alias="free-chat",
            messages=messages,
            usage=usage,
            tools=[{"type": "function", "function": {"name": "calendar"}}],
            on_status=None,
            should_cancel=None,
        )
    invoke.assert_not_awaited()
    assert out == [*messages, tool_loop._tool_selection_unavailable_message()]
    assert usage == {"input": 50, "output": 1024}
    assert verified is terminal is None
    assert hits == []


@pytest.mark.asyncio
async def test_cancel_after_selection_prevents_invocation_and_failure_context():
    stopped = False

    async def complete(**kwargs):
        nonlocal stopped
        stopped = True
        return {"tool_calls": [{"id": "c", "function": {"name": "calendar"}}]}

    messages = [{"role": "user", "content": "Create an event"}]
    invoke = AsyncMock()
    with (
        patch.object(tool_loop.litellm_gateway, "complete_with_tools", complete),
        patch.object(tool_loop.mcp_registry, "invoke_validated", invoke),
    ):
        out, *_ = await tool_loop._run_tool_rounds_bound(
            settings=Settings(),
            model_alias="free-chat",
            messages=messages,
            usage={},
            tools=[],
            on_status=None,
            should_cancel=lambda: stopped,
        )
    invoke.assert_not_awaited()
    assert out == messages
