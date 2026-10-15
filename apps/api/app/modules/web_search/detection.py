"""Decide whether a turn needs live web search."""

from __future__ import annotations

import logging
import re

from app.core.config import Settings
from app.models.schemas import WebSearchClassification
from app.modules.chat import (
    has_code_syntax,
    has_locale_cue,
    is_lightweight_chat_turn,
    is_personal_disclosure_turn,
    is_short_confirmation,
    prior_looks_like_offer,
)
from app.modules.web_search.command import search_command
from app.modules.web_search.geo_intent import is_geo_query, is_short_letter_answer
from app.modules.web_search.patterns import (
    _CLARIFICATION,
    _EXPLICIT_SEARCH,
    _LATEST_NEWS,
    _NEW_PRODUCT,
    _NEWS,
    _ONGOING,
    _OWN_CALENDAR,
    _PERSONAL_PLANNING,
    _REMINDER_TURN,
    _SHORT_FOLLOWUP_WORDS,
    _SKIP,
    _SPORTS,
    _SPORTS_LOOKUP,
    _TEAM_POSSESSIVE_SCORE,
    _TEAM_SCORE,
    _WEATHER_NOT_A_FORECAST,
    _WORLD_CUP,
    _YESTERDAY,
    asks_for_prior_subject,
    collapse_ws,
    has_recency,
    is_correspondence_request,
    is_weather_request,
    is_word_problem,
    looks_like_math_or_code,
)
from app.modules.web_search.subject import (
    _prior_searchable_topic,
    resolve_search_subject,
)
from app.services import time_context as time_context_service

logger = logging.getLogger(__name__)


# Questions about the user's own stored profile must be answered from memory,
# not by searching the public web. Keep this deliberately narrower than every
# first-person question: "find jobs for me" or "restaurants near me" may still
# need live results, while these clauses ask Recall to repeat a personal fact.
_PERSONAL_MEMORY_QUESTION = re.compile(
    r"(?:"
    r"\bwhere\s+(?:do|did)\s+i\s+(?:currently\s+)?work"
    r"(?:\s+(?:currently|now|right\s+now))?\b"
    r"|\bwho\s+do\s+i\s+(?:currently\s+)?work\s+for\b"
    r"|\b(?:what|which)\s+company\s+(?:do\s+i\s+work\s+(?:for|at)"
    r"|am\s+i\s+(?:currently\s+)?(?:working\s+(?:for|at)|employed\s+(?:by|at)))\b"
    r"|\bwhere\s+am\s+i\s+(?:currently\s+)?employed\b"
    r"|\bwhat(?:'s|\s+is|\s+was)\s+my\s+(?:current\s+)?"
    r"(?:job|role|title|employer|company|occupation|profession)\b"
    r"(?=\s*(?:[?.!,]|$|\band\b))"
    r"|\b(?:what|which)\s+(?:company|job|role|employer)\s+(?:am|was)\s+i\s+"
    r"(?:considering|targeting|pursuing|interested\s+in|moving\s+to|"
    r"planning\s+to\s+join|trying\s+to\s+join|hoping\s+to\s+join)\b"
    r"|\bwhat(?:'s|\s+is|\s+was)\s+my\s+"
    r"(?:current\s+|future\s+|career\s+|long[- ]term\s+)?"
    r"(?:goal|target|aspiration|plan)\b"
    r"(?=\s*(?:[?.!,]|$|\band\b))"
    r"|\b(?:do|can)\s+you\s+remember\s+(?:where|who|what)\s+i\b"
    r"|\bwhat\s+(?:do|did)\s+you\s+(?:remember|know)\s+about\s+my\s+"
    r"(?:job|work|career|role|employer|company|goals?|plans?)\b"
    r")",
    re.IGNORECASE,
)


