"""A reply that says it can't see live data searches instead, and answers again.

"Perfect. totally unrelated but did the bears win today" was answered "I can't check live
scores" (live chat, 2026-10-25): the word rules read the line as a statement, so neither
the tool loop nor the reply's own call could search. Two rules that read the user's words
caught everyday statements ("went to the gym today but was too tired") in review. The
reply decides instead: the model never says it can't check live data about a statement.
When its first answer is such a denial, nothing was searched and search is on, the turn
searches the user's question (``search_queries_for_turn``) and the model answers again
from the results, in place of the denial.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import Settings
from app.modules.chat.clock_denial import model_denies_clock
from app.modules.chat.turn_prep import StreamContext
from app.modules.web_search import search_queries_for_turn
from app.services.text_normalize import collapse_ws, straighten_apostrophes

_MAX_LEN = 600
_LIVE = r"(?:live|real-time|realtime|current|up-to-date|today's|the\s+latest)"
_DENIAL = re.compile(
    r"\bi(?:\s+can't|\s+cannot|\s+can\s+not|'m\s+unable\s+to|\s+am\s+unable\s+to|"
    r"\s+don't\s+have\s+(?:a\s+way|the\s+ability)\s+to)\s+"
    rf"(?:check|access|look\s+up|see|get|pull\s+up|browse|confirm|track)\s+{_LIVE}\b"
    r"|\bi\s+(?:don't|do\s+not)\s+have\s+(?:access\s+to\s+)?"
    rf"{_LIVE}\s+(?:\w+\s+)?(?:data|information|info|results|scores|access|updates|news|stats)\b"
    r"|\bi\s+(?:can't|cannot)\s+browse\s+the\s+(?:web|internet)\b",
    re.IGNORECASE,
)
DENIAL_CALL_ID = "call_live_denial"


def denies_live_data(reply: str) -> bool:
    """A short reply that says it cannot see live data: "I can't check live scores"."""
    cleaned = straighten_apostrophes(collapse_ws(reply))
    return bool(cleaned) and len(cleaned) <= _MAX_LEN and _DENIAL.search(cleaned) is not None


async def search_instead(
    settings: Settings, ctx: StreamContext, reply: str
) -> dict[str, Any] | None:
    """The web_search call to run in place of a live-data denial, or None."""
    if not (
        settings.web_search_enabled
        and settings.mcp_tool_loop_enabled
        and settings.reply_search_tool_enabled
    ):
        return None
    asked = ctx.user_message_content or ""
    if ctx.search_sources or not denies_live_data(reply):
        return None
    # "What time is it" denied gets the clock (``finalize_text.fix_clock``), not a search.
    if model_denies_clock(reply, asked):
        return None
    queries = await search_queries_for_turn(
        settings,
        asked,
        ctx.prompt_messages,
        user_timezone=ctx.user_timezone,
        user_location=ctx.search_location,
    )
    if not queries:
        return None
    return {
        "id": DENIAL_CALL_ID,
        "type": "function",
        "function": {"name": "web_search", "arguments": json.dumps({"query": queries[0]})},
    }
