"""Resolve the searchable subject for follow-up turns."""

from __future__ import annotations

from app.services.web_search.patterns import (
    _CLARIFICATION,
    _LOOK_IT_UP,
    _NEWS,
    _SHORT_FOLLOWUP_WORDS,
    _SPORTS,
    _WORLD_CUP,
)


def _prior_user_messages(
    prompt_messages: list[dict[str, str]],
    current: str,
) -> list[str]:
    user_msgs = [str(m.get("content") or "") for m in prompt_messages if m.get("role") == "user"]
    if user_msgs and user_msgs[-1].strip() == current.strip():
        user_msgs = user_msgs[:-1]
    return [msg for msg in user_msgs if msg.strip()]


def _prior_searchable_topic(prior_user_messages: list[str] | None) -> str | None:
    if not prior_user_messages:
        return None
    for msg in reversed(prior_user_messages):
        cleaned = msg.strip()
        if not cleaned or _LOOK_IT_UP.match(cleaned):
            continue
        if (
            _topic_needs_search(cleaned)
            or _SPORTS.search(cleaned)
            or _WORLD_CUP.search(cleaned)
            or _NEWS.search(cleaned)
        ):
            return cleaned
    return None


def resolve_search_subject(
    user_content: str,
    *,
    prior_user_messages: list[str] | None = None,
) -> str:
    cleaned = user_content.strip()
    if _LOOK_IT_UP.match(cleaned) and prior_user_messages:
        for msg in reversed(prior_user_messages):
            if msg.strip() and not _LOOK_IT_UP.match(msg.strip()):
                return msg.strip()
    if prior_user_messages and (
        len(cleaned.split()) <= _SHORT_FOLLOWUP_WORDS or _CLARIFICATION.search(cleaned)
    ):
        prior_topic = _prior_searchable_topic(prior_user_messages)
        if prior_topic:
            return prior_topic
    return cleaned


def _topic_needs_search(text: str) -> bool:
    from app.services.web_search.detection import needs_web_search

    return needs_web_search(text, prior_user_messages=None)