def web_search_skip(
    text: str,
    *,
    prior_user_messages: list[str] | None = None,
    prior_assistant: str | None = None,
) -> bool:
    """Hard no — never run web search or the classifier."""
    cleaned = collapse_ws(text)
    if not cleaned:
        return True
    # "search", "google it": an explicit request is never chitchat.
    if search_command(cleaned) is not None:
        return False
    if is_word_problem(cleaned) and not is_weather_request(cleaned):
        return True
    follow_up = bool(prior_user_messages) or prior_looks_like_offer(prior_assistant)
    if len(cleaned) < 4 and not (is_short_confirmation(cleaned) and follow_up):
        return True
    confirming = is_short_confirmation(cleaned) and follow_up
    # Only a yes to an offer may search; "no" / "got it" never do, question or not.
    if not confirming and is_lightweight_chat_turn(cleaned):
        return True
    if is_short_letter_answer(cleaned):
        return True
    if is_personal_disclosure_turn(cleaned):
        return True
    if _PERSONAL_MEMORY_QUESTION.search(cleaned):
        return True
    if time_context_service.is_local_now_question(cleaned):
        return True
    if time_context_service.is_location_question(cleaned):
        return True
    if _SKIP.search(cleaned):
        return True
    # "Under the weather today", "a poem about the weather": a figure of speech.
    if _WEATHER_NOT_A_FORECAST.search(cleaned) and not is_weather_request(cleaned):
        return True
    if _REMINDER_TURN.search(cleaned):
        return True
    if _PERSONAL_PLANNING.search(cleaned):
        return True
    return bool(_OWN_CALENDAR.search(cleaned)) or has_locale_cue(cleaned, "calendar")


# A live or time-sensitive cue is the only reason to spend a model call
# deciding search. Schoolbook questions and chitchat have none of these, so
# they keep the regex answer and the chat model can start immediately. Weather
# is not a cue: a forecast is a fast yes and "what causes weather" needs no search.
_MAYBE_LIVE = re.compile(
    r"\b(?:who\s+is|who\s+leads|current|latest|today|tonight|right\s+now|"
    r"price|pricing|hotel|score|news|ceo|near\s+me|"
    # Rules, fares, schedules and results change; a model's memory of them is stale.
    r"visas?|flights?|airfares?|fares?|tickets?|this\s+weekend|open\s+now|"
    r"sunset|sunrise|results|how\s+much\s+(?:is|are|does|do)\s+(?:an?|the)|"
    r"rn|exchange\s+rates?|(?:usd|eur|gbp|etb|kes)\s+(?:to|in)\s+(?:usd|eur|gbp|etb|kes|birr)|"
    r"opening\s+hours|what\s+time\s+(?:does|do)|open\s+(?:today|tomorrow|on\s+sundays?))\b",
    re.IGNORECASE,
)
_TIME_SENSITIVE = re.compile(
    r"\b(?:when|next|upcoming|release|coming out|launch)\b",
    re.IGNORECASE,
)


def _live_lookup_cue(text: str) -> bool:
    return _MAYBE_LIVE.search(text) is not None or _TIME_SENSITIVE.search(text) is not None


def _continues_searchable_topic(
    text: str,
    prior_user_messages: list[str] | None,
) -> bool:
    """A short line continuing the user's previous message, when that needed a lookup.

    An older search does not count. Otherwise "remind me…" or "what is my
    dog's name?" after a price question pays for a classifier that says no.
    """
    if not prior_user_messages:
        return False
    if len(collapse_ws(text).split()) > _SHORT_FOLLOWUP_WORDS:
        return False
    # "And the Red Terror museum?" after "what time does the National Museum
    # open" continues a live question; the classifier decides.
    last = prior_user_messages[-1]
    return _prior_searchable_topic([last]) is not None or (
        _live_lookup_cue(collapse_ws(last)) and not looks_like_math_or_code(last)
    )


def web_search_fast_yes(
    text: str,
    *,
    prior_user_messages: list[str] | None = None,
) -> bool:
    """Obvious yes — skip the classifier."""
    cleaned = collapse_ws(text)
    if asks_for_prior_subject(cleaned):
        return bool(prior_user_messages)
    command = search_command(cleaned)
    if command is not None and command.subject:
        return True
    if _EXPLICIT_SEARCH.search(cleaned):
        return True
    if _NEWS.search(cleaned) or _LATEST_NEWS.search(cleaned):
        return True
    # Conditions and products change after training; no model call can know them.
    if is_weather_request(cleaned) or _NEW_PRODUCT.search(cleaned):
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


