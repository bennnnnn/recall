"""Finalize pass for a money reply: the market note and the calculator card under it.

The ``calculator`` fence is the server's: one the model wrote is dropped on every turn,
and a money turn gets the one ``modules/money`` builds, with today's average when the
lookup that started with the turn found one. A stopped reply adds nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.chat.finalize_subjects import fallback_text
from app.modules.money.service import MoneyTurn, finish_money_reply
from app.services.md_fence_scan import strip_closed_fences

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

CALCULATOR_FENCE = "calculator"


async def attach_money_card(state: FinalizeState) -> str:
    text = state.text
    if CALCULATOR_FENCE in text:
        text = strip_closed_fences(text, CALCULATOR_FENCE).rstrip()
    turn = state.ctx.money
    if not isinstance(turn, MoneyTurn) or state.was_cancelled or state.user_stopped:
        return text
    text = await finish_money_reply(turn, text, state.settings)
    state.committed = fallback_text(text, server_text=state.server_text)
    return text
