"""Web search (Tavily, then DuckDuckGo) and reference-photo lookup."""

from pydantic import BaseModel


class SearchSettings(BaseModel):
    tavily_api_key: str = ""

    web_search_enabled: bool = True
    # The reply's own model call carries the web_search tool (``tool_loop.reply_calls``):
    # the model decides whether to search. A reply that needs none costs nothing.
    reply_search_tool_enabled: bool = True
    # A fast model reads each message beside the turn's prep and says whether its answer
    # depends on facts that change (``web_search.live_read``): yes, and its query is
    # searched before the reply. Off, or no answer in time, and the reply's model decides.
    live_read_enabled: bool = True
    live_read_timeout_seconds: float = 2.0
    # How long the reply waits for a read still running when the prep is done (it starts
    # when the turn loads, so most are in by then).
    live_read_wait_seconds: float = 1.2
    # Reading what "search that" or "show me one" refers to in the conversation (one
    # small model call before the search). Foreground: kept short, no retry.
    reference_resolve_timeout_seconds: float = 4.0
    web_search_fallback_enabled: bool = True
    web_search_max_results: int = 5
    web_search_cache_ttl: int = 300

    # Real reference-photo lookup ("show me an ear" / "what does X look like")
    # — separate from AI generation. Reuses Tavily (image_search_enabled also
    # requires tavily_api_key, same as web_search). Available to free users
    # (lower cap) since it costs one Tavily query + one image fetch, not a
    # 120s image-gen provider call.
    image_search_enabled: bool = True
    image_search_max_results: int = 3
    image_search_fetch_timeout_seconds: float = 8.0
