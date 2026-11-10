"""Context hints a turn's prompt sections place: where the user is, what the turn may
look up, and the time, memory, files and schedule loaded for it (``prompt_sections``)."""

from __future__ import annotations

from typing import Protocol

from app.core.config import Settings
from app.models.orm import User
from app.modules import web_search as web_search_service
from app.modules.chat.prompt_constants import PHOTO_LOOKUP_HINT
from app.modules.chat.prompt_profile import USE_THE_LOCATION
from app.modules.chat.turn_prep.saved_place import profile_place
from app.services import time_context as time_context_service
from app.services.prompt_safety import wrap_saved_memory, wrap_untrusted


def _geo_hints(query_text: str | None, prompt_location: str | None) -> list[str]:
    """Layout and location for a nearby, distance or local-weather question."""
    if not query_text:
        return []
    parts: list[str] = []
    if web_search_service.is_ambiguous_local_places_query(query_text):
        parts.append(web_search_service.AMBIGUOUS_NEARBY_HINT)
    elif web_search_service.is_places_list_query(query_text):
        parts.append(web_search_service.LOCAL_PLACES_FORMAT_HINT)
    elif web_search_service.is_distance_query(query_text):
        parts.append(web_search_service.GEO_DISTANCE_HINT)
    if prompt_location and web_search_service.is_geo_query(query_text):
        parts.append(web_search_service.GEO_ACTIVE_LOCATION_HINT)
    return parts


class SlimTurn(Protocol):
    """What a slim turn's location line reads (``prompt_sections.PromptTurn``)."""

    @property
    def settings(self) -> Settings: ...
    @property
    def query_text(self) -> str | None: ...
    @property
    def prompt_location(self) -> str | None: ...
    @property
    def user(self) -> User: ...
    @property
    def local_tz(self) -> str: ...
    @property
    def lightweight(self) -> bool: ...
    @property
    def minimal_personal_context(self) -> bool: ...


def slim_geo_hints(turn: SlimTurn) -> list[str]:
    """A slim turn has no profile block, so it states where the user is whenever Location
    gives a place (the turn's fix, else the saved one), whatever the message's wording
    (``USE_THE_LOCATION``). A greeting and a "who am I" turn, which share no profile detail,
    state it only when they ask about a place; the places layout hints go with that too."""
    query = turn.query_text
    asks_place = bool(
        turn.settings.web_search_enabled and query and web_search_service.is_geo_query(query)
    )
    if not asks_place and (turn.lightweight or turn.minimal_personal_context):
        return []
    location = turn.prompt_location or profile_place(turn.user, turn.local_tz)
    parts = [f"The user's location: {location}. {USE_THE_LOCATION}"] if location else []
    return parts + (_geo_hints(query, turn.prompt_location) if asks_place else [])


def lookup_hints(settings: Settings) -> list[str]:
    """What a rich turn may look up: the web and real photos. Fixed text, one per flag."""
    parts: list[str] = []
    if settings.web_search_enabled:
        parts.append(web_search_service.WEB_SEARCH_HINT)
    if settings.image_search_enabled:
        parts.append(PHOTO_LOOKUP_HINT)
    return parts


def integration_hints(
    *,
    settings: Settings,
    query_text: str | None,
    local_tz: str,
    user_locale: str | None,
    location_for_context: str | None,
    prompt_location: str | None,
    memory_block: str,
    attachment_rag_block: str,
    todos_section: str | None,
    chat_history_rag_block: str = "",
) -> list[str]:
    """Time / place / memory / todos context (the summary and ``lookup_hints`` are
    their own sections)."""
    parts: list[str] = [
        time_context_service.format_time_context(local_tz, user_locale, location_for_context)
    ]
    if settings.web_search_enabled:
        parts.extend(_geo_hints(query_text, prompt_location))
    if memory_block:
        parts.append(wrap_saved_memory(memory_block))
    if attachment_rag_block:
        parts.append(attachment_rag_block)
    if todos_section:
        parts.append(wrap_untrusted("schedule", todos_section, first_party=True))
    if chat_history_rag_block:
        parts.append(chat_history_rag_block)
    return parts
