"""A clarify card in the chat history, and the turn that answers it (docs/clarify.md).

The model reads an earlier card as one line ("Asked: …"), not JSON it might copy. The
message right after a card is the user's picks (one "Label: pick" line per question,
written by the phone), a skip, or something typed instead: each gets the hint that says
what to answer now.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.chat.clarify_card import CLARIFY_FENCE, ClarifyCard, read_card
from app.modules.chat.prompt_constants.clarify import (
    CLARIFY_PICKS_AFTER_HINT,
    CLARIFY_PICKS_FIRST_HINT,
    CLARIFY_UNANSWERED_HINT,
)
from app.services.md_fence_scan import iter_fences


def card_in_reply(reply: str | None) -> ClarifyCard | None:
    """The card a saved reply ended on, or None."""
    if not reply or CLARIFY_FENCE not in reply:
        return None
    for fence in reversed(list(iter_fences(reply))):
        if fence.lang == CLARIFY_FENCE and fence.closed:
            return read_card(reply[fence.body_start : fence.body_end])
    return None


def follows_card(last_reply: str | None) -> bool:
    """The turn after a reply that asked with a card: it answers, it never asks again."""
    return card_in_reply(last_reply) is not None


def card_as_line(body: str) -> str:
    """An earlier card as the model reads it in history."""
    card = read_card(body)
    if card is None:
        return ""
    asked = "; ".join(f"{q.question} [{' / '.join(q.options)}]" for q in card.questions)
    return f"Asked: {asked}\n"


def answers_card(message: str, card: ClarifyCard) -> bool:
    """Every line is "Label: pick" for one of the card's labels: the phone sent the picks."""
    labels = {question.label.casefold() for question in card.questions}
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    if not lines:
        return False
    for line in lines:
        label, colon, pick = line.partition(":")
        if not colon or not pick.strip() or label.strip().casefold() not in labels:
            return False
    return True


def last_reply_card(prior: Sequence[tuple[str, str]] | None) -> ClarifyCard | None:
    """The card the conversation's last reply asked with, or None."""
    for role, content in reversed(prior or ()):
        if role == "assistant":
            return card_in_reply(content)
    return None


def clarify_reply_hint(query: str | None, prior: Sequence[tuple[str, str]] | None) -> str | None:
    """What this turn answers when the last reply asked with a card; None otherwise."""
    card = last_reply_card(prior)
    if card is None or not query or not query.strip():
        return None
    if answers_card(query, card):
        return CLARIFY_PICKS_FIRST_HINT if card.when == "first" else CLARIFY_PICKS_AFTER_HINT
    return CLARIFY_UNANSWERED_HINT
