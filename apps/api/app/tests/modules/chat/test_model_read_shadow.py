"""The model reader in shadow: the turn's trace line says how its read compares, and the
read never outlives the turn (docs/MODEL_READER.md)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.gateways import structured_completion
from app.modules.chat.turn_prep.model_read_shadow import start_model_read_shadow
from app.modules.chat.turn_trace import begin_turn_trace, emit_turn_trace, plain_record, turn_record
from app.modules.turn_reading.schemas import GivenRead, LawRead, RouteRead

_SPEED = "A car travels 120 m in 8 s. What is its average speed?"


def _replies(replies: list[BaseModel]) -> Any:
    async def complete_structured(**_kwargs: Any) -> BaseModel:
        return replies.pop(0)

    return complete_structured


@pytest.mark.asyncio
async def test_off_by_default_no_read_and_no_field() -> None:
    trace = begin_turn_trace("new")
    start_model_read_shadow(_SPEED, Settings())
    assert trace.model_read_task is None
    assert "model_read" not in turn_record(trace, None, outcome=None)


@pytest.mark.asyncio
async def test_a_finished_read_is_compared_in_the_line(monkeypatch: pytest.MonkeyPatch) -> None:
    reads = [
        RouteRead(subject="physics", kind="kinematics"),
        LawRead(
            op="rate_speed",
            givens=[
                GivenRead(name="d", value=120, unit="m", quote="120 m"),
                GivenRead(name="t", value=8, unit="s", quote="8 s"),
            ],
        ),
    ]
    monkeypatch.setattr(structured_completion, "complete_structured", _replies(reads))
    trace = begin_turn_trace("new")
    start_model_read_shadow(_SPEED, Settings(model_reader_shadow_enabled=True))
    await trace.model_read_task
    record = turn_record(trace, None, outcome=None)
    shown = record["model_read"]
    assert shown["verdict"] == "model_only"
    assert (shown["subject"], shown["op"], shown["reason"]) == ("physics", "rate_speed", "ok")
    assert plain_record(record)
    # Only identifiers and numbers: the message never reaches the line.
    assert "120 m" not in str(record) and "car" not in str(record)


@pytest.mark.asyncio
async def test_a_read_still_running_is_late_and_stops_with_the_turn(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    started = asyncio.Event()

    async def slow(**_kwargs: Any) -> None:
        started.set()
        await asyncio.sleep(60)

    monkeypatch.setattr(structured_completion, "complete_structured", slow)
    trace = begin_turn_trace("new")
    start_model_read_shadow(_SPEED, Settings(model_reader_shadow_enabled=True))
    await started.wait()
    with caplog.at_level(logging.INFO, logger="app.modules.chat.turn_trace"):
        emit_turn_trace(None, outcome=None)
    assert '"model_read":{"verdict":"late"}' in caplog.text
    task = trace.model_read_task
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()
