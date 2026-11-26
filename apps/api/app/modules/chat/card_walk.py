"""The reply's answer cards, walked one way by every finalize pass that reads them.

Six passes (the card numbers, a card held to its working, a card held to the server's
value, the rounding on the working's last line, the lead and the tail around the cards)
each walked the fences themselves, and disagreed on what a card is: four took only closed
fences, the lead and tail passes any ``answer``/``result``/``final`` fence, open or not
(audit, 2026-11-25).

A card is a closed answer fence, or the last fence of the reply left open to its end: the
closer (``finalize_text.close_open_fences``) closes that one, so a pass before the closer
and a pass after it see the same cards. A fence left open with another fence after it is
never closed, and is no card.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from app.services.answer_fence import ANSWER_FENCE_LANGS
from app.services.md_fence_scan import Fence, iter_fences


@dataclass(frozen=True)
class AnswerCard:
    """One card and where the text above it starts."""

    fence: Fence
    # The end of the card before it (0 for the first): the card's part of the reply.
    since_card: int
    # The end of the fence of any kind before it: the working that leads straight to it.
    since_fence: int

    def body(self, text: str) -> str:
        return text[self.fence.body_start : self.fence.body_end]


def is_card(fence: Fence, text: str) -> bool:
    """An answer fence that is closed, or open to the reply's end (the closer closes it)."""
    return fence.lang in ANSWER_FENCE_LANGS and (fence.closed or fence.end == len(text))


def answer_cards(text: str) -> Iterator[AnswerCard]:
    """Every card of ``text`` in order (the module docstring)."""
    since_card = since_fence = 0
    for fence in iter_fences(text):
        if is_card(fence, text):
            yield AnswerCard(fence, since_card, since_fence)
            since_card = fence.end
        since_fence = fence.end


def cards_text(text: str) -> str:
    """Every card's body, one after another."""
    return "\n".join(card.body(text) for card in answer_cards(text))
