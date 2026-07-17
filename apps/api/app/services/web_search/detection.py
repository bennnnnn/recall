"""Decide whether a turn needs live web search."""

from __future__ import annotations

from app.core.config import Settings
from app.models.schemas import WebSearchClassification
from app.services import calendar as calendar_service
from app.services import time_context as time_context_service
from app.services.chat.prompt_constants import is_lightweight_chat_turn
from app.services.web_search.geo_intent import is_geo_query, is_vocab_quiz_answer
from app.services.web_search.patterns import (
    _CLARIFICATION,
    _EXPLICIT_SEARCH,
    _LOOK_IT_UP,
    _NEWS,
    _ONGOING,
    _PERSONAL_PLANNING,
    _SHORT_FOLLOWUP_WORDS,
    _SKIP,
    _SPORTS,
    _SPORTS_LOOKUP,
    _TEAM_POSSESSIVE_SCORE,
    _TEAM_SCORE,
    _WORLD_CUP,
    _YESTERDAY,
    collapse_ws,
    has_recency,
)
from app.services.web_search.subject import (
    _prior_searchable_topic,
    resolve_search_subject,
)


def web_search_skip(
    text: str,
    *,
    prior_user_messages: list[str] | None = None,
) -> bool:
    """Hard no — never run web search or the classifier."""
    del prior_user_messages  # reserved for future context-aware skips
    cleaned = collapse_ws(text)
    if not cleaned or len(cleaned) < 4:
        return True
    if is_lightweight_chat_turn(cleaned):
        return True
    if is_vocab_quiz_answer(cleaned):
        return True
    if time_context_service.is_time_question(cleaned):
        return True
    if time_context_service.is_location_question(cleaned):
        return True
    if _SKIP.search(cleaned):
        return True
    if _PERSONAL_PLANNING.search(cleaned):
        return True
    if calendar_service.is_external_calendar_question(cleaned):
        return True
    return False


def web_search_fast_yes(
    text: str,
    *,
    prior_user_messages: list[str] | None = None,
) -> bool:
    """Obvious yes — skip the classifier."""
    cleaned = collapse_ws(text)
    if _LOOK_IT_UP.match(cleaned):
        return bool(prior_user_messages)
    if _EXPLICIT_SEARCH.search(cleaned):
        return True
    if _NEWS.search(cleaned):
        return True
    if _SPORTS_LOOKUP.search(cleaned):
        return True
    if _TEAM_SCORE.search(cleaned) or _TEAM_POSSESSIVE_SCORE.search(cleaned):
        return True
    if _YESTERDAY.search(cleaned) and _SPORTS.search(cleaned):
        return True
    if _WORLD_CUP.search(cleaned) and (_ONGOING.search(cleaned) or _SPORTS.search(cleaned)):
        return True
    subject = resolve_search_subject(cleaned, prior_user_messages=prior_user_messages)
    if _SPORTS_LOOKUP.search(subject):
        return True
    if _YESTERDAY.search(subject) and _SPORTS.search(subject):
        return True
    if _WORLD_CUP.search(subject) and (_ONGOING.search(cleaned) or _SPORTS.search(subject)):
        return True
    if is_geo_query(cleaned):
        return True
    return False


def needs_web_search_heuristic(
    text: str,
    *,
    prior_user_messages: list[str] | None = None,
) -> bool:
    """Regex fallback for follow-ups and recency when the classifier is off or fails."""
    cleaned = collapse_ws(text)
    if _CLARIFICATION.search(cleaned) and prior_user_messages:
        return _prior_searchable_topic(prior_user_messages) is not None
    if prior_user_messages and len(cleaned.split()) <= _SHORT_FOLLOWUP_WORDS:
        if _prior_searchable_topic(prior_user_messages) is not None:
            return True
    if has_recency(cleaned) and "?" in cleaned:
        return True
    if has_recency(cleaned) and len(cleaned.split()) >= 6:
        return True
    return False


def needs_web_search(
    text: str,
    *,
    prior_user_messages: list[str] | None = None,
) -> bool:
    """Sync gate: skip + fast-path + heuristic (tests and legacy callers)."""
    if web_search_skip(text, prior_user_messages=prior_user_messages):
        return False
    if web_search_fast_yes(text, prior_user_messages=prior_user_messages):
        return True
    return needs_web_search_heuristic(text, prior_user_messages=prior_user_messages)


async def classify_web_search(
    text: str,
    settings: Settings,
    *,
    prior_user_messages: list[str] | None = None,
) -> WebSearchClassification | None:
    """LLM gate for ambiguous turns; None when classifier disabled or call fails."""
    if not settings.web_search_classifier_enabled:
        return None
    from app.services.web_search.classify import classify_web_search_need

    return await classify_web_search_need(
        settings,
        text,
        prior_user_messages=prior_user_messages,
    )


async def should_web_search(
    text: str,
    settings: Settings,
    *,
    prior_user_messages: list[str] | None = None,
) -> bool:
    """Async gate: regex fast paths, then LLM classifier for everything else."""
    if not settings.web_search_enabled:
        return False
    if web_search_skip(text, prior_user_messages=prior_user_messages):
        return False
    if web_search_fast_yes(text, prior_user_messages=prior_user_messages):
        return True
    classification = await classify_web_search(
        text,
        settings,
        prior_user_messages=prior_user_messages,
    )
    if classification is None:
        return needs_web_search_heuristic(text, prior_user_messages=prior_user_messages)
    return classification.needs_search
