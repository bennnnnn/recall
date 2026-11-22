"""A money request read from the chat by a model, in any wording, over any number of lines.

The word rules (``read``, ``follow_up``, ``purchase``) read one line, or a change of the
line before, by a positive grammar, and leave everything else to the model. In one chat
(the owner's, 2026-11-22) a car of 40k, "The interest is 6", "Down payment is 20 percent"
and "72 months" came over five lines, and "What would be my exact monthly payment?" asked
for it: no rule read any of them, so the reply's model did the sums, and a "correction" it
made was wrong ($4,550.63 for $4,563.29). When the turn's read says the message is about
the user's money (``chat.turn_decision``: ``subject`` money), a model reads the chat and
writes the request down as it stands now: the product, whether a figure is asked, and each
value with the words that state it (``MoneyReading``). The server holds each value to those
words in the chat and works the numbers (``read_check``); the model never does a sum.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import Settings
from app.models.routing_lanes import ROUTING

logger = logging.getLogger(__name__)

ProductKey = Literal[
    "mortgage",
    "car",
    "student",
    "personal",
    "loan",
    "card",
    "savings",
    "investing",
    "afford",
    "none",
]
ValueName = Literal[
    "price",
    "down",
    "down_percent",
    "amount",
    "rate",
    "years",
    "months",
    "balance",
    "apr",
    "payment",
    "start",
    "deposit",
    "income",
    "monthly_income",
    "debts",
]
_PRODUCTS: tuple[str, ...] = get_args(ProductKey)
_NAMES: tuple[str, ...] = get_args(ValueName)

_MAX_TOKENS = 400
# The chat the read sees: the last messages, a user line whole up to its cap, a reply's
# start (its numbers are context; only a proposed amount is ever taken from one).
_MESSAGES = 12
_USER_CHARS = 400
_REPLY_CHARS = 500

PROMPT = (
    "You read a chat for an app that works out the user's own money: loans (a mortgage, a "
    "car, a student, a personal or any other loan), paying off a credit card, savings or "
    "investments growing, and how big a mortgage an income can afford. Read the user's "
    "last message against the chat before it and write down, as JSON, the money request "
    "it makes as the request stands now.\n"
    "\n"
    "calculate: true when the last message asks for a figure worked out from amounts (a "
    "monthly payment, a total, the interest, how long to pay off, what savings grow to, "
    "what mortgage or home they can afford), or gives or changes a value of a figure an "
    "earlier message asked for (a rate, a term, a down payment, a price), or asks why the "
    "app's calculator was not used for one. false for advice and opinions (whether a salary "
    "is good, whether to buy something, how much to spend or save), how loans or interest "
    "work, today's rates in general, a fact about the user's money with no figure asked, "
    "and anything else.\n"
    "product: mortgage (a home), car, student, personal, loan (any other loan), card (a "
    "credit card balance), savings, investing, afford (the user asks what mortgage or home "
    "price their income allows), or none.\n"
    "used: true only when the car bought is used (pre-owned, second-hand).\n"
    "plain: false when the request is not a fixed yearly rate with equal monthly payments "
    "or deposits (interest-only, a balloon, a deferment, simple interest, weekly or yearly "
    "payments, a rate per month), or when the last message compares options (two rates, "
    "two terms, two prices); otherwise true.\n"
    "values: each value the request uses, from anywhere in the chat, the latest one when "
    "the user changed it, one entry per name: name, value (a plain number: 40k is 40000, "
    "6% is 6), quote (the user's own words that state it, copied exactly from their "
    "message), from (user). Only an amount an assistant reply proposed, which the user "
    "asked it to choose or went on with, is quoted from that reply, with from assistant; "
    "never take a rate or a term from a reply. Names:\n"
    "- price: what the thing bought costs; down: money put down, as a sum; down_percent: "
    "money put down, as a percent of the price; amount: the sum borrowed, when the user "
    "names the loan itself\n"
    "- rate: the yearly interest rate, in percent\n"
    "- years or months: the term, in the unit the user said it in\n"
    "- balance, apr, payment: a credit card's balance, its APR and the monthly payment "
    "toward it\n"
    "- start, deposit: savings' starting amount and monthly deposit\n"
    "- for afford only: income (gross income a year) or monthly_income (a month's); "
    "debts (monthly payments on other debts, 0 when they say they have none); price (a "
    "home they ask about)\n"
    "Leave out every value nobody stated: never fill one in or estimate one (the app has "
    "its own defaults and today's average rates).\n"
    "\n"
    'Example: "User: thinking of buying a car for 30k" ... "User (last): rate is 5, 48 '
    'months, what\'s the payment?" -> {"calculate": true, "product": "car", "used": false, '
    '"plain": true, "values": [{"name": "price", "value": 30000, "quote": "30k", "from": '
    '"user"}, {"name": "rate", "value": 5, "quote": "rate is 5", "from": "user"}, {"name": '
    '"months", "value": 48, "quote": "48 months", "from": "user"}]}'
)


def _known(value: Any, choices: tuple[str, ...], default: str) -> str:
    text = str(value).strip().lower() if value is not None else ""
    return text if text in choices else default


class StatedValue(BaseModel):
    """One value of the request, with the chat's own words for it."""

    model_config = ConfigDict(populate_by_name=True)

    name: ValueName
    value: float = Field(allow_inf_nan=False)
    quote: str = Field(max_length=120)
    said_by: Literal["user", "assistant"] = Field(default="user", alias="from")

    @field_validator("said_by", mode="before")
    @classmethod
    def _said_by(cls, value: Any) -> str:
        return _known(value, ("user", "assistant"), "user")


