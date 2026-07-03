"""Inject live web results into the chat prompt."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.core.config import Settings
from app.gateways.web_search_gateway import WebSearchHit
from app.services.prompt_safety import wrap_untrusted
from app.services.web_search.detection import (
    classify_web_search,
    needs_web_search_heuristic,
    web_search_fast_yes,
    web_search_skip,
)
from app.services.web_search.formatting import (
    GEO_DISTANCE_HINT,
    format_search_block,
    format_search_empty_block,
)
from app.services.web_search.geo_intent import _geo_is_active, _places_list_is_active
from app.services.web_search.query_builders import (
    _extract_team_subject,
    _prioritize_team_hits,
    build_search_queries,
)
from app.services.web_search.search_cache import _run_search
from app.services.web_search.subject import _prior_user_messages, resolve_search_subject


def _inject_before_last_user(messages: list[dict[str, str]], block: str) -> list[dict[str, str]]:
    augmented = list(messages)
    insert_at = len(augmented)
    for index in range(len(augmented) - 1, -1, -1):
        if augmented[index].get("role") == "user":
            insert_at = index
            break
    augmented.insert(insert_at, {"role": "system", "content": block})
    return augmented


async def augment_prompt_messages(
    messages: list[dict[str, str]],
    user_content: str,
    settings: Settings,
    *,
    user_timezone: str | None = None,
    user_location: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    prior_user_messages: list[str] | None = None,
    on_status: Callable[[str], Awaitable[None]] | None = None,
) -> tuple[list[dict[str, str]], list[WebSearchHit]]:
    prior_user = prior_user_messages or _prior_user_messages(messages, user_content)
    if web_search_skip(user_content, prior_user_messages=prior_user):
        return messages, []

    if web_search_fast_yes(user_content, prior_user_messages=prior_user):
        needs_search = True
        classifier_query: str | None = None
    else:
        classification = await classify_web_search(
            user_content,
            settings,
            prior_user_messages=prior_user,
        )
        if classification is not None:
            if not classification.needs_search:
                return messages, []
            needs_search = True
            classifier_query = (classification.query or "").strip() or None
        elif not needs_web_search_heuristic(user_content, prior_user_messages=prior_user):
            return messages, []
        else:
            needs_search = True
            classifier_query = None

    if not needs_search:
        return messages, []

    if on_status is not None:
        await on_status("searching")

    subject = resolve_search_subject(user_content, prior_user_messages=prior_user)
    if classifier_query:
        queries = [classifier_query]
    else:
        queries = build_search_queries(
            user_content,
            user_timezone=user_timezone,
            user_location=user_location,
            latitude=latitude,
            longitude=longitude,
            prior_user_messages=prior_user,
        )
    hits, tried = await _run_search(settings, queries)
    team = _extract_team_subject(user_content.strip())
    if not team and prior_user:
        for prior in reversed(prior_user):
            team = _extract_team_subject(prior.strip())
            if team:
                break
    hits = _prioritize_team_hits(hits, team) if team else hits
    local_places = _places_list_is_active(user_content, subject)
    geo_query = _geo_is_active(user_content, subject)
    if hits:
        block = format_search_block(
            hits, team=team, local_places=local_places, user_location=user_location
        )
        if geo_query and not local_places:
            block = f"{block}\n\n{GEO_DISTANCE_HINT}"
        block = wrap_untrusted("web search", block)
    else:
        block = format_search_empty_block(tried, local_places=local_places)
    return _inject_before_last_user(messages, block), hits
