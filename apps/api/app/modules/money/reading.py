"""The money request a turn's words make, read once a turn and never on the event loop.

A money turn asks what request its line makes (a change to the chat's last request, a request
of its own, or a price and a rate for what the line before buys) and, when it makes none, the
chat's last request still standing. Both read the user's earlier lines too, each with every
reader of a money request, so a turn read the same words three times and more, on the event
loop (audit, 2026-11-25). These are readings (``core.readings``): the SymPy pool reads them
with the turn's message (``MoneyPeer.read_requests``, asked by ``ask_turn_readings``), and a
line it did not read is read in the pool when the turn asks (``read_aside``). The workers
import this module: it imports nothing but the readers.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.core.readings import reading
from app.modules.money.follow_up import as_parts, follow_up_request, standing_request
from app.modules.money.purchase import purchase_request
from app.modules.money.read import MoneyRequest, read_money_request

# The user's lines a request reads back over: a follow-up's three, the line before the oldest
# (what its bare amount buys), and one more for the request a standing talk goes on about.
EARLIER_LINES = 5

Earlier = tuple[tuple[str, ...], ...]


def earlier_parts(earlier: Sequence[str | Sequence[str]]) -> Earlier:
    """The user's last lines, oldest first, each as the parts its turn read it in: the key the
    turn's readings keep a request under."""
    return tuple(as_parts(line) for line in earlier[-EARLIER_LINES:])


@reading(declined=None)
def request_of(text: str, earlier: Earlier) -> MoneyRequest | None:
    """The money request ``text`` makes after the user's ``earlier`` lines, or None."""
    before = earlier[-1] if earlier else ()
    return (
        follow_up_request(text, earlier)
        or read_money_request(text)
        or purchase_request(text, before)
    )


@reading(declined=None)
def standing_of(earlier: Earlier) -> MoneyRequest | None:
    """The chat's last money request in the user's ``earlier`` lines, with its changes made."""
    return standing_request(earlier)


def read_requests(texts: Sequence[str], earlier: Sequence[str | Sequence[str]]) -> None:
    """Read, in a pool worker, every request a money turn will ask of these words."""
    parts = earlier_parts(earlier)
    for text in texts:
        request_of(text, parts)
    standing_of(parts)
