"""Model-initiated MCP tool rounds via LiteLLM ``tools=``.

When ``mcp_tool_loop_enabled`` is on, run bounded non-streaming tool rounds
before the user-visible stream. Pre-stream heuristic MCP / web-search
injection is skipped for those turns (see prompt_builder).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.gateways.mcp import registry as mcp_registry

logger = logging.getLogger(__name__)

StreamStatusFn = Callable[[str], Awaitable[None]]


def _status_for_tool(name: str) -> str:
    if name == "web_search":
        return "searching"
    if name == "sympy":
        return "calculating"
    return "thinking"


async def run_tool_rounds(
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, Any]],
    usage: dict[str, int],
    on_status: StreamStatusFn | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> list[dict[str, Any]]:
    """Mutate a copy of *messages* through up to ``mcp_tool_loop_max_rounds`` tool rounds."""
    if not settings.mcp_tool_loop_enabled:
        return messages

    tools = mcp_registry.build_openai_tools()
    if not tools:
        return messages

    working: list[dict[str, Any]] = [dict(m) for m in messages]
    max_rounds = max(1, settings.mcp_tool_loop_max_rounds)

    for _ in range(max_rounds):
        if should_cancel and should_cancel():
            break
        try:
            msg = await litellm_gateway.complete_with_tools(
                settings=settings,
                model_alias=model_alias,
                messages=working,
                tools=tools,
                usage=usage,
                timeout_seconds=settings.mcp_tool_loop_timeout_seconds,
            )
        except Exception:
            logger.exception("Tool-loop completion failed; falling through to stream")
            break

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            # Model produced a final answer without tools — keep any content
            # out of the stream path (stream will regenerate). Drop assistant
            # content here so we don't double-answer.
            break

        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": msg.get("content") or None,
            "tool_calls": tool_calls,
        }
        working.append(assistant_msg)

        for call in tool_calls:
            if should_cancel and should_cancel():
                break
            fn = call.get("function") or {}
            name = str(fn.get("name") or "")
            raw_args = fn.get("arguments") or "{}"
            call_id = str(call.get("id") or name)
            if on_status is not None and name:
                await on_status(_status_for_tool(name))
            result = await mcp_registry.invoke_validated(name, raw_args)
            content = result.content if result else f"Unknown tool: {name}"
            working.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": content,
                }
            )

    return working


def dump_tool_debug(messages: list[dict[str, Any]]) -> str:
    """Compact debug string for tests/logging."""
    return json.dumps(
        [{"role": m.get("role"), "keys": sorted(m.keys())} for m in messages],
        default=str,
    )
