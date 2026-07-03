"""Geo / proximity / distance query classification."""

from __future__ import annotations

import re

from app.services.web_search.patterns import (
    _AMBIGUOUS_NEARBY_SUBJECT,
    _BEST_NEAR,
    _DISTANCE_BETWEEN,
    _DISTANCE_INTENT,
    _FROM_USER,
    _IMPLICIT_LOCAL,
    _NEARBY_INTENT,
    _NON_GEOGRAPHIC_NEAREST,
    _PROXIMITY_PHRASES,
    _QUALIFIED_NEARBY,
    _QUIZ_ANSWER,
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
    if _NON_GEOGRAPHIC_NEAREST.search(cleaned):
        return False
    if _NEARBY_INTENT.search(cleaned):
        return True
    if _IMPLICIT_LOCAL.search(cleaned):
        return True
    return bool(_BEST_NEAR.search(cleaned) and "?" in cleaned)


def is_distance_query(text: str) -> bool:
    """Distance, travel time, or directions from the user's location."""
    cleaned = text.strip()
    if not cleaned or not _DISTANCE_INTENT.search(cleaned):
        return False
    if _DISTANCE_BETWEEN.search(cleaned) and not _FROM_USER.search(cleaned):
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


def is_vocab_quiz_answer(text: str) -> bool:
    """Single-letter multiple-choice reply (A–D) in an in-chat vocabulary quiz."""
    return bool(_QUIZ_ANSWER.match(text.strip()))


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
