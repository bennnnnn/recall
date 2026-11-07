"""Praise of the question ("Great question —", "Good question.") comes off a reply's start.

``NO_SELF_TALK_RULE`` asks for none; the free plan's model still opened "Great question —
here's how the factoring works" and "Good question. Here's the thinking" (2026-11-06). Only
the reply's first words, only the praise itself (a whole sentence, or a clause that a dash,
comma or colon ends), never inside a code fence, never the whole reply. "Good question to
ask your doctor: …" goes on with what the question is, so it stays.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

_PRAISE = re.compile(
    r"(?:(?:that|this)(?:'s| is) )?(?:a |such a |what a )?(?:really |very )?"
    r"(?:great|good|excellent|fantastic|interesting|smart|fair|brilliant|nice|awesome)"
    r" question(?: there)?(?:[!.]+\s*|\s*[\u2014\u2013:,-]+\s*)",
    re.IGNORECASE,
)


def strip_praise_opener(state: FinalizeState) -> str:
    """The finalize pass: a model reply loses a leading praise of the question."""
    if state.was_cancelled or state.server_text:
        return state.text
    return drop_praise_opener(state.text)


def drop_praise_opener(text: str) -> str:
    """``text`` without the praise its first line opens with, or unchanged."""
    lead = len(text) - len(text.lstrip())
    match = _PRAISE.match(text, lead)
    rest = text[match.end() :].lstrip() if match is not None else ""
    if not rest:
        return text
    return rest[0].upper() + rest[1:]
