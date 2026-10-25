"""A money turn from message to card: read, look up today's average, work, write.

``prepare_money_turn`` runs while the prompt is built. It reads the request (or the
change a follow-up makes to the chat's last one, ``follow_up``) and starts the
average-rate lookup at once. The lookup is awaited before the prompt only when the
numbers need it (the user gave no rate, or asked what rates are); otherwise it runs while
the reply streams, and ``finish_money_reply`` collects it to write the note and the
card's marker. A lookup that is late or finds nothing leaves both out; the turn never
waits on it past a few seconds.

A kind of product priced apart (a used car) also starts the product's own lookup, which
stands in, said as such, when the kind's finds nothing in time: the first live used-car
ask (2026-10-25) found no used-car average and got no numbers, where main had worked it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace

from redis.asyncio import Redis

from app.core.background_tasks import create_background_task
from app.core.config import Settings
from app.models.orm import User
from app.modules.money.block import money_block
from app.modules.money.currencies import country_for, currency_for
from app.modules.money.fence import calculator_fence, card_values
from app.modules.money.follow_up import follow_up_request
from app.modules.money.note import market_note
from app.modules.money.rates import MarketRate, current_average
from app.modules.money.read import MoneyRequest, read_money_request
from app.modules.money.solve import Worked, rate_name, work

logger = logging.getLogger(__name__)

# Waited before the prompt only when the numbers need the average.
_PROMPT_WAIT_SECONDS = 5.0
# Waited after the reply streamed; the lookup started with the turn, so it is usually done.
_FINISH_WAIT_SECONDS = 3.0
# A stand-in that finished while the kind's lookup ran out its time is still taken.
_LAST_LOOK_SECONDS = 0.05


@dataclass
class MoneyTurn:
    """What a money turn carries from its prompt to its finalize."""

    request: MoneyRequest
    worked: Worked | None
    # Read before the last user message: numbers to copy, and what the app adds.
    block: str
    average: MarketRate | None
    lookup: asyncio.Task[MarketRate | None] | None
    # The product's own average, started beside a variant's (``Variant.stand_in``).
    stand_in: asyncio.Task[MarketRate | None] | None = None


async def prepare_money_turn(
    text: str,
    settings: Settings,
    redis: Redis | None,
    *,
    user: User | None,
    location: str | None,
    earlier: Sequence[str] = (),
    last_reply: str = "",
) -> MoneyTurn | None:
    """The money turn ``text`` asks for, or None when it is not one.

    ``earlier`` is the user's lines before it, oldest first: "what if 3 years instead"
    is the last request there with its term changed. ``last_reply`` is the reply before
    it, whose card shows the rate a follow-up is told about when its own rate differs.
    """
    if not settings.money_enabled:
        return None
    request = follow_up_request(text, earlier) or read_money_request(text)
    if request is None:
        return None
    # The card and the prompt use one currency: the one named, else the user's place's.
    request = replace(request, currency=currency_for(request.currency, location))
    product = request.product
    # A follow-up's average is read again for its own kind and term.
    term = request.values.get("years", request.values.get("months"))
    if term is None:
        term = product.defaults.get("years", product.defaults.get("months"))
    lookup = stand_in = None
    country = country_for(request.currency, location)
    if product.rate_lookup(request.variant) is not None:
        lookup = create_background_task(
            current_average(
                product, term, country, settings, redis, user=user, variant=request.variant
            ),
            name="money_average",
        )
    if product.variant(request.variant) is not None and product.lookup is not None:
        stand_in = create_background_task(
            current_average(product, term, country, settings, redis, user=user),
            name="money_average_stand_in",
        )
    average = None
    if lookup is not None and (request.rates_only or rate_name(product) not in request.values):
        average = await _average(request, lookup, stand_in, _PROMPT_WAIT_SECONDS)
    worked = None if request.rates_only else work(request, average.value if average else None)
    shown = card_values(last_reply).get(rate_name(product)) if request.changed else None
    block = money_block(request, worked, average, shown_rate=shown)
    return MoneyTurn(request, worked, block, average, lookup, stand_in)


async def finish_money_reply(turn: MoneyTurn, text: str, settings: Settings) -> str:
    """The reply with the market note and the calculator card under it."""
    if turn.worked is None:
        return text
    average = turn.average
    if average is None and turn.lookup is not None:
        average = await _average(turn.request, turn.lookup, turn.stand_in, _FINISH_WAIT_SECONDS)
    pieces = [text.rstrip()]
    note = market_note(turn.worked, average, settings.money_unrealistic_ratio)
    if note:
        pieces.append(note)
    card = calculator_fence(turn.worked, average, turn.request.currency)
    if card:
        pieces.append(card)
    return "\n\n".join(piece for piece in pieces if piece)


async def _average(
    request: MoneyRequest,
    lookup: asyncio.Task[MarketRate | None],
    stand_in: asyncio.Task[MarketRate | None] | None,
    seconds: float,
) -> MarketRate | None:
    """The kind's average within ``seconds``, else the product's own, said as standing in."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    found = await _collect(lookup, seconds)
    variant = request.product.variant(request.variant)
    if found is not None or stand_in is None or variant is None:
        return found
    plain = await _collect(stand_in, max(deadline - loop.time(), _LAST_LOOK_SECONDS))
    return replace(plain, caveat=variant.stand_in) if plain is not None else None


async def _collect(lookup: asyncio.Task[MarketRate | None], seconds: float) -> MarketRate | None:
    """The lookup's answer within ``seconds``; a late one keeps running to fill the cache."""
    try:
        return await asyncio.wait_for(asyncio.shield(lookup), timeout=seconds)
    except TimeoutError:
        return None
    except Exception:
        logger.info("money average lookup failed", exc_info=True)
        return None
