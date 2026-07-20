"""Build Tavily/DuckDuckGo queries from user text."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from app.gateways.web_search_gateway import WebSearchHit
from app.services import time_context as time_context_service
from app.services.web_search.geo_intent import is_geo_query
from app.services.web_search.patterns import (
    _CLARIFICATION,
    _GENERIC_NEWS_QUERY,
    _LOOK_IT_UP,
    _ONGOING,
    _QUERY_PREFIX,
    _SPORTS,
    _TEAM_POSSESSIVE_SCORE,
    _TEAM_SCORE,
    _WORLD_CUP,
    collapse_ws,
)
from app.services.web_search.subject import resolve_search_subject


def _yesterday_label(user_timezone: str | None) -> str:
    tz = time_context_service.resolve_timezone(user_timezone)
    yesterday = datetime.now(tz) - timedelta(days=1)
    return yesterday.strftime("%B %d %Y")


def _yesterday_iso(user_timezone: str | None) -> str:
    tz = time_context_service.resolve_timezone(user_timezone)
    yesterday = datetime.now(tz) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def _today_label(user_timezone: str | None) -> str:
    tz = time_context_service.resolve_timezone(user_timezone)
    return datetime.now(tz).strftime("%B %d %Y")


def _today_iso(user_timezone: str | None) -> str:
    tz = time_context_service.resolve_timezone(user_timezone)
    return datetime.now(tz).strftime("%Y-%m-%d")


def _world_cup_queries(
    *, today: str, yesterday: str, yesterday_iso: str, today_iso: str
) -> list[str]:
    return [
        f"FIFA World Cup 2026 live scores results {today}",
        f"FIFA World Cup 2026 match results scores {yesterday}",
        f"World Cup 2026 group stage results {yesterday_iso}",
        f"World Cup 2026 scores {today_iso}",
    ]


_TEMPORAL_TEAM_WORDS = frozenset({"yesterday", "today", "tomorrow", "tonight", "week", "weekend"})
_TEAM_FILLER = frozenset({"show", "me", "the", "a", "an", "my", "our"})


def _normalize_team_label(raw: str) -> str:
    label = collapse_ws(raw).strip("?.!")
    # No ``\s+`` — input is whitespace-collapsed (CodeQL py/polynomial-redos).
    label = re.sub(r"(?: game| match| scores?| results?| fixture)s?$", "", label, flags=re.I)
    label = re.sub(r"(?:'s|s)$", "", label, flags=re.I)
    return label.strip()


def _is_plausible_team_label(label: str) -> bool:
    """Reject temporal phrases mis-parsed as teams (\"yesterdays game\")."""
    tokens = [t for t in label.lower().split() if t not in _TEAM_FILLER]
    if not tokens:
        return False
    if tokens[0] in _TEMPORAL_TEAM_WORDS:
        return False
    return True


def _extract_team_subject(cleaned: str) -> str | None:
    if not (_TEAM_SCORE.search(cleaned) or _TEAM_POSSESSIVE_SCORE.search(cleaned)):
        return None
    for pattern in (
        r"^(?P<team>.+?)\s+(?:game|match|scores?|results?|fixture)s?\s*[?.!]*$",
        r"^(?P<team>.+?)\s+(?:game|match)\s+score\s*[?.!]*$",
    ):
        match = re.match(pattern, cleaned, flags=re.I)
        if match:
            team = _normalize_team_label(match.group("team"))
            if team and len(team.split()) <= 6 and _is_plausible_team_label(team):
                return team
    fallback = _normalize_team_label(cleaned) or None
    if fallback and _is_plausible_team_label(fallback):
        return fallback
    return None


def _team_score_queries(team: str) -> list[str]:
    return [
        f"{team} national team football latest match score result",
        f"{team} football latest match score result",
        f"{team} World Cup 2026 qualified teams list",
    ]


def _hit_mentions_team(hit: WebSearchHit, team: str) -> bool:
    needle = team.strip().lower()
    if not needle:
        return False
    blob = f"{hit.title} {hit.snippet}".lower()
    return needle in blob


def _prioritize_team_hits(hits: list[WebSearchHit], team: str) -> list[WebSearchHit]:
    if not hits or not team.strip():
        return hits
    matched = [hit for hit in hits if _hit_mentions_team(hit, team)]
    if not matched:
        return hits
    rest = [hit for hit in hits if hit not in matched]
    return matched + rest


def _is_team_specific_sports_query(cleaned: str) -> bool:
    if _WORLD_CUP.search(cleaned):
        return False
    return (
        _TEAM_SCORE.search(cleaned) is not None
        or _TEAM_POSSESSIVE_SCORE.search(cleaned) is not None
    )


def _geo_located_queries(
    cleaned: str,
    user_location: str | None,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
) -> list[str]:
    query = _QUERY_PREFIX.sub("", cleaned.strip()).strip(" ?.!")
    loc = (user_location or "").strip()
    coord = (
        f"{latitude:.5f},{longitude:.5f}"
        if latitude is not None and longitude is not None
        else None
    )
    anchor = coord or loc
    if anchor:
        for pattern, repl in (
            (r"\bnear me\b", f"near {anchor}"),
            (r"\bnearby\b", f"near {anchor}"),
            (r"\baround here\b", f"near {anchor}"),
            (r"\bin(?:\s+this)?\s+town\b", f"in {loc or anchor}"),
            (r"\bclose to me\b", f"near {anchor}"),
            (r"\bfrom me\b", f"from {anchor}"),
            (r"\bfrom here\b", f"from {anchor}"),
        ):
            query = re.sub(pattern, repl, query, flags=re.I)
        if anchor.lower() not in query.lower():
            query = f"{query} {anchor}"
        if loc and loc.lower() not in query.lower():
            query = f"{query} {loc}"
    primary = query or cleaned
    return [primary, f"{primary} official website address"]


def build_search_queries(
    text: str,
    *,
    user_timezone: str | None = None,
    user_location: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    prior_user_messages: list[str] | None = None,
) -> list[str]:
    subject = resolve_search_subject(text, prior_user_messages=prior_user_messages)
    query = _QUERY_PREFIX.sub("", subject.strip())
    cleaned = query.strip(" ?.!")
    current = collapse_ws(text)
    yesterday = _yesterday_label(user_timezone)
    yesterday_iso = _yesterday_iso(user_timezone)
    today = _today_label(user_timezone)
    today_iso = _today_iso(user_timezone)

    if _GENERIC_NEWS_QUERY.match(cleaned):
        return ["top news today"]

    if _WORLD_CUP.search(current) or (
        _WORLD_CUP.search(subject) and (_ONGOING.search(current) or _CLARIFICATION.search(current))
    ):
        return _world_cup_queries(
            today=today,
            yesterday=yesterday,
            yesterday_iso=yesterday_iso,
            today_iso=today_iso,
        )

    # Generic "yesterday + sports" must NOT force World Cup — that stole team
    # queries like "did the Lakers win yesterday". WC only via _WORLD_CUP above.

    team = _extract_team_subject(cleaned)
    if team and _is_team_specific_sports_query(cleaned):
        return _team_score_queries(team)

    if _SPORTS.search(cleaned):
        return [
            f"{cleaned} scores results {yesterday}",
            f"{cleaned} latest match result",
        ]

    if _LOOK_IT_UP.match(current) and prior_user_messages:
        return build_search_queries(
            subject,
            user_timezone=user_timezone,
            user_location=user_location,
            prior_user_messages=None,
        )

    if _CLARIFICATION.search(current) and prior_user_messages:
        return build_search_queries(
            subject,
            user_timezone=user_timezone,
            user_location=user_location,
            prior_user_messages=None,
        )

    if is_geo_query(subject) or is_geo_query(current):
        return _geo_located_queries(
            cleaned or current,
            user_location,
            latitude=latitude,
            longitude=longitude,
        )

    fallback = cleaned or current
    return [fallback] if fallback else []


def build_search_query(
    text: str,
    *,
    user_timezone: str | None = None,
    user_location: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    prior_user_messages: list[str] | None = None,
) -> str:
    queries = build_search_queries(
        text,
        user_timezone=user_timezone,
        user_location=user_location,
        latitude=latitude,
        longitude=longitude,
        prior_user_messages=prior_user_messages,
    )
    return queries[0] if queries else text.strip()
