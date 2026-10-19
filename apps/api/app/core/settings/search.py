"""Web search (Tavily, then DuckDuckGo) and reference-photo lookup."""

from pydantic import BaseModel


class SearchSettings(BaseModel):
    tavily_api_key: str = ""

    web_search_enabled: bool = True
    web_search_classifier_enabled: bool = True
    # Foreground TTFT path — keep this short; no model-fallback retry on timeout.
    web_search_classifier_timeout_seconds: float = 4.0
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
