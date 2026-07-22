"""Inject live web results into the chat prompt."""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways.web_search_gateway import WebSearchHit
from app.models.orm import User
from app.services.chat.stream_status import StreamStatusFn, clip_status_detail
from app.services.prompt_inject import inject_before_last_user
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


async def build_search_augmentation(
    user_content: str,
    settings: Settings,
    *,
    messages: list[dict[str, str]] | None = None,
    user_timezone: str | None = None,
    user_location: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    prior_user_messages: list[str] | None = None,
    on_status: StreamStatusFn | None = None,
    user: User | None = None,
    redis: Redis | None = None,
) -> tuple[str | None, list[WebSearchHit]]:
    """Compute the web-search system block (or None) without mutating messages.

    Safe to run concurrently with other augment builders that share the same
    base prompt — the caller injects returned blocks after gather.
    """
    prior_user = prior_user_messages
    if prior_user is None:
        prior_user = _prior_user_messages(messages or [], user_content)
    if web_search_skip(user_content, prior_user_messages=prior_user):
        return None, []

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
                return None, []
            needs_search = True
            classifier_query = (classification.query or "").strip() or None
        elif not needs_web_search_heuristic(user_content, prior_user_messages=prior_user):
            return None, []
        else:
            needs_search = True
            classifier_query = None

    if not needs_search:
        return None, []

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

    if on_status is not None:
        # Surface what we're searching for so the client label is specific.
        await on_status("searching", clip_status_detail(queries[0] if queries else None))

    hits, tried = await _run_search(settings, queries, user=user, redis=redis)
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
    return block, hits


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
    on_status: StreamStatusFn | None = None,
    user: User | None = None,
    redis: Redis | None = None,
) -> tuple[list[dict[str, str]], list[WebSearchHit]]:
    block, hits = await build_search_augmentation(
        user_content,
        settings,
        messages=messages,
        user_timezone=user_timezone,
        user_location=user_location,
        latitude=latitude,
        longitude=longitude,
        prior_user_messages=prior_user_messages,
        on_status=on_status,
        user=user,
        redis=redis,
    )
    if block is None:
        return messages, []
    return inject_before_last_user(messages, block), hits
