"""Live web search routing, query building, and prompt injection."""

from app.modules.web_search.augment import augment_prompt_messages, build_search_augmentation
from app.modules.web_search.detection import (
    needs_web_search,
    needs_web_search_heuristic,
    should_web_search,
    web_search_fast_yes,
    web_search_skip,
)
from app.modules.web_search.formatting import (
    AMBIGUOUS_NEARBY_HINT,
    GEO_ACTIVE_LOCATION_HINT,
    GEO_DISTANCE_HINT,
    LOCAL_PLACES_FORMAT_HINT,
    WEB_SEARCH_HINT,
    format_places_fence,
    format_search_block,
    format_search_empty_block,
    format_sources_fence,
    places_payload_from_hits,
    sources_payload,
    strip_duplicate_venue_list,
    strip_sources_from_text,
)
from app.modules.web_search.geo_intent import (
    format_location_not_set_answer,
    is_ambiguous_local_places_query,
    is_distance_query,
    is_geo_query,
    is_local_places_query,
    is_places_list_query,
    is_proximity_query,
    is_vocab_quiz_answer,
)
from app.modules.web_search.query_builders import build_search_queries, build_search_query
from app.modules.web_search.search_cache import run_cached_search
from app.modules.web_search.subject import resolve_search_subject
from app.modules.web_search.tool import WebSearchAdapter, bind_search_quota_context

__all__ = [
    "AMBIGUOUS_NEARBY_HINT",
    "GEO_ACTIVE_LOCATION_HINT",
    "GEO_DISTANCE_HINT",
    "LOCAL_PLACES_FORMAT_HINT",
    "WEB_SEARCH_HINT",
    "WebSearchAdapter",
    "augment_prompt_messages",
    "bind_search_quota_context",
    "build_search_augmentation",
    "build_search_queries",
    "build_search_query",
    "format_location_not_set_answer",
    "format_places_fence",
    "format_search_block",
    "format_search_empty_block",
    "format_sources_fence",
    "is_ambiguous_local_places_query",
    "is_distance_query",
    "is_geo_query",
    "is_local_places_query",
    "is_places_list_query",
    "is_proximity_query",
    "is_vocab_quiz_answer",
    "needs_web_search",
    "needs_web_search_heuristic",
    "places_payload_from_hits",
    "resolve_search_subject",
    "run_cached_search",
    "should_web_search",
    "sources_payload",
    "strip_duplicate_venue_list",
    "strip_sources_from_text",
    "web_search_fast_yes",
    "web_search_skip",
]
