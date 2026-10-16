"""Finalize passes over the reply's photo, source chips, layout and clock.

``chat/finalize_passes.py`` lists these passes in order. The photo and source
passes commit the text: ``done`` already carries what they added, so a later
failure keeps it.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.modules.chat.finalize_subjects import fallback_text
from app.modules.chat.presentation import drop_orphan_leading_answer, present_assistant_markdown
from app.modules.chat.prose_normalizer import (
    normalize_prose_artifacts,
    prose_changed,
    strip_unrequested_recipient_placeholders,
)
from app.modules.images.answer_photo import strip_photo_fences
from app.services.md_fence_scan import close_unclosed_fences
from app.services.mermaid_sanitize import sanitize_mermaid_fences
from app.services.places_fence import sanitize_places_fences
from app.services.time_context import (
    correct_weekday_dates,
    format_shown_clock_answer,
    model_denies_clock,
)

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState


async def attach_answer_photo(state: FinalizeState) -> str:
    """Swap the reply's ```photo fence for the photo found while it streamed.

    A linked photo commits the text, so a later failure keeps its marker.
    """
    ctx = state.ctx
    photo = ctx.answer_photo
    if photo is None or state.was_cancelled:
        if photo is not None:
            photo.cancel()
        return strip_photo_fences(state.text)
    text, ctx.answer_photo_ids = await photo.attach(state.text)
    if ctx.answer_photo_ids:
        state.committed = fallback_text(text, server_text=state.server_text)
    return text


def add_search_sources(state: FinalizeState) -> str:
    """Source chips for a searched turn, and the places card for a local search."""
    ctx = state.ctx
    text = state.text
    if not ctx.search_sources:
        return text
    web_search = state.deps.web_search
    text = web_search.strip_sources_from_text(text)
    if state.result is not None:
        state.result["search_sources"] = json.dumps(web_search.sources_payload(ctx.search_sources))
    sources_fence = web_search.format_sources_fence(ctx.search_sources)
    if sources_fence and not (state.should_cancel and state.should_cancel()):
        text = f"{text}{sources_fence}".strip()
    if ctx.local_places and "```places" not in text.lower():
        text = web_search.strip_duplicate_venue_list(text)
        places_fence = web_search.format_places_fence(ctx.search_sources)
        if places_fence and not (state.should_cancel and state.should_cancel()):
            state.assistant_parts[:] = [text] if text.strip() else []
            state.assistant_parts.append(places_fence)
            text = "".join(state.assistant_parts).strip()
    state.committed = text  # done already carries these chips
    return text


def record_instant_usage(state: FinalizeState) -> str:
    """An instant reply used no model: its usage is zero, not missing."""
    if state.ctx.instant_reply and not state.usage:
        state.usage["output"] = 0
        state.usage["input"] = 0
    return state.text


def close_open_fences(state: FinalizeState) -> str:
    """A provider can report a normal finish while still omitting a fence
    closer. Always repair odd fence parity so settled rendering never leaves raw
    backticks or an open streaming-style block behind."""
    return close_unclosed_fences(state.text)


def strip_recipient_placeholders(state: FinalizeState) -> str:
    return strip_unrequested_recipient_placeholders(state.text, state.ctx.user_message_content)


def normalize_prose(state: FinalizeState) -> str:
    """Prose artifact cleanup, after the fence passes so it never interferes with
    fence parsing: orphan colon lines go and 3+ blank lines collapse."""
    normalized = normalize_prose_artifacts(state.text)
    return normalized if prose_changed(state.text, normalized) else state.text


def sanitize_fences(state: FinalizeState) -> str:
    return sanitize_places_fences(sanitize_mermaid_fences(state.text))


def present_markdown(state: FinalizeState) -> str:
    return drop_orphan_leading_answer(
        present_assistant_markdown(state.text), state.ctx.user_message_content
    )


def fix_clock(state: FinalizeState) -> str:
    """A reply that says it cannot see the clock gets the clock, and a date's
    weekday is corrected."""
    ctx = state.ctx
    text = state.text
    if model_denies_clock(text):
        locale = ctx.user.locale if ctx.user is not None else None
        text = format_shown_clock_answer(ctx.user_timezone, locale)
    return correct_weekday_dates(text)
