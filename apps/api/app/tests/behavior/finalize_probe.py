"""A model reply saved through the real finalize on the real turn context its prompt builds:
for the finalize tests and the review probes (``app/tests/review``)."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from app.modules.chat.finalize_passes import enrich_final_content
from app.modules.chat.turn_deps import default_deps
from app.modules.chat.turn_outcome import TurnOutcome
from app.tests.behavior.cases import Case, Expect
from app.tests.behavior.harness import (
    _no_reminders,
    _no_session,
    battery_settings,
    offline_pubchem,
    route_case,
)


def _done(value: Any) -> asyncio.Future[Any]:
    future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    future.set_result(value)
    return future


async def finalize_reply(
    prompt: str,
    reply: str,
    *,
    history: tuple[tuple[str, str], ...] = (),
    formal: tuple[float, str, tuple[float, ...]] | None = None,
) -> tuple[Any, str]:
    """``reply`` as the model wrote it on ``prompt``'s turn, saved through every pass.

    ``formal``: the formal reader's answer (value, unit), as the physics read's task gives it
    (it needs a model, so it is stubbed here, with the live read saying physics).
    """
    route = await route_case(Case("probe", "probe", prompt, Expect(), "", history=history))
    ctx = route.context
    ctx.instant_reply = None  # the model wrote this reply
    if formal is not None:
        ctx.live_read = _done(SimpleNamespace(subject="physics"))
        ctx.formal = _done(_formal_answer(*formal))
    deps = replace(
        default_deps(),
        session_factory=_no_session,
        users=SimpleNamespace(get_by_id=AsyncMock(return_value=None)),
        todos=SimpleNamespace(materialize_reminder_fences=AsyncMock(side_effect=_no_reminders)),
    )
    with offline_pubchem():
        saved = await enrich_final_content(
            deps,
            AsyncMock(),
            battery_settings(),
            ctx,
            assistant_text=reply,
            usage={},
            outcome=TurnOutcome(),
            was_cancelled=False,
            should_cancel=None,
        )
    return route, saved


def _formal_answer(value: float, unit: str, uses: tuple[float, ...] = ()) -> Any:
    """The formal reader's answer: one part's value, with the range the standard constants
    allow and the stated numbers the value is worked from."""
    from app.services.formal.answer import FormalAnswer, FormalValue

    part = FormalValue(
        part="",
        symbol="",
        value=value,
        unit=unit,
        low=value * 0.997,
        high=value * 1.003,
        uses=uses,
    )
    return FormalAnswer(values=(part,))


def answer_cards(text: str) -> list[str]:
    from app.services.answer_fence import ANSWER_FENCE_LANGS
    from app.services.md_fence_scan import iter_fences

    return [
        text[fence.body_start : fence.body_end]
        for fence in iter_fences(text)
        if fence.closed and fence.lang in ANSWER_FENCE_LANGS
    ]