class MoneyReading(BaseModel):
    """The money request the chat makes now, as a model reads it: a candidate only."""

    calculate: bool = False
    product: ProductKey = "none"
    used: bool = False
    plain: bool = True
    values: list[StatedValue] = Field(default_factory=list, max_length=14)

    @field_validator("product", mode="before")
    @classmethod
    def _product(cls, value: Any) -> str:
        return _known(value, _PRODUCTS, "none")

    @field_validator("values", mode="before")
    @classmethod
    def _values(cls, value: Any) -> Any:
        """Entries with a name the schema does not know are dropped, not the whole read."""
        if not isinstance(value, list):
            return value
        return [
            item
            for item in value
            if not isinstance(item, dict) or str(item.get("name", "")).strip().lower() in _NAMES
        ]


def chat_lines(conversation: list[tuple[str, str]], text: str) -> str:
    """The chat as the read sees it, the last message marked."""
    lines = []
    for role, content in conversation[-_MESSAGES:]:
        if role == "user":
            lines.append(f"User: {content[:_USER_CHARS]}")
        else:
            lines.append(f"Assistant: {content[:_REPLY_CHARS]}")
    lines.append(f"User (last): {text[:_USER_CHARS]}")
    return "\n".join(lines)


async def read_money_chat(
    settings: Settings,
    conversation: list[tuple[str, str]],
    text: str,
    *,
    model_alias: str | None = None,
) -> MoneyReading | None:
    """The model's reading of the chat's money request, or None when there is no read."""
    from app.core.redis import get_redis_client
    from app.gateways.structured_completion import complete_structured
    from app.services import quota as quota_service

    try:
        if await quota_service.global_spend_exceeded(get_redis_client(), settings):
            return None
        return await complete_structured(
            settings=settings,
            model_alias=model_alias or ROUTING.money_read,
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": chat_lines(conversation, text)},
            ],
            schema=MoneyReading,
            max_tokens=_MAX_TOKENS,
            timeout_seconds=settings.money_read_timeout_seconds,
            allow_fallback=False,
            quiet_timeout=True,
        )
    except Exception as exc:  # A read is a hint: any failure reads nothing.
        logger.info("money read failed (%s)", type(exc).__name__)
        return None
