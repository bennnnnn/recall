"""Optional MCP tool round before streaming (guarded by mcp_tools_enabled)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from app.core.config import Settings
from app.gateways.mcp import registry as mcp_registry
from app.services import calendar as calendar_service
from app.services import math_tools as math_tools_service

logger = logging.getLogger(__name__)


def _inject_before_last_user(messages: list[dict[str, str]], block: str) -> list[dict[str, str]]:
    augmented = list(messages)
    insert_at = len(augmented)
    for index in range(len(augmented) - 1, -1, -1):
        if augmented[index].get("role") == "user":
            insert_at = index
            break
    augmented.insert(insert_at, {"role": "system", "content": block})
    return augmented


async def augment_prompt_with_mcp_tools(
    messages: list[dict[str, str]],
    user_content: str,
    settings: Settings,
    *,
    user_timezone: str | None = None,
    user_location: str | None = None,
    prior_user_messages: list[str] | None = None,
    on_status: Callable[[str], Awaitable[None]] | None = None,
    has_calendar_write: bool = False,
) -> list[dict[str, str]]:
    """Run registered MCP adapters when heuristics match (single pre-stream round)."""
    if not settings.mcp_tools_enabled:
        return messages

    blocks: list[str] = []

    if has_calendar_write and calendar_service.is_calendar_create_request(user_content):
        blocks.append(calendar_service.CALENDAR_WRITE_HINT)

    if settings.math_tools_enabled and math_tools_service.needs_symbolic_math(user_content):
        intent = math_tools_service.extract_math_intent(user_content)
        if intent is not None:
            verified = math_tools_service._build_verified_block(intent, settings)
            if verified:
                blocks.append(verified.text)
            else:
                if on_status is not None:
                    await on_status("calculating")
                result = await mcp_registry.invoke(
                    "sympy",
                    {
                        "action": intent.operation or "solve",
                        "lhs": intent.lhs,
                        "rhs": intent.rhs,
                        "expr": intent.expr,
                        "text": user_content,
                    },
                )
                if result and result.content.strip():
                    blocks.append(
                        "Symbolic math results (from MCP sympy tool — use for your answer):\n"
                        f"{result.content}"
                    )

    if not blocks:
        return messages

    return _inject_before_last_user(messages, "\n\n".join(blocks))
