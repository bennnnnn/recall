"""The Decider's work question is a call of its own beside the turn's (``decider_read``).

Asked among the turn's questions it moved their measured answers (the think corpus's recall
from 96% to 92%), so it goes in a second call begun with the first, only for a message with a
number in it. The turn's read waits for it a moment at most, and whatever ends the read (an
answer, a failure, the reply's wait, a Stop) ends it, metered when it finished.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.gateways import decider_gateway, llm_spend
from app.gateways.decider_gateway import DeciderReply
from app.modules.chat import decider_read
from app.modules.chat.quiz_cards import PracticeCard
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


@pytest.mark.parametrize(
    ("failure", "success", "cause"),
    [(None, True, None), (RuntimeError("down"), False, None)],
)
@pytest.mark.asyncio
async def test_the_deciders_call_leaves_a_health_sample(
    monkeypatch: pytest.MonkeyPatch,
    metered: list[float],
    failure: Exception | None,
    success: bool,
    cause: str | None,
) -> None:
    """MODEL-07: the Decider's breaker opens on its own failures, so it needs samples."""
    from app.core import background_tasks
    from app.services import model_health

    samples: list[Any] = []

    async def record(_redis: Any, batch: list[Any]) -> None:
        samples.extend(batch)

    monkeypatch.setattr(model_health, "record_samples", record)
    monkeypatch.setattr("app.core.redis.get_redis_client", lambda: object())

    async def decide(*_args: Any, **_kwargs: Any) -> DeciderReply:
        if failure is not None:
            raise failure
        return DeciderReply.model_validate({"answers": _TURN})

    monkeypatch.setattr(decider_gateway, "decide", decide)
    await decider_read.decide_turn(
        isolated_settings(openrouter_api_key="key"), "hi", has_earlier=False, seconds=1.0
    )
    await background_tasks.drain_background_tasks(timeout_seconds=1.0)
    assert [(s.alias, s.success, s.cause) for s in samples] == [("decider-model", success, cause)]


def test_a_refusal_for_capacity_opens_the_breaker_by_itself() -> None:
    from types import SimpleNamespace

    refused = SimpleNamespace(response=SimpleNamespace(status_code=429))
    assert decider_read._failure_cause(refused) == "rate_limit"  # type: ignore[arg-type]
    assert decider_read._failure_cause(RuntimeError("x")) is None


@pytest.mark.asyncio
async def test_no_key_leaves_no_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import model_health

    record = AsyncMock()
    monkeypatch.setattr(model_health, "record_samples", record)
    decider_read._note_health(isolated_settings(openrouter_api_key=""), "decider-model", 0.0, None)
    await asyncio.sleep(0)
    record.assert_not_awaited()


# ── The cards' questions, after a lesson's practice card ───────────────

_CARD = PracticeCard(
    label="Exercise 1",
    question="17 protons and 18 neutrons: what is the mass number?",
    options=("17", "35", "18", "52"),
    answer=1,
)
_CODE_CARD = PracticeCard(
    label="Exercise 2",
    question="What will this Python code print?",
    options=("7", "9"),
    answer=1,
    code='scores = {"Ben": 7}\nscores["Ben"] = 9\nprint(scores["Ben"])',
)


def test_each_card_is_a_choice_among_its_lettered_options() -> None:
    questions = decider_read.lesson_questions([_CARD, _CODE_CARD], lesson=True)
    assert set(questions) == {"card1", "card2", "answers", "unplaced", "goes_on"}
    card = questions["card1"]
    assert card["type"] == "choice"
    assert card["criteria"]["b"] == "B: 35"
    assert {"other", "none"} <= set(card["criteria"])
    assert "scores" in questions["card2"]["instructions"]
    assert {questions[name]["type"] for name in ("answers", "unplaced", "goes_on")} == {"noul"}
    # A reply with no card and no lesson asks nothing; a lesson with no card asks to go on;
    # one card has no other card its answer could be for.
    assert decider_read.lesson_questions([], lesson=False) == {}
    assert set(decider_read.lesson_questions([], lesson=True)) == {"goes_on"}
    assert set(decider_read.lesson_questions([_CARD], lesson=False)) == {"card1", "answers"}
    assert len(decider_read.lesson_questions([_CARD] * 9, lesson=False)) == 5 + 2


def test_a_cards_words_are_quoted_only_so_far() -> None:
    """A card is the model's text: its question and options go into the read's instructions
    cut short, whatever their length (review, 2026-11-14)."""
    long = PracticeCard("Exercise 1", "Why? " * 400, ("x" * 5000, "y"), 0, code="z" * 5000)
    questions = decider_read.lesson_questions([long], lesson=False)
    assert len(questions["card1"]["instructions"]) < 1000
    assert max(len(text) for text in questions["card1"]["criteria"].values()) < 300


class _LessonDecider(_Decider):
    """The turn's call, and the cards' call answering the second card and going on."""

    def __init__(self, *, lesson_delay: float = 0.0) -> None:
        super().__init__()
        self.lesson_delay = lesson_delay

    async def __call__(
        self, _settings: Any, *, questions: dict[str, Any], **kwargs: Any
    ) -> DeciderReply:
        if "goes_on" not in questions:
            return await super().__call__(_settings, questions=questions, **kwargs)
        self.asked.append(set(questions))
        await asyncio.sleep(self.lesson_delay)
        answers = {
            "card1": {"type": "choice", "choice": "none"},
            "card2": {"type": "choice", "choice": "b"},
            "goes_on": {"type": "noul", "noul": 0.9},
        }
        return DeciderReply.model_validate({"answers": answers, "usage": {"cost": 0.003}})


# Past the read's own call but inside its budget, the cards are read: 0.6 s past it, a call a
# second late left "b" ungraded (review, 2026-11-14).
@pytest.mark.parametrize(
    ("delay", "read"), [(0.0, True), (0.8, True), (5.0, False)], ids=["in", "slow", "late"]
)
@pytest.mark.asyncio
async def test_the_cards_questions_are_a_call_of_their_own(
    monkeypatch: pytest.MonkeyPatch, metered: list[float], delay: float, read: bool
) -> None:
    decider = _LessonDecider(lesson_delay=delay)
    monkeypatch.setattr(decider_gateway, "decide", decider)
    fields = await decider_read.decide_turn(
        isolated_settings(),
        "B",
        has_earlier=True,
        seconds=1.0,
        lesson=decider_read.lesson_questions([_CARD, _CODE_CARD], lesson=True),
    )
    assert fields is not None and fields["subject"] == "maths"
    assert set(decider_read.QUESTIONS) in decider.asked
    # Late, the cards go unread and the turn goes on as it would without them.
    assert fields["card_picks"] == (["none", "b"] if read else None)
    assert fields["goes_on"] is (True if read else None)
