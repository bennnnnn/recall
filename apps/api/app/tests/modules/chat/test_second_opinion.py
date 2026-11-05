"""A second opinion on an unverified answer: the reply changes only when two of three agree."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.gateways import structured_completion
from app.models.routing_lanes import ROUTING
from app.modules.chat import second_opinion as module
from app.modules.chat.second_opinion import second_opinion_reply
from app.modules.chat.turn_prep import StreamContext
from app.modules.chat.turn_prep.model_read_shadow import start_second_opinion_read
from app.modules.chat.turn_trace import begin_turn_trace
from app.modules.model_reader.schemas import GivenRead, LawRead, ModelRead, Reason, RouteRead

_CARD = r"19.6\,\mathrm{m/s}"
_WRONG = "It hits the ground at **25 m/s**."
_RIGHT = "**Answer**\n\nv = 19.6 m/s"
_OTHER = "**Answer**\n\nv = 31 m/s"
_SETTINGS = Settings(second_opinion_enabled=True, second_opinion_seconds=2.0)


def _ctx(*, unverified: bool = True, subject: str | None = "physics") -> StreamContext:
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "A ball falls 19.6 m. Impact speed?"}],
        run_title=False,
        user_message_content="A ball falls 19.6 m. Impact speed?",
        reserved_tokens=0,
        max_output_tokens=800,
    )
    ctx.solver_unverified = unverified
    ctx.unverified_subject = subject
    return ctx


def _deps(redo: str | None) -> Any:
    calls: list[dict[str, Any]] = []

    async def stream_chat_completion(**kwargs: Any) -> AsyncIterator[str]:
        calls.append(kwargs)
        if redo is None:
            return
        for piece in (redo[:5], redo[5:]):
            yield piece

    return SimpleNamespace(
        llm=SimpleNamespace(stream_chat_completion=stream_chat_completion), calls=calls
    )


def _read(reason: Reason = "ok") -> ModelRead:
    return ModelRead(
        "physics", "impact_speed", object() if reason == "ok" else None, reason, 1.0, 0, 0
    )


async def _run(
    text: str,
    deps: Any,
    *,
    read: ModelRead,
    card: str | None = _CARD,
    ctx: StreamContext | None = None,
) -> tuple[str, dict[str, Any] | None]:
    trace = begin_turn_trace("new")
    with (
        patch.object(module, "read_with_model", AsyncMock(return_value=read)),
        patch.object(module, "read_card", lambda _read, _settings: card),
    ):
        out = await second_opinion_reply(deps, _SETTINGS, ctx or _ctx(), text, {})
    return out, trace.second_opinion


@pytest.mark.asyncio
async def test_an_agreeing_read_leaves_the_reply_and_asks_no_model(
    thread_sympy_executor: None,
) -> None:
    deps = _deps("never")
    out, record = await _run(_RIGHT, deps, read=_read())
    assert out == _RIGHT
    assert record == {"redo": False, "chosen": "original", "verdict": "agree"}
    assert deps.calls == []


@pytest.mark.asyncio
async def test_a_redo_that_agrees_with_the_read_replaces_the_reply(
    thread_sympy_executor: None,
) -> None:
    deps = _deps(_RIGHT)
    out, record = await _run(_WRONG, deps, read=_read())
    assert out == _RIGHT
    assert record == {"redo": True, "chosen": "redo", "verdict": "redone"}
    assert deps.calls[0]["model_alias"] == ROUTING.hard


@pytest.mark.asyncio
async def test_a_redo_that_agrees_with_the_first_reply_keeps_it(
    thread_sympy_executor: None,
) -> None:
    out, record = await _run(_WRONG, _deps("The impact speed is **25 m/s**."), read=_read())
    assert out == _WRONG
    assert record == {"redo": True, "chosen": "original", "verdict": "kept"}


@pytest.mark.asyncio
async def test_three_different_answers_keep_the_first_reply(thread_sympy_executor: None) -> None:
    out, record = await _run(_WRONG, _deps(_OTHER), read=_read())
    assert out == _WRONG
    assert record == {"redo": True, "chosen": "original", "verdict": "kept"}


@pytest.mark.parametrize(("read", "card"), [(_read("no_read"), _CARD), (_read(), None)])
@pytest.mark.asyncio
async def test_no_read_or_no_solved_card_leaves_the_reply(
    read: ModelRead, card: str | None, thread_sympy_executor: None
) -> None:
    deps = _deps("never")
    out, record = await _run(_WRONG, deps, read=read, card=card)
    assert out == _WRONG
    assert record is not None and record["verdict"] == "no_read"
    assert deps.calls == []


@pytest.mark.asyncio
async def test_a_reply_with_no_final_value_is_left_alone(thread_sympy_executor: None) -> None:
    out, record = await _run("It falls faster and faster.", _deps("never"), read=_read())
    assert out == "It falls faster and faster."
    assert record is not None and record["verdict"] == "no_value"


@pytest.mark.asyncio
async def test_a_redo_past_the_time_bound_keeps_the_reply(thread_sympy_executor: None) -> None:
    async def slow(**_kwargs: Any) -> AsyncIterator[str]:
        await asyncio.sleep(5)
        yield _RIGHT

    deps = SimpleNamespace(llm=SimpleNamespace(stream_chat_completion=slow))
    out, record = await _run(_WRONG, deps, read=_read())
    assert out == _WRONG
    assert record is not None and record["verdict"] == "timeout"


@pytest.mark.asyncio
async def test_a_failing_read_keeps_the_reply() -> None:
    trace = begin_turn_trace("new")
    with patch.object(module, "read_with_model", AsyncMock(side_effect=RuntimeError("boom"))):
        out = await second_opinion_reply(_deps("never"), _SETTINGS, _ctx(), _WRONG, {})
    assert out == _WRONG
    assert trace.second_opinion is not None and trace.second_opinion["verdict"] == "failed"


@pytest.mark.parametrize(
    ("settings", "ctx"),
    [
        (Settings(second_opinion_enabled=False), _ctx()),
        (_SETTINGS, _ctx(unverified=False)),
        (_SETTINGS, _ctx(subject=None)),
    ],
)
@pytest.mark.asyncio
async def test_only_an_unverified_subject_answer_is_checked(
    settings: Settings, ctx: StreamContext
) -> None:
    deps = _deps("never")
    with patch.object(module, "read_with_model", AsyncMock()) as read:
        out = await second_opinion_reply(deps, settings, ctx, _WRONG, {})
    assert out == _WRONG
    read.assert_not_called()


_SPEED = "A car travels 120 m in 8 s. What is its average speed?"


def _speed_reads() -> list[BaseModel]:
    return [
        RouteRead(subject="physics", kind="kinematics"),
        LawRead(
            op="rate_speed",
            givens=[
                GivenRead(name="d", value=120, unit="m", quote="120 m"),
                GivenRead(name="t", value=8, unit="s", quote="8 s"),
            ],
        ),
    ]


@pytest.mark.parametrize(
    ("enabled", "subject", "started"),
    [(True, "physics", True), (False, "physics", False), (True, None, False)],
)
@pytest.mark.asyncio
async def test_an_unverified_subject_turn_starts_its_read_beside_the_reply(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis: Any,
    enabled: bool,
    subject: str | None,
    started: bool,
) -> None:
    replies = _speed_reads()

    async def complete_structured(**_kwargs: Any) -> BaseModel:
        return replies.pop(0)

    monkeypatch.setattr(structured_completion, "complete_structured", complete_structured)
    trace = begin_turn_trace("new")
    # The shadow's own sampling plays no part: every such turn is read.
    settings = Settings(second_opinion_enabled=enabled, model_reader_shadow_rate=0.0)
    start_second_opinion_read(_SPEED, settings, fake_redis, unverified_subject=subject)
    assert (trace.model_read_task is not None) is started
    if trace.model_read_task is not None:
        await trace.model_read_task


@pytest.mark.asyncio
async def test_a_wrong_reply_gives_way_when_the_redo_and_the_solved_read_agree(
    monkeypatch: pytest.MonkeyPatch, fake_redis: Any, thread_sympy_executor: None
) -> None:
    replies = _speed_reads()

    async def complete_structured(**_kwargs: Any) -> BaseModel:
        return replies.pop(0)

    monkeypatch.setattr(structured_completion, "complete_structured", complete_structured)
    trace = begin_turn_trace("new")
    start_second_opinion_read(_SPEED, _SETTINGS, fake_redis, unverified_subject="physics")
    ctx = _ctx()
    ctx.user_message_content = _SPEED
    deps = _deps("**Answer**\n\nv = 15 m/s")
    out = await second_opinion_reply(deps, _SETTINGS, ctx, "The average speed is **20 m/s**.", {})
    assert out == "**Answer**\n\nv = 15 m/s"
    assert trace.second_opinion == {"redo": True, "chosen": "redo", "verdict": "redone"}
