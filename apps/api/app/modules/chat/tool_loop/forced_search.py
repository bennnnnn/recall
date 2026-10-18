"""The live search a turn needs when the model skipped ``web_search``."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.config import Settings
from app.gateways.mcp.base import ToolContext
from app.gateways.web_search_gateway import WebSearchHit
from app.modules.chat.stream_status import StreamStatusFn, clip_status_detail
from app.modules.chat.tool_loop.selection import _last_user_content
from app.modules.web_search import (
    format_search_block,
    format_search_empty_block,
    run_cached_search,
    search_queries_for_turn,
)


def _web_search_was_called(messages: list[dict[str, Any]]) -> bool:
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        for call in msg.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            name = str((call.get("function") or {}).get("name") or "")
            if name == "web_search":
                return True
    return False


async def _force_web_search_if_needed(
    *,
    settings: Settings,
    messages: list[dict[str, Any]],
    search_hits: list[WebSearchHit],
    ctx: ToolContext,
    on_status: StreamStatusFn | None,
    should_cancel: Callable[[], bool] | None,
    search_required: bool = False,
) -> tuple[list[dict[str, Any]], list[WebSearchHit]]:
    """If the model skipped web_search on a turn that needs live results, search once.

    ``search_required`` preserves a classifier-yes decision. The sync heuristic
    alone would otherwise drop that turn (silent answer from training data).
    Empty hits still inject a no-results block so the model cannot look current.
    """
    if search_hits:
        return messages, search_hits
    if should_cancel and should_cancel():
        return messages, search_hits
    if not settings.web_search_enabled:
        return messages, search_hits
    user_text = _last_user_content(messages)
    if not user_text:
        return messages, search_hits
    from app.modules.web_search.detection import needs_web_search
    from app.services.prompt_inject import inject_before_last_user
    from app.services.prompt_safety import wrap_untrusted

    already_searched = _web_search_was_called(messages)
    if not search_required and not already_searched and not needs_web_search(user_text):
        return messages, search_hits

    tried = [user_text]
    if not already_searched:
        # Show the search before reading the chat for a follow-up's topic.
        if on_status is not None:
            await on_status("searching", None)
        # "do a search" / "when did she die?" search for what the chat was
        # about, not for the words of the request.
        queries = await search_queries_for_turn(
            settings,
            user_text,
            messages,
            user_timezone=ctx.user_timezone,
            user_location=ctx.user_location,
        )
        if on_status is not None:
            await on_status("searching", clip_status_detail(queries[0] if queries else user_text))
        hits, tried = await run_cached_search(
            settings,
            queries or [user_text],
            user=ctx.user,
            redis=ctx.redis,
            budget=ctx.tavily_budget,
        )
        if hits:
            block = wrap_untrusted("web search", format_search_block(hits))
            return inject_before_last_user(messages, block), hits

    empty = format_search_empty_block(tried or [user_text])
    return inject_before_last_user(messages, empty), search_hits
