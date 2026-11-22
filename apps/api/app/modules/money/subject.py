"""Money as the subject registry names it beside the subjects (``services/subjects/registry``).

A money turn is no SymPy solve: its numbers are worked before the prompt (``prepare``) and its
calculator card lands after the reply (``finish``). The service is imported when a turn asks:
it loads the web search and the database models, which a SymPy pool worker that loads the
registry must not.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, TypeGuard

from app.core.readings import reading

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from app.core.config import Settings
    from app.models.orm import User
    from app.modules.money.catalog import Product
    from app.modules.money.service import MoneyTurn


@dataclass(frozen=True)
class MoneyPeer:
    async def prepare(
        self,
        text: str,
        settings: Settings,
        redis: Redis | None,
        *,
        user: User | None,
        location: str | None,
        earlier: Sequence[str | Sequence[str]],
        last_reply: str,
    ) -> MoneyTurn | None:
        from app.modules.money.service import prepare_money_turn

        return await prepare_money_turn(
            text,
            settings,
            redis,
            user=user,
            location=location,
            earlier=earlier,
            last_reply=last_reply,
        )

    async def prepare_standing(
        self,
        text: str,
        settings: Settings,
        redis: Redis | None,
        *,
        user: User | None,
        location: str | None,
        earlier: Sequence[str | Sequence[str]],
        last_reply: str,
    ) -> MoneyTurn | None:
        from app.modules.money.service import prepare_standing_turn

        return await prepare_standing_turn(
            text,
            settings,
            redis,
            user=user,
            location=location,
            earlier=earlier,
            last_reply=last_reply,
        )

    async def prepare_read(
        self,
        text: str,
        settings: Settings,
        redis: Redis | None,
        *,
        user: User | None,
        location: str | None,
        conversation: Sequence[tuple[str, str]],
    ) -> MoneyTurn | None:
        from app.modules.money.service import prepare_read_turn

        return await prepare_read_turn(
            text, settings, redis, user=user, location=location, conversation=conversation
        )

    async def finish(self, turn: MoneyTurn, text: str, settings: Settings, *, english: bool) -> str:
        from app.modules.money.service import finish_money_reply

        return await finish_money_reply(turn, text, settings, english=english)

    def reads(self, text: str) -> bool:
        """``text`` is a money request this peer works (a loan, card payoff or savings):
        routing leaves it to the money card, never a subject's lane."""
        return _reads_money(text)

    def yields_to(self, text: str, subject: str | None) -> bool:
        """``text``, read as ``subject``'s problem, is a science's and never a money request,
        unless it names money outright (a currency, a loan, an APR) or names its product by
        the product's own words ("save", "car loan"), not only by what a loan buys ("a car").
        A screw jack lifting "a car weighing 9000 N" at "40%" efficiency got a car-loan card
        and a rate note (2026-11-18), while "$3,000 at 18% APR ... how long until it is paid
        off?" and "I save 300 a month at 5%", which physics reads too, are the card's.
        Maths keeps its money lines. The text is read in the turn's pool (``_names_no_money``),
        never on the event loop (Gemini on #2495)."""
        return subject in _SCIENCES and _names_no_money(text)

    def names_currency(self, unit: str) -> bool:
        """``unit`` is money: a currency sign ($, €, ₹) or word (dollars, USD, cents). A
        sum of money is exact as written, never rounded as a measurement is. A word that
        is also a unit of measure ("pounds", a force or a mass) is the measure's (Claude
        on #2489): a physics unit is read as physics."""
        return _names_currency(unit)

    def owns(self, value: object) -> TypeGuard[MoneyTurn]:
        from app.modules.money.service import MoneyTurn

        return isinstance(value, MoneyTurn)


_SCIENCES = frozenset({"physics", "chemistry"})

MONEY_PEER = MoneyPeer()


@reading(declined=False)
@lru_cache(maxsize=128)
def _reads_money(text: str) -> bool:
    """Whether ``text`` is a money request: a reading, so routing's ask of it is answered
    in the turn's pool read, never on the event loop (Gemini on #2489)."""
    from app.modules.money.read import read_money_request

    return read_money_request(text) is not None


@reading(declined=False)
@lru_cache(maxsize=128)
def _names_no_money(text: str) -> bool:
    """``text`` names no money: no currency, loan or APR, and no product by its own words. A
    reading, read with the turn's message in the pool (``ask_turn_readings``)."""
    from app.modules.money.read import read_money_request
    from app.modules.money.sums import NAMES_MONEY

    if NAMES_MONEY.search(text) is not None:
        return False
    request = read_money_request(text)
    return request is None or not _names_its_product(text, request.product)


def _names_its_product(text: str, product: Product) -> bool:
    """``text`` names ``product`` by its own words ("car loan", "save"), not only by the goods
    a loan buys ("car", "truck")."""
    import re

    return any(
        re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text, re.IGNORECASE)
        for word in product.words
        if word not in product.goods
    )


def _names_currency(unit: str) -> bool:
    import re
    import unicodedata

    from pint.errors import UndefinedUnitError

    from app.modules.money.phrases import CURRENCY_WORDS
    from app.services.units import get_unit_registry

    if any(unicodedata.category(mark) == "Sc" for mark in unit):
        return True
    word = re.search(rf"\b(?:{CURRENCY_WORDS}|cents?|pence)\b", unit, re.I)
    if word is None:
        return False
    try:
        get_unit_registry().parse_units(word.group(0).lower())
    except UndefinedUnitError:
        return True  # no unit of measure: the currency's
    return False
