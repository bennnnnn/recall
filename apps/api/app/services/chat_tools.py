"""Optional MCP tool round before streaming (guarded by mcp_tools_enabled)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from app.core.config import Settings
from app.services import calendar as calendar_service
from app.services.prompt_inject import inject_before_last_user

logger = logging.getLogger(__name__)


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
    if not settings.mcp_tools_enabled or settings.mcp_tool_loop_enabled:
        return messages

    blocks: list[str] = []

    if has_calendar_write and calendar_service.is_calendar_create_request(user_content):
        blocks.append(calendar_service.CALENDAR_WRITE_HINT)

    # Math intent is NOT handled here. math_tools_service.augment_prompt_messages
    # is the single owner of math augmentation — it always runs right after this
    # function returns, in the only production call site (_augment_web_and_tools).
    # This function used to also build and inject its own verified-math block,
    # so a math-intent turn got the same "verified, do NOT recompute" block
    # injected twice whenever mcp_tools_enabled=True and mcp_tool_loop_enabled=
    # False.

    if not blocks:
        return messages

    return inject_before_last_user(messages, "\n\n".join(blocks))
