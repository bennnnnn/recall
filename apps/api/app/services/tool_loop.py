"""Model-initiated MCP tool rounds via LiteLLM ``tools=``.

When ``mcp_tool_loop_enabled`` is on, run bounded non-streaming tool rounds
before the user-visible stream. Pre-stream heuristic MCP / web-search
injection is skipped for those turns (see prompt_builder).

SymPy tool results that carry a ``canonical_fence`` in ``ToolResult.data`` are
collected so ``validate_math_fences`` can still overwrite/densify geometry and
graph fences the same way the heuristic math_tools path does.

``generate_image`` is terminal: on success the stream skips the visible LLM
pass and uses the already-persisted ``[Image: …]`` assistant row.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.gateways.mcp import registry as mcp_registry
from app.gateways.mcp.image_gen_adapter import bind_image_gen_context
from app.gateways.mcp.web_search_adapter import bind_search_quota_context
from app.models.orm import User
from app.services import plan as plan_service
from app.services.chat.stream_status import StreamStatusFn, clip_status_detail
from app.services.math_tools import VerifiedMathBlock

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TerminalImageResult:
    """Successful model-initiated image gen — stream must not create another row."""

    message_id: str
    final_content: str
    resolved_model: str


def _status_for_tool(name: str) -> str:
    if name == "web_search":
        return "searching"
    if name == "sympy":
        return "calculating"
    if name == "generate_image":
        return "image_gen"
    return "thinking"


def _canonical_from_tool_result(result: Any) -> dict[str, Any] | None:
    data = getattr(result, "data", None)
    if not isinstance(data, dict):
        return None
    fence = data.get("canonical_fence")
    return fence if isinstance(fence, dict) else None


def _terminal_image_from_tool_result(result: Any) -> TerminalImageResult | None:
    data = getattr(result, "data", None)
    if not isinstance(data, dict) or not data.get("terminal"):
        return None
    marker = data.get("image_marker")
    message_id = data.get("assistant_message_id")
    if not isinstance(marker, str) or not marker.startswith("[Image:"):
        return None
    if not isinstance(message_id, str) or not message_id.strip():
        return None
    model = data.get("resolved_model")
    resolved = model if isinstance(model, str) and model.strip() else "image-gen-model"
    return TerminalImageResult(
        message_id=message_id.strip(),
        final_content=marker.strip(),
        resolved_model=resolved,
    )


def _status_detail_for_tool(name: str, raw_args: str) -> str | None:
    """Surface the tool's subject (e.g. the search query) for the status label."""
    if name == "web_search":
        key = "query"
    elif name == "generate_image":
        key = "prompt"
    else:
        return None
    try:
        args = json.loads(raw_args)
    except (TypeError, ValueError):
        return None
    if not isinstance(args, dict):
        return None
    value = args.get(key)
    return clip_status_detail(value) if isinstance(value, str) else None


def _tools_for_user(settings: Settings, user: User | None) -> list[dict[str, Any]]:
    """OpenAI tool payloads; omit image gen for free users / when disabled."""
    tools = mcp_registry.build_openai_tools()
    if settings.image_generation_enabled and user is not None and plan_service.is_pro(user):
        return tools
    return [t for t in tools if (t.get("function") or {}).get("name") != "generate_image"]


async def run_tool_rounds(
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, Any]],
    usage: dict[str, int],
    on_status: StreamStatusFn | None = None,
    should_cancel: Callable[[], bool] | None = None,
    user: User | None = None,
    redis: Redis | None = None,
    chat_id: UUID | None = None,
) -> tuple[list[dict[str, Any]], VerifiedMathBlock | None, TerminalImageResult | None]:
    """Mutate a copy of *messages* through up to ``mcp_tool_loop_max_rounds`` tool rounds.

    Returns ``(messages, verified_math, terminal_image)``.
    """
    if not settings.mcp_tool_loop_enabled:
        return messages, None, None

    tools = _tools_for_user(settings, user)
    if not tools:
        return messages, None, None

    with (
        bind_search_quota_context(user=user, redis=redis),
        bind_image_gen_context(user=user, redis=redis, chat_id=chat_id),
    ):
        return await _run_tool_rounds_bound(
            settings=settings,
            model_alias=model_alias,
            messages=messages,
            usage=usage,
            tools=tools,
            on_status=on_status,
            should_cancel=should_cancel,
        )


async def _run_tool_rounds_bound(
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, Any]],
    usage: dict[str, int],
    tools: list[dict[str, Any]],
    on_status: StreamStatusFn | None,
    should_cancel: Callable[[], bool] | None,
) -> tuple[list[dict[str, Any]], VerifiedMathBlock | None, TerminalImageResult | None]:
    working: list[dict[str, Any]] = [dict(m) for m in messages]
    max_rounds = max(1, settings.mcp_tool_loop_max_rounds)
    last_canonical: dict[str, Any] | None = None
    terminal_image: TerminalImageResult | None = None

    for _ in range(max_rounds):
        if should_cancel and should_cancel():
            break
        try:
            msg = await litellm_gateway.complete_with_tools(
                settings=settings,
                model_alias=model_alias,
                messages=working,
                tools=tools,
                max_tokens=settings.max_output_tokens,
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
            image = _terminal_image_from_tool_result(result) if result else None
            if image is not None:
                terminal_image = image
            working.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": content,
                }
            )

        # Image gen already persisted the assistant row — stop before another
        # completion round invents prose around the marker.
        if terminal_image is not None:
            break

    # A cancel can land after the assistant's tool_calls are recorded but before
    # every tool result is appended. Providers reject a message list where a
    # tool_calls turn isn't fully answered, so truncate back to the last valid
    # (fully-answered) prefix before handing off to the visible stream.
    cut = _first_unanswered_assistant_idx(working)
    if cut is not None:
        logger.info("Tool loop cancelled mid-round; trimming unanswered tool_calls turn")
        working = working[:cut]

    verified = (
        VerifiedMathBlock(text="", canonical_fence=last_canonical)
        if last_canonical is not None
        else None
    )
    return working, verified, terminal_image


def _first_unanswered_assistant_idx(msgs: list[dict[str, Any]]) -> int | None:
    """Index of the newest assistant tool_calls turn missing a tool reply, else None."""
    for i in range(len(msgs) - 1, -1, -1):
        m = msgs[i]
        if m.get("role") != "assistant" or not m.get("tool_calls"):
            continue
        answered = {t.get("tool_call_id") for t in msgs[i + 1 :] if t.get("role") == "tool"}
        needed = {str(c.get("id") or "") for c in m["tool_calls"]}
        needed.discard("")
        if not needed.issubset(answered):
            return i
    return None


def dump_tool_debug(messages: list[dict[str, Any]]) -> str:
    """Compact debug string for tests/logging."""
    return json.dumps(
        [{"role": m.get("role"), "keys": sorted(m.keys())} for m in messages],
        default=str,
    )
