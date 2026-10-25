"""A loan, card or savings question: the money module's block and card for this turn.

It runs beside the rest of the prompt's preparation. One request of a multi-part
message may be the money one; the first part that reads as money is used. A part may
also change the chat's last money request ("what if i only do 3 years instead"), which
the user's earlier lines in the turn's window give; the server works that one too.
"""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.aio import gather_or_cancel
from app.core.config import Settings
from app.modules.chat.prompt_inject import inject_before_last_user
from app.modules.chat.turn_plan import TurnPlan
from app.modules.chat.turn_prep.instant import settings_card
from app.modules.chat.turn_prep.mode import prior_user_texts
from app.modules.chat.turn_prep.request import TurnIdentity, TurnRequest
from app.modules.money.service import MoneyTurn, prepare_money_turn


async def money_turn(
    request: TurnRequest,
    identity: TurnIdentity,
    settings: Settings,
    redis: Redis,
    plan: TurnPlan,
) -> MoneyTurn | None:
    if not settings.money_enabled or request.has_image_attachment:
        return None
    earlier = prior_user_texts(request.recent_messages or [], request.content)
    for text in plan.texts() if plan.multi else (request.content,):
        turn = await prepare_money_turn(
            text,
            settings,
            redis,
            user=identity.user,
            location=identity.geo.user_location,
            earlier=earlier,
        )
        if turn is not None:
            return turn
    return None


def with_money_block(
    prompt_messages: list[dict[str, str]], turn: MoneyTurn | None
) -> list[dict[str, str]]:
    """The prompt with the money block before the last user message."""
    if turn is None:
        return prompt_messages
    return inject_before_last_user(prompt_messages, turn.block)


async def server_parts(
    request: TurnRequest, identity: TurnIdentity, settings: Settings, redis: Redis, plan: TurnPlan
) -> tuple[str | None, MoneyTurn | None]:
    """The server's own parts of the reply: a multi-part settings card, a money card."""
    card, money = await gather_or_cancel(
        settings_card(identity, settings, redis, plan),
        money_turn(request, identity, settings, redis, plan),
    )
    return card, money
