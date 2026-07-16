"""Model-initiated MCP tool rounds via LiteLLM ``tools=``.

When ``mcp_tool_loop_enabled`` is on, run bounded non-streaming tool rounds
before the user-visible stream. Pre-stream heuristic MCP / web-search
injection is skipped for those turns (see prompt_builder).

SymPy tool results that carry a ``canonical_fence`` in ``ToolResult.data`` are
collected so ``validate_math_fences`` can still overwrite/densify geometry and
graph fences the same way the heuristic math_tools path does.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.gateways.mcp import registry as mcp_registry
from app.services.chat.stream_status import StreamStatusFn, clip_status_detail
from app.services.math_tools import VerifiedMathBlock

logger = logging.getLogger(__name__)


def _status_for_tool(name: str) -> str:
    if name == "web_search":
        return "searching"
    if name == "sympy":
        return "calculating"
    return "thinking"


def _canonical_from_tool_result(result: Any) -> dict[str, Any] | None:
    data = getattr(result, "data", None)
    if not isinstance(data, dict):
        return None
    fence = data.get("canonical_fence")
    return fence if isinstance(fence, dict) else None


def _status_detail_for_tool(name: str, raw_args: str) -> str | None:
    """Surface the tool's subject (e.g. the search query) for the status label."""
    if name != "web_search":
        return None
    try:
        args = json.loads(raw_args)
    except (TypeError, ValueError):
        return None
    if not isinstance(args, dict):
        return None
    query = args.get("query")
    return clip_status_detail(query) if isinstance(query, str) else None


async def run_tool_rounds(
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, Any]],
    usage: dict[str, int],
    on_status: StreamStatusFn | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> tuple[list[dict[str, Any]], VerifiedMathBlock | None]:
    """Mutate a copy of *messages* through up to ``mcp_tool_loop_max_rounds`` tool rounds.

    Returns ``(messages, verified_math)``. ``verified_math`` is set when any
    sympy tool call returned a ``canonical_fence`` (last one wins) so post-stream
    fence validation matches the heuristic math_tools path.
    """
    if not settings.mcp_tool_loop_enabled:
        return messages, None

    tools = mcp_registry.build_openai_tools()
    if not tools:
        return messages, None

    working: list[dict[str, Any]] = [dict(m) for m in messages]
    max_rounds = max(1, settings.mcp_tool_loop_max_rounds)
    last_canonical: dict[str, Any] | None = None

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
                await on_status(_status_for_tool(name), _status_detail_for_tool(name, raw_args))
            result = await mcp_registry.invoke_validated(name, raw_args)
            content = result.content if result else f"Unknown tool: {name}"
            fence = _canonical_from_tool_result(result) if result else None
            if fence is not None:
                last_canonical = fence
            working.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": content,
                }
            )

    verified = (
        VerifiedMathBlock(text="", canonical_fence=last_canonical)
        if last_canonical is not None
        else None
    )
    return working, verified


def dump_tool_debug(messages: list[dict[str, Any]]) -> str:
    """Compact debug string for tests/logging."""
    return json.dumps(
        [{"role": m.get("role"), "keys": sorted(m.keys())} for m in messages],
        default=str,
    )
