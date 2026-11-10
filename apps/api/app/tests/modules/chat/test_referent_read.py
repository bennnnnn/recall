"""What "it" is: a fast model's pick of an earlier message (``chat.referent_read``)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.modules.chat import referent_read
from app.modules.chat.referent_read import Referent, ReferentPick, read_referent

_TRIANGLE_CHAT = [
    ("user", "Differentiate sin(x^2)cos(x^2)"),
    ("assistant", "2x cos(2x^2)"),
    ("user", "Triangle are with sides 5, 4,"),
    ("assistant", "What's the third side length? 🔺"),
    ("user", "3"),
    ("assistant", "Sides 3, 4 and 5 make a right triangle."),
    ("user", "The area"),
    ("assistant", "6 square units."),
    ("user", "Do it properly"),
    ("assistant", "Area = 6."),
    ("user", "Draw it"),
]


def _rows(pairs: list[tuple[str, str]]) -> list[SimpleNamespace]:
    return [SimpleNamespace(role=role, content=content) for role, content in pairs]


async def _read(
    line: str, rows: list[Any], pick: ReferentPick | None
) -> tuple[Referent | None, AsyncMock]:
    model = AsyncMock(return_value=pick)
    with patch.object(referent_read, "pick_referent", model):
        return await read_referent(Settings(), line, rows), model


@pytest.mark.parametrize("message", [2, 3, 4])
@pytest.mark.asyncio
async def test_draw_it_is_the_problem_the_model_names_whole(message: int) -> None:
    """Whichever piece of the triangle the model names, it is drawn with all three sides."""
    referent, model = await _read("Draw it", _rows(_TRIANGLE_CHAT), ReferentPick(message=message))
    assert referent == Referent("Triangle are with sides 5, 4, 3")
    assert model.await_args is not None
    conversation = model.await_args.args[2]
    assert "[1] User: Differentiate sin(x^2)cos(x^2)" in conversation
    assert "Draw it" not in conversation  # the turn's own line is the latest message


@pytest.mark.asyncio
async def test_none_and_no_read_are_told_apart() -> None:
    rows = _rows(_TRIANGLE_CHAT)
    assert (await _read("Draw it", rows, ReferentPick(message=None)))[0] == Referent(None)
    # A failed, mocked or late read, and a pick out of range: answered as before.
    assert (await _read("Draw it", rows, None))[0] is None
    assert (await _read("Draw it", rows, ReferentPick(message=9)))[0] is None


@pytest.mark.parametrize(
    "line",
    ["what is the domain?", "give me that", "send me that", "show me how", "画出来", "wow"],
)
@pytest.mark.asyncio
async def test_a_line_that_asks_to_see_nothing_is_not_read(line: str) -> None:
    referent, model = await _read(line, _rows(_TRIANGLE_CHAT[:-1]), ReferentPick(message=1))
    assert referent is None
    model.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_read_off_or_with_no_earlier_line_asks_no_model() -> None:
    model = AsyncMock(return_value=ReferentPick(message=1))
    with patch.object(referent_read, "pick_referent", model):
        assert await read_referent(Settings(referent_read_enabled=False), "draw it", []) is None
        assert await read_referent(Settings(), "draw it", _rows([("user", "draw it")])) is None
    model.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_slow_model_leaves_the_turn_as_before() -> None:
    """The read's own deadline: past it there is no read, and the turn is read as main did."""
    settings = Settings(referent_read_timeout_seconds=0.01, mock_llm_enabled=False)
    with (
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False)),
        patch("app.core.redis.get_redis_client", lambda: None),
        patch(
            "app.gateways.structured_completion.complete_structured",
            AsyncMock(side_effect=TimeoutError),
        ),
    ):
        assert await read_referent(settings, "Draw it", _rows(_TRIANGLE_CHAT)) is None
