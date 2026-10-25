"""What the latest message is, said beside it: a list of values, "What?" at the last reply,
and the language it is written in.

These sit nearest the user's turn (``prompt_sections.CONTEXT_SECTIONS``): a small model
follows the note closest to the message. A lesson, its outline and a clarify card read
"I don't get it" their own way (a new explanation under the lesson's title, the request
answered now), so the "say it again" note stays out of them.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.modules.chat.clarify_turn import clarify_reply_hint
from app.modules.chat.continuation_subject import exchange_pairs
from app.modules.chat.prompt_constants.lesson_flow import active_lesson_step, outline_awaits_pick
from app.modules.chat.prompt_constants.reply_missed import reply_missed_hint
from app.modules.chat.prompt_constants.shared_numbers import shared_numbers_hint
from app.modules.chat.reply_language import reply_language_hint


def _own_way(query: str, exchange: list[Any], pairs: Sequence[tuple[str, str]]) -> bool:
    """A lesson, an outline awaiting a pick, or the turn after a clarify card."""
    if active_lesson_step(exchange) or outline_awaits_pick(exchange):
        return True
    return clarify_reply_hint(query, pairs) is not None


def message_notes(query: str, exchange: list[Any], user: Any) -> list[str]:
    """The notes that apply to this message, in order; its language last, nearest it."""
    pairs = exchange_pairs(exchange)
    missed = None if _own_way(query, exchange, pairs) else reply_missed_hint(query, pairs)
    language = reply_language_hint(query, pairs, user.locale, user.custom_instructions)
    return [note for note in (shared_numbers_hint(query), missed, language) if note]
