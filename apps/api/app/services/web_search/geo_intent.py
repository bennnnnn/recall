"""Geo / proximity / distance query classification."""

from __future__ import annotations

import re

from app.services.web_search.patterns import (
    _AMBIGUOUS_NEARBY_SUBJECT,
    _DISTANCE_INTENT,
    _FROM_USER,
    _IMPLICIT_LOCAL,
    _NEARBY_INTENT,
    _PROXIMITY_PHRASES,
    _QUALIFIED_NEARBY,
    best_near_phrase,
    distance_between_phrase,
    non_geographic_nearest,
)


def _subject_without_proximity(cleaned: str) -> str:
    subject = cleaned.strip()
    for pattern in _PROXIMITY_PHRASES:
        subject = re.sub(pattern, " ", subject, flags=re.IGNORECASE)
    return " ".join(subject.split()).strip(" ?.!")


def is_proximity_query(text: str) -> bool:
    """Find something near the user — any category (restaurant, hospital, casino, …)."""
    cleaned = text.strip()
    if not cleaned:
        return False
    if non_geographic_nearest(cleaned):
        return False
    if _NEARBY_INTENT.search(cleaned):
        return True
    if _IMPLICIT_LOCAL.search(cleaned):
        return True
    return bool(best_near_phrase(cleaned) and "?" in cleaned)


def is_distance_query(text: str) -> bool:
    """Distance, travel time, or directions from the user's location."""
    cleaned = text.strip()
    if not cleaned or not _DISTANCE_INTENT.search(cleaned):
        return False
    if distance_between_phrase(cleaned) and not _FROM_USER.search(cleaned):
        return False
    return True


def is_geo_query(text: str) -> bool:
    """Any query that needs the user's location — places OR distance. Venue-agnostic."""
    return is_proximity_query(text) or is_distance_query(text)


def is_places_list_query(text: str) -> bool:
    """Render the native ```places card (find venues, not mileage-only answers)."""
    if is_ambiguous_local_places_query(text):
        return False
    return is_proximity_query(text)


def is_local_places_query(text: str) -> bool:
    """Backward-compatible alias — prefer is_geo_query / is_places_list_query."""
    return is_proximity_query(text)


def is_ambiguous_local_places_query(text: str) -> bool:
    """Nearby intent but missing sale/rent/address/etc. — ask before web search."""
    cleaned = text.strip()
    if not is_proximity_query(cleaned):
        return False
    if _QUALIFIED_NEARBY.search(cleaned):
        return False
    subject = _subject_without_proximity(cleaned)
    if not subject:
        return False
    return _AMBIGUOUS_NEARBY_SUBJECT.search(subject) is not None


def is_vocab_quiz_answer(text: str, *, choices: tuple[tuple[str, str], ...] | None = None) -> bool:
    """Multiple-choice reply (A-D), including short phrases like 'Is it a?'."""
    from app.services.vocab_quiz import is_vocab_quiz_answer as _is_vocab_quiz_answer

    return _is_vocab_quiz_answer(text, choices=choices)


def _geo_is_active(*texts: str) -> bool:
    return any(is_geo_query(t.strip()) for t in texts if t and t.strip())


def _places_list_is_active(*texts: str) -> bool:
    return any(is_places_list_query(t.strip()) for t in texts if t and t.strip())


def format_location_not_set_answer() -> str:
    """No user location for a geo query — ask to enable location instead of guessing."""
    return (
        "I don't have your location yet, so I can't answer nearby or distance questions "
        "accurately.\n\n"
        "Turn on **Location** in **Settings** (or allow location when prompted), then ask again."
    )
