"""Live web search: the ``web_search`` tool the model calls, its sources and their fences.

Whether a turn searches is the model's call (``chat.tool_loop.reply_calls``). The package
stays lazy: the SymPy pool's workers read a message with ``geo_intent`` and must not load
the search cache, which brings the ORM and the database with it.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.modules.web_search.formatting import (
        AMBIGUOUS_NEARBY_HINT,
        DIRECTIONS_LINK_RULE,
        GEO_ACTIVE_LOCATION_HINT,
        GEO_DISTANCE_HINT,
        WEB_SEARCH_HINT,
        SearchSource,
        format_search_block,
        format_search_empty_block,
        format_sources_fence,
        sources_payload,
        strip_sources_from_text,
    )
    from app.modules.web_search.geo_intent import (
        LOCATION_ASK_OPENING,
        format_location_not_set_answer,
        is_ambiguous_local_places_query,
        is_distance_query,
        is_geo_query,
        names_its_place,
    )
    from app.modules.web_search.homework import asks_about_a_place
    from app.modules.web_search.recency import wants_dated_results
    from app.modules.web_search.search_cache import (
        SideSearchBudget,
        TurnTavilyBudget,
        run_cached_search,
        side_search_budget,
        turn_search_budget,
    )
    from app.modules.web_search.source_credits import drop_source_credits
    from app.modules.web_search.tool import WebSearchAdapter
    from app.modules.web_search.turn_query import points_back_in_chat

_EXPORTS = {
    "AMBIGUOUS_NEARBY_HINT": "formatting",
    "DIRECTIONS_LINK_RULE": "formatting",
    "GEO_ACTIVE_LOCATION_HINT": "formatting",
    "GEO_DISTANCE_HINT": "formatting",
    "SearchSource": "formatting",
    "TurnTavilyBudget": "search_cache",
    "WEB_SEARCH_HINT": "formatting",
    "WebSearchAdapter": "tool",
    "asks_about_a_place": "homework",
    "drop_source_credits": "source_credits",
    "format_location_not_set_answer": "geo_intent",
    "LOCATION_ASK_OPENING": "geo_intent",
    "format_search_block": "formatting",
    "format_search_empty_block": "formatting",
    "format_sources_fence": "formatting",
    "is_ambiguous_local_places_query": "geo_intent",
    "is_distance_query": "geo_intent",
    "is_geo_query": "geo_intent",
    "names_its_place": "geo_intent",
    "points_back_in_chat": "turn_query",
    "run_cached_search": "search_cache",
    "side_search_budget": "search_cache",
    "SideSearchBudget": "search_cache",
    "turn_search_budget": "search_cache",
    "sources_payload": "formatting",
    "strip_sources_from_text": "formatting",
    "wants_dated_results": "recency",
}

__all__ = [
    "AMBIGUOUS_NEARBY_HINT",
    "DIRECTIONS_LINK_RULE",
    "GEO_ACTIVE_LOCATION_HINT",
    "GEO_DISTANCE_HINT",
    "LOCATION_ASK_OPENING",
    "WEB_SEARCH_HINT",
    "SearchSource",
    "SideSearchBudget",
    "TurnTavilyBudget",
    "WebSearchAdapter",
    "asks_about_a_place",
    "drop_source_credits",
    "format_location_not_set_answer",
    "format_search_block",
    "format_search_empty_block",
    "format_sources_fence",
    "is_ambiguous_local_places_query",
    "is_distance_query",
    "is_geo_query",
    "names_its_place",
    "points_back_in_chat",
    "run_cached_search",
    "side_search_budget",
    "sources_payload",
    "strip_sources_from_text",
    "turn_search_budget",
    "wants_dated_results",
]


# Seams the chat turn uses to decide on a search and read prior turns.
_MODULE_EXPORTS = ("detection", "subject")


def __getattr__(name: str) -> Any:
    if name in _MODULE_EXPORTS:
        value = import_module(f"app.modules.web_search.{name}")
    else:
        module = _EXPORTS.get(name)
        if module is None:
            raise AttributeError(name)
        value = getattr(import_module(f"app.modules.web_search.{module}"), name)
    globals()[name] = value
    return value
