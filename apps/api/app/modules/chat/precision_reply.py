"""A message that asks only a precision: the answer before it, rounded again by the server.

After a card of v = 3.13 m/s the user wrote "1 digit". The model answered "3.1 m/s — one
digit, as ordered: 3 m/s. (Mind, that's the rounded-down version; 3.13 m/s is the truer
figure.)": two answers, and a hedge (the owner's chat, 2026-11-20). The card's number is the
server's to show (``rounding_rule``), so a precision said on its own ("1 digit", "2 sig
figs", "no rounding") is answered with the last reply's cards again, each number shown by
that precision from the working's unrounded value (``card_numbers.cards_again``): one card
per answer, and no model call. A card that cannot show it honestly leaves the turn to the
model.
"""

from __future__ import annotations

from app.modules.chat.card_numbers import cards_again
from app.services.rounding_rule import precision_only


def rounded_again(content: str, prior_reply: str | None) -> str | None:
    """The prior reply's answer cards in the precision ``content`` alone asks for, or None."""
    precision = precision_only(content)
    if precision is None or not prior_reply:
        return None
    cards = cards_again(prior_reply, precision)
    if cards is None:
        return None
    if len(cards) == 1:
        return cards[0][1]
    # Each part's card under its own heading: three bare tensions name no place.
    return "\n\n".join(f"{heading}\n\n{card}" if heading else card for heading, card in cards)
