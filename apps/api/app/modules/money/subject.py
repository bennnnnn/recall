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

    async def finish(self, turn: MoneyTurn, text: str, settings: Settings, *, english: bool) -> str:
        from app.modules.money.service import finish_money_reply

        return await finish_money_reply(turn, text, settings, english=english)

    def reads(self, text: str) -> bool:
        """``text`` is a money request this peer works (a loan, card payoff or savings):
        routing leaves it to the money card, never a subject's lane."""
        return _reads_money(text)

    def yields_to(self, subject: str | None) -> bool:
        """A line a science reads as its own problem is never a money request, whatever
        "car", "rate" or "40%" it holds: a screw jack lifting "a car weighing 9000 N" at
        "40%" efficiency got a car-loan card and a rate note (2026-11-18). Maths keeps its
        money lines: a card payoff reads as maths and is still the money card's."""
        return subject in _SCIENCES

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
    in the turn's pool read, never on the event loop (Gemini on #2489). A science's
    problem is none (``yields_to``), by the subject order's own read of it."""
    from app.modules.money.read import read_money_request
    from app.services.subjects.order import read_subject_reason

    if read_money_request(text) is None:
        return False
    read = read_subject_reason(text, False, True)
    return not MONEY_PEER.yields_to(None if read is None else read.subject)


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