# "Current" in a circuit is amps, and "100 days from tomorrow" is counting:
# neither is news.
_CURRENT = re.compile(r"\bcurrent\b", re.IGNORECASE)
_CIRCUIT = re.compile(
    r"\bohms?\b|\u03a9|\bvolts?\b|\b\d+(?:\.\d+)?\s*k?v\b|resist|circuit|\bseries\b"
    r"|\bparallel\b|battery|\bamps?\b|ampere|capacitor|inductor|kirchhoff",
    re.IGNORECASE,
)
_DATE_ARITHMETIC = re.compile(
    r"\b\d+\s+(?:days?|weeks?|months?|years?)\s+(?:from|after|before|ago|since|until)\b"
    r"|\bwhat\s+day\s+(?:of\s+the\s+week\s+)?(?:will\s+it\s+be|was\s+it|is\s+it)\s+\d+",
    re.IGNORECASE,
)


_TELLS = re.compile(
    r"(?:ugh|omg|lol|haha|so|well|just|i|i'm|im|i've|my|we|we're|today\s+i)\b", re.IGNORECASE
)


def needs_web_search_heuristic(
    text: str,
    *,
    prior_user_messages: list[str] | None = None,
) -> bool:
    """Regex fallback for follow-ups and recency when the classifier is off or fails."""
    cleaned = collapse_ws(text)
    electric = _CURRENT.search(cleaned) and _CIRCUIT.search(cleaned)
    if electric or _DATE_ARITHMETIC.search(cleaned) or is_correspondence_request(cleaned):
        return False
    # "Traceback (most recent call last)" is not recency.
    if has_code_syntax(text):
        return False
    if _CLARIFICATION.search(cleaned) and prior_user_messages:
        return _prior_searchable_topic(prior_user_messages) is not None
    if prior_user_messages and len(cleaned.split()) <= _SHORT_FOLLOWUP_WORDS:
        if _prior_searchable_topic([prior_user_messages[-1]]) is not None:
            return True
    if has_recency(cleaned) and "?" in cleaned:
        return True
    # "ugh forgot my umbrella today and its pouring" tells; it asks nothing.
    if has_recency(cleaned) and len(cleaned.split()) >= 6 and not _TELLS.match(cleaned):
        return True
    return False


def needs_web_search(
    text: str,
    *,
    prior_user_messages: list[str] | None = None,
    prior_assistant: str | None = None,
) -> bool:
    """Sync gate: skip + fast-path + heuristic (tests and legacy callers)."""
    if web_search_skip(
        text, prior_user_messages=prior_user_messages, prior_assistant=prior_assistant
    ):
        return False
    if web_search_fast_yes(text, prior_user_messages=prior_user_messages):
        return True
    return needs_web_search_heuristic(text, prior_user_messages=prior_user_messages)


async def classify_web_search(
    text: str,
    settings: Settings,
    *,
    prior_user_messages: list[str] | None = None,
    prior_assistant: str | None = None,
) -> WebSearchClassification | None:
    """LLM gate for ambiguous turns; None when classifier disabled or call fails."""
    if not settings.web_search_classifier_enabled:
        return None
    from app.modules.web_search.classify import classify_web_search_need

    try:
        return await classify_web_search_need(
            settings,
            text,
            prior_user_messages=prior_user_messages,
            prior_assistant=prior_assistant,
        )
    except Exception:
        logger.warning("Web-search classifier failed; using heuristic", exc_info=True)
    # CancelledError intentionally propagates: stopping a turn cancels its IO.
    return None


async def should_web_search(
    text: str,
    settings: Settings,
    *,
    prior_user_messages: list[str] | None = None,
    prior_assistant: str | None = None,
) -> bool:
    """Async gate: regex first. The classifier runs only for a live cue or a short follow-up."""
    if not settings.web_search_enabled:
        return False
    if web_search_skip(
        text, prior_user_messages=prior_user_messages, prior_assistant=prior_assistant
    ):
        return False
    if web_search_fast_yes(text, prior_user_messages=prior_user_messages):
        return True
    cleaned = collapse_ws(text)
    if not (_live_lookup_cue(cleaned) or _continues_searchable_topic(cleaned, prior_user_messages)):
        return needs_web_search_heuristic(text, prior_user_messages=prior_user_messages)
    classification = await classify_web_search(
        text,
        settings,
        prior_user_messages=prior_user_messages,
        prior_assistant=prior_assistant,
    )
    if classification is None:
        return needs_web_search_heuristic(text, prior_user_messages=prior_user_messages)
    return classification.needs_search
