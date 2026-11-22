"""The one-line summary a worked reply closes on, after its answer cards: it stays.

"The painter used 12 gallons of white pigment, 8 gallons of linseed oil, …" after the last
card gathers every result in a sentence (owner, 2026-11-12: "it is actually good … it is
giving a summary"), and stays even when it only repeats the cards' numbers (owner,
2026-11-22). Two passes dropped it: the working check as a restatement of the cards, and a
subject's fence pass, which takes the model's card out and read the sentence left under
**Answer** as the answer itself (``tests/review/test_finalize_conflicts.py``, conflict 7).
"""

from __future__ import annotations

import re

from app.services.answer_fence import ANSWER_FENCE_LANGS
from app.services.md_fence_scan import iter_fences

# A sentence or two, short.
_SUMMARY_MOST_WORDS = 40
_SENTENCE_END = re.compile(r"[.!?](?:\s|$)")
# A piece that opens with a part's label, a heading or a list item is no summary.
_LABELLED = re.compile(r"^\s*(?:\*\*\s*)?\(?[a-h][).]|^\s*(?:#|[-*+]\s|\d+[.)]\s)")


def is_one_line_summary(piece: str) -> bool:
    """``piece`` is one short line of a sentence or two: no list, heading or display maths."""
    text = piece.strip()
    return (
        bool(text)
        and "\n" not in text
        and "$$" not in text
        and len(text.split()) <= _SUMMARY_MOST_WORDS
        and len(_SENTENCE_END.findall(text)) <= 2
        and not _LABELLED.match(text)
    )


def closing_summary(text: str) -> str | None:
    """The one-line summary after the reply's last answer card, when that is all that
    follows it; None otherwise."""
    cards = [fence for fence in iter_fences(text) if fence.lang in ANSWER_FENCE_LANGS]
    if not cards or not cards[-1].closed:
        return None
    tail = text[cards[-1].end :].strip()
    return tail if is_one_line_summary(tail) else None


def with_closing_summary(text: str, summary: str | None) -> str:
    """``text`` closing on ``summary`` after its last card, when a pass took it out."""
    if not summary or summary in text:
        return text
    cards = [fence for fence in iter_fences(text) if fence.lang in ANSWER_FENCE_LANGS]
    if not cards or not cards[-1].closed:
        return text
    end = cards[-1].end
    rest = text[end:]
    return f"{text[:end].rstrip()}\n\n{summary}" + (
        f"\n\n{rest.lstrip()}" if rest.strip() else "\n"
    )
