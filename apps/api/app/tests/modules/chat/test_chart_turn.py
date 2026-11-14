"""A chart of the user's own numbers is drawn by the server beside the reply and put in its
place (owner decision, 2026-11-13): the model's Vega spec carried numbers nobody checked."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import User
from app.modules.charts import read as chart_read
from app.modules.charts.request import ChartPoint, ChartRequest
from app.modules.chat import chart_turn
from app.modules.chat.chart_turn import attach_chart, start_chart
from app.modules.chat.finalize_passes import FINALIZE_PASSES, FinalizeState
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import StreamContext
from app.tests.modules.chat.chat_test_support import turn_deps

_LINE = "Make a bar chart of my spending: rent 1200, food 400, transport 150"
_MODEL_CHART = (
    '```chart\n{"data":{"values":[{"item":"rent","amount":1300},{"item":"food","amount":400}]},'
    '"mark":"bar","encoding":{"x":{"field":"amount","type":"quantitative"},'
    '"y":{"field":"item","type":"nominal"}}}\n```'
)
_READING = ChartRequest(
    kind="bar",
    points=[
        ChartPoint(label="rent", value="1200"),
        ChartPoint(label="food", value="400"),
        ChartPoint(label="transport", value="150"),
    ],
)


def _settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def _ctx(line: str = _LINE, **fields: Any) -> StreamContext:
    user = User(id=uuid4(), name="Bini", plan="pro", locale="en")
    ctx = StreamContext(
        user_id=user.id,
        chat_id=uuid4(),
        model="smart-chat",
        prompt_messages=[{"role": "user", "content": line}],
        run_title=False,
        user_message_content=line,
        reserved_tokens=0,
        max_output_tokens=0,
        user_timezone="UTC",
        user=user,
    )
    for name, value in fields.items():
        setattr(ctx, name, value)
    return ctx


def _state(ctx: StreamContext, text: str, settings: Settings | None = None) -> FinalizeState:
    return FinalizeState(
        deps=turn_deps(),
        settings=settings or _settings(),
        ctx=ctx,
        raw=text,
        text=text,
        usage={},
        outcome=TurnOutcome(),
        was_cancelled=False,
        should_cancel=None,
    )


def _drawn() -> str:
    fence = chart_read.chart_from_request(_READING, _LINE)
    assert fence is not None
    return fence


async def _done(value: str | None) -> str | None:
    return value


@pytest.mark.asyncio
async def test_the_servers_chart_takes_the_model_charts_place() -> None:
    ctx = _ctx(chart=asyncio.ensure_future(_done(_drawn())))
    text = await attach_chart(_state(ctx, f"Here it is:\n\n{_MODEL_CHART}\n\nRent is the most."))
    assert _drawn() in text and "1300" not in text
    assert text.startswith("Here it is:") and text.rstrip().endswith("Rent is the most.")


@pytest.mark.asyncio
async def test_a_reply_with_no_chart_gets_the_servers_under_it() -> None:
    ctx = _ctx(chart=asyncio.ensure_future(_done(_drawn())))
    text = await attach_chart(_state(ctx, "Rent is most of your spending."))
    assert text == f"Rent is most of your spending.\n\n{_drawn()}\n"


@pytest.mark.asyncio
async def test_a_chart_late_past_the_wait_leaves_only_a_checked_model_chart() -> None:
    """The wait runs out: the model's chart is held to the same check, and its rent of 1300
    (the user wrote 1200) is no picture at all."""

    async def slow() -> str | None:
        await asyncio.sleep(30)
        return _drawn()

    task = asyncio.ensure_future(slow())
    ctx = _ctx(chart=task)
    text = await attach_chart(
        _state(ctx, f"Chart:\n\n{_MODEL_CHART}", _settings(chart_wait_seconds=0.01))
    )
    await asyncio.sleep(0)
    assert task.cancelled()
    assert "```chart" not in text and "Chart:" in text


@pytest.mark.asyncio
async def test_a_failed_chart_is_no_chart() -> None:
    async def fails() -> str | None:
        raise RuntimeError("down")

    ctx = _ctx(chart=asyncio.ensure_future(fails()))
    assert await attach_chart(_state(ctx, "Rent is the most.")) == "Rent is the most."


@pytest.mark.asyncio
async def test_a_stopped_reply_stops_the_chart() -> None:
    task = asyncio.ensure_future(asyncio.sleep(30))
    ctx = _ctx(chart=task)
    state = _state(ctx, "Rent")
    state.was_cancelled = True
    assert await attach_chart(state) == "Rent"
    await asyncio.sleep(0)
    assert task.cancelled()


@pytest.mark.asyncio
async def test_a_turn_with_no_chart_is_left_alone() -> None:
    assert await attach_chart(_state(_ctx(), f"x {_MODEL_CHART}")) == f"x {_MODEL_CHART}"


@pytest.mark.asyncio
async def test_start_chart_reads_only_a_chart_of_the_users_numbers() -> None:
    draw = AsyncMock(return_value=None)
    with patch.object(chart_turn, "draw_chart", draw):
        started = start_chart(_settings(), _ctx())
        assert started is not None
        await started
        assert draw.await_args is not None and draw.await_args.kwargs["named"] == "bar"
        assert start_chart(_settings(), _ctx("Plot y = 2x + 3")) is None
        assert (
            start_chart(_settings(), _ctx("Make a scatter plot of x: 1, 2, 3 and y: 4, 5, 6"))
            is None
        )
        assert start_chart(_settings(data_charts_enabled=False), _ctx()) is None
        assert start_chart(_settings(), _ctx(instant_reply="4")) is None


@pytest.mark.asyncio
async def test_a_failed_read_draws_nothing() -> None:
    with (
        patch(
            "app.gateways.structured_completion.complete_structured",
            AsyncMock(side_effect=RuntimeError("down")),
        ),
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False)),
        patch("app.core.redis.get_redis_client", lambda: object()),
    ):
        assert await chart_read.draw_chart(_LINE, _LINE, _settings()) is None


@pytest.mark.asyncio
async def test_a_read_past_the_spend_cap_draws_nothing() -> None:
    ask = AsyncMock()
    with (
        patch("app.gateways.structured_completion.complete_structured", ask),
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=True)),
        patch("app.core.redis.get_redis_client", lambda: object()),
    ):
        assert await chart_read.draw_chart(_LINE, _LINE, _settings()) is None
    ask.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_read_draws_its_checked_chart() -> None:
    with (
        patch(
            "app.gateways.structured_completion.complete_structured",
            AsyncMock(return_value=_READING),
        ),
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False)),
        patch("app.core.redis.get_redis_client", lambda: object()),
    ):
        assert await chart_read.draw_chart(_LINE, _LINE, _settings(), named="bar") == _drawn()
        assert await chart_read.draw_chart(_LINE, _LINE, _settings(), named="pie") is None


def test_the_chart_pass_runs_after_the_figure() -> None:
    names = [finalize_pass.name for finalize_pass in FINALIZE_PASSES]
    assert names.index("data_chart") > names.index("figure")


def _scores(count: int) -> str:
    return "My class's test scores: " + ", ".join(str(40 + (i * 7) % 60) for i in range(count))


def test_a_follow_up_holds_the_chart_to_the_whole_earlier_list() -> None:
    """Review (2026-11-14): "graph it" quoted the earlier list cut at 600 characters, and the
    chart was grounded in that cut text, so a long list drew part of its data."""
    from app.modules.chat.chart_turn import chart_turn

    long_list = _scores(150)
    assert 600 < len(long_list) <= 2000
    turn = chart_turn("graph it", [("user", long_list), ("assistant", "Nice spread.")])
    assert turn is not None and turn[0] == long_list
    cut = ChartRequest(kind="histogram", values=long_list.split(": ")[1].split(", ")[:80])
    assert chart_read.chart_for_reading(cut, turn[0], None) is None
    whole = ChartRequest(kind="histogram", values=long_list.split(": ")[1].split(", "))
    assert chart_read.chart_for_reading(whole, turn[0], None) is not None


@pytest.mark.parametrize("line", [_scores(600) + ". Make a histogram.", "graph it"])
def test_data_longer_than_the_read_is_shown_is_not_judged(line: str) -> None:
    """A read of its first part would draw a chart of part of the data: no chart turn."""
    from app.modules.chat.chart_turn import chart_turn

    earlier = [("user", _scores(600)), ("assistant", "Got it.")]
    assert len(_scores(600)) > chart_read.MAX_DATA_CHARS
    assert chart_turn(line, earlier) is None


@pytest.mark.asyncio
async def test_draw_chart_refuses_data_too_long_to_read_whole() -> None:
    ask = AsyncMock()
    with patch("app.gateways.structured_completion.complete_structured", ask):
        assert await chart_read.draw_chart("graph it", _scores(600), _settings()) is None
    ask.assert_not_awaited()
