"""The Decider's work question is a call of its own beside the turn's (``decider_read``).

Asked among the turn's questions it moved their measured answers (the think corpus's recall
from 96% to 92%), so it goes in a second call begun with the first, only for a message with a
number in it. The turn's read waits for it a moment at most, and whatever ends the read (an
answer, a failure, the reply's wait, a Stop) ends it, metered when it finished.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.gateways import decider_gateway, llm_spend
from app.gateways.decider_gateway import DeciderReply
from app.modules.chat import decider_read
from app.tests.fakes import isolated_settings

_TURN = {
    "subject": {"type": "choice", "choice": "maths"},
    "think": {"type": "noul", "noul": 0.1},
    "hard": {"type": "noul", "noul": 0.1},
    "picture": {"type": "choice", "choice": "none"},
    "follow": {"type": "choice", "choice": "none"},
    "live": {"type": "noul", "noul": 0.0},
    "asked": {"type": "noul", "noul": 0.0},
}


class _Decider:
    """A fake Decider: the turn's call and the work call, each with its own delay."""

    def __init__(
        self, *, work_delay: float = 0.0, turn_delay: float = 0.0, work_fails: bool = False
    ):
        self.work_delay, self.turn_delay, self.work_fails = work_delay, turn_delay, work_fails
        self.asked: list[set[str]] = []
        self.work_cancelled = False

    async def __call__(
        self, _settings: Any, *, questions: dict[str, Any], **_: Any
    ) -> DeciderReply:
        self.asked.append(set(questions))
        if "work" not in questions:
            await asyncio.sleep(self.turn_delay)
            return DeciderReply.model_validate({"answers": _TURN, "usage": {"cost": 0.001}})
        try:
            await asyncio.sleep(self.work_delay)
        except asyncio.CancelledError:
            self.work_cancelled = True
            raise
        if self.work_fails:
            raise RuntimeError("refused")
        return DeciderReply.model_validate(
            {"answers": {"work": {"type": "noul", "noul": 0.1}}, "usage": {"cost": 0.002}}
        )


@pytest.fixture
def metered(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    costs: list[float] = []
    monkeypatch.setattr(llm_spend, "meter_reported_cost", lambda _alias, cost: costs.append(cost))
    return costs


async def _read(
    monkeypatch: pytest.MonkeyPatch, decider: _Decider, *, ask_work: bool = True
) -> dict[str, Any] | None:
    monkeypatch.setattr(decider_gateway, "decide", decider)
    return await decider_read.decide_turn(
        isolated_settings(),
        "Translate 7x into words",
        has_earlier=False,
        seconds=1.0,
        ask_work=ask_work,
    )


@pytest.mark.asyncio
async def test_the_work_question_is_its_own_call_and_both_are_metered(
    monkeypatch: pytest.MonkeyPatch, metered: list[float]
) -> None:
    decider = _Decider()
    fields = await _read(monkeypatch, decider)
    assert fields is not None and (fields["subject"], fields["work"]) == ("maths", False)
    assert {"work"} in decider.asked and set(decider_read.QUESTIONS) in decider.asked
    assert "work" not in decider_read.QUESTIONS
    await asyncio.sleep(0)
    assert sorted(metered) == [0.001, 0.002]


@pytest.mark.asyncio
async def test_a_message_with_no_number_asks_no_work_question(
    monkeypatch: pytest.MonkeyPatch, metered: list[float]
) -> None:
    decider = _Decider()
    fields = await _read(monkeypatch, decider, ask_work=False)
    assert fields is not None and fields["work"] is None
    assert decider.asked == [set(decider_read.QUESTIONS)]


@pytest.mark.parametrize("fails", [False, True], ids=["late", "failed"])
@pytest.mark.asyncio
async def test_a_late_or_failed_work_call_leaves_the_layout_to_the_rules(
    monkeypatch: pytest.MonkeyPatch, metered: list[float], fails: bool
) -> None:
    decider = _Decider(work_delay=0 if fails else 5.0, work_fails=fails)
    fields = await _read(monkeypatch, decider)
    assert fields is not None and fields["subject"] == "maths" and fields["work"] is None
    await asyncio.sleep(0)
    assert decider.work_cancelled is (not fails)
    assert metered == [0.001]


@pytest.mark.asyncio
async def test_a_read_cancelled_ends_its_work_call(
    monkeypatch: pytest.MonkeyPatch, metered: list[float]
) -> None:
    """The reply's wait ran out, or the user tapped Stop: nothing keeps calling or billing."""
    decider = _Decider(work_delay=5.0, turn_delay=5.0)
    task = asyncio.create_task(_read(monkeypatch, decider))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)
    assert decider.work_cancelled
    assert metered == []
