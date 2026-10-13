"""The query a turn's live search sends, when the tool loop searches before the model.

Most messages are their own query. A request that names its topic ("search
for the meaning of bini") sends the topic. A message that points back ("do a
search", "look it up", "when did she die?") sends what the conversation was
about; sending the literal words searched for "do a search".
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.modules.web_search.command import search_command
from app.modules.web_search.patterns import (
    _CLARIFICATION,
    _SHORT_FOLLOWUP_WORDS,
    asks_for_prior_subject,
    collapse_ws,
)
from app.modules.web_search.query_builders import (
    anchor_news_query_to_today,
    build_search_queries,
    is_current_news_request,
)
from app.modules.web_search.subject import collect_prior_user_messages
from app.services.conversation_reference import resolve_reference, turns_from_prompt

# Words that stand for someone or something named earlier in the chat.
_REFERENCE_WORDS = frozenset(
    {
        "it",
        "its",
        "that",
        "this",
        "those",
        "these",
        "she",
        "he",
        "her",
        "him",
        "his",
        "they",
        "them",
        "their",
        "there",
    }
)


def _fold(word: str) -> str:
    return word.lower().strip(".,!?;:\"'()[]")


def points_back(text: str, prior_user_messages: list[str] | None) -> bool:
    """True when *text* needs the conversation to say what to search."""
    if not prior_user_messages:
        return False
    cleaned = collapse_ws(text)
    if asks_for_prior_subject(cleaned) or _CLARIFICATION.search(cleaned):
        return True
    words = [_fold(w) for w in cleaned.split()]
    return len(words) <= _SHORT_FOLLOWUP_WORDS and any(w in _REFERENCE_WORDS for w in words)


async def search_queries_for_turn(
    settings: Settings,
    user_text: str,
    messages: list[dict[str, Any]],
    *,
    user_timezone: str | None = None,
) -> list[str]:
    """Queries for this turn's search, best first; never empty for a non-empty message."""
    cleaned = collapse_ws(user_text)
    if not cleaned:
        return []
    command = search_command(cleaned)
    if command is not None and command.subject:
        subject = command.subject
        if is_current_news_request(subject):
            subject = anchor_news_query_to_today(subject, user_timezone)
        return [subject]
    priors = collect_prior_user_messages(messages, user_text)
    if points_back(cleaned, priors):
        resolved = await resolve_reference(
            settings,
            kind="search",
            request=cleaned,
            turns=turns_from_prompt(messages),
        )
        if resolved:
            return [resolved]
        queries = build_search_queries(
            cleaned,
            user_timezone=user_timezone,
            prior_user_messages=priors,
        )
        if queries:
            return queries
    return [cleaned]
