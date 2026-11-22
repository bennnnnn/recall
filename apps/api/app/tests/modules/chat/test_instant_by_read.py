"""An instant reply the read says the message did not ask for gives way to the model (QA,
2026-11-22)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import Settings
from app.modules.chat.instant_by_read import instant_reply_by_read
from app.modules.chat.turn_decision import TurnDecision
from app.modules.web_search import LOCATION_ASK_OPENING

_SETTINGS = Settings(_env_file=None)  # type: ignore[call-arg]
_ASK = f"{LOCATION_ASK_OPENING}, so I can't answer that for where you are."


def _read(**fields: Any) -> asyncio.Task[TurnDecision | None]:
    decision = TurnDecision.model_validate(
        {"live": False, "subject": "everyday", "think": False, **fields}
    )

    async def answer() -> TurnDecision | None:
        return decision

    return asyncio.ensure_future(answer())


def _ctx(
    reply: str, read: asyncio.Task[TurnDecision | None] | None, verified: object = None
) -> Any:
    return SimpleNamespace(instant_reply=reply, live_read=read, verified_subject=verified)


@pytest.mark.asyncio
async def test_a_location_ask_goes_when_the_read_needs_no_live_facts() -> None:
    """ "you think it means I am sad?" after a dream got the canned location ask."""
    ctx = _ctx(_ASK, _read(follow="answer"))
    await instant_reply_by_read(ctx, _SETTINGS)
    assert ctx.instant_reply is None


@pytest.mark.asyncio
async def test_a_location_ask_stays_for_a_nearby_search() -> None:
    ctx = _ctx(_ASK, _read(live=True, query="pharmacy near me"))
    await instant_reply_by_read(ctx, _SETTINGS)
    assert ctx.instant_reply == _ASK


@pytest.mark.parametrize("follow", ["explain", "more"])
@pytest.mark.asyncio
async def test_a_verified_instant_reply_goes_when_it_is_asked_explained(follow: str) -> None:
    ctx = _ctx(
        "**Given** ... ```answer\nC = 62.80 cm\n```", _read(follow=follow), verified=object()
    )
    await instant_reply_by_read(ctx, _SETTINGS)
    assert ctx.instant_reply is None


@pytest.mark.asyncio
async def test_without_a_read_the_instant_reply_stands() -> None:
    ctx = _ctx(_ASK, None)
    await instant_reply_by_read(ctx, _SETTINGS)
    assert ctx.instant_reply == _ASK
    solved = _ctx("**Given** ...", _read(follow="none"), verified=object())
    await instant_reply_by_read(solved, _SETTINGS)
    assert solved.instant_reply == "**Given** ..."
