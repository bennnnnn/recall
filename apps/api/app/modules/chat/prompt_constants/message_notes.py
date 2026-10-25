"""What the latest message is, said beside it: a list of values, or "What?" at the last reply.

These sit nearest the user's turn (``prompt_sections.CONTEXT_SECTIONS``): a small model
follows the note closest to the message.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.chat.prompt_constants.reply_missed import reply_missed_hint
from app.modules.chat.prompt_constants.shared_numbers import shared_numbers_hint


def message_notes(query: str, prior: Sequence[tuple[str, str]]) -> list[str]:
    """The notes that apply to this message, in order."""
    notes = (shared_numbers_hint(query), reply_missed_hint(query, prior))
    return [note for note in notes if note]
