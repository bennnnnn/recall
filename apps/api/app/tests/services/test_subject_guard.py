"""A registered subject whose members raise answers as a subject with nothing to say.

Chemistry's ``continues_alone`` raising failed every turn, "hi there" included, and its
``fast_lane`` raising failed chemistry and plain chat (audit REL-01, 2026-11-13).
"""

from __future__ import annotations

import logging
import pickle
from contextlib import AbstractContextManager
from typing import Any

import pytest

from app.core.config import Settings
from app.services.solving import PhotoReading, SubjectAugmentation
from app.services.subjects import guard
from app.services.subjects.guard import GuardedSubject
from app.services.subjects.registry import SUBJECTS, SubjectRequest


def _boom(*_args: Any, **_kwargs: Any) -> Any:
    raise RuntimeError("a subject's bug")


async def _aboom(*_args: Any, **_kwargs: Any) -> Any:
    raise RuntimeError("a subject's bug")


class _Raising:
    """Every member a subject has, each raising."""

    def __getattr__(self, member: str) -> Any:
        return _aboom if member in {"solve", "read", "draw", "described", "answer"} else _boom


class _BrokenSubject:
    name = "chemistry"
    hints = object()
    status_phase = "chemistry"
    followups = _Raising()
    fence = object()
    photo = _Raising()
    tool = _Raising()
    figure = _Raising()
    formal = _Raising()

    def __getattr__(self, member: str) -> Any:
        return _aboom if member == "solve" else _boom


@pytest.fixture
def broken(monkeypatch: pytest.MonkeyPatch) -> GuardedSubject:
    monkeypatch.setattr(guard, "_FAILED", set())
    return GuardedSubject(_BrokenSubject())  # type: ignore[arg-type]


async def test_subject_guard_every_member_answers_neutrally(broken: GuardedSubject) -> None:
    settings = Settings()
    assert broken.enabled(settings) is False
    assert broken.asks("text") is False
    assert broken.reads("text") is False
    assert broken.asks_of("setup", "question") is False
    assert broken.fast_lane("text", tools_on=True) is None
    assert broken.instant_reply("text", prior_reply=None) is None
    broken.warm()
    with broken.solve_timeouts() as timeouts:
        assert timeouts == []
    solved = await broken.solve(SubjectRequest(text="t", math_text="t"), settings)
    assert solved == SubjectAugmentation(None, None, None)
    assert (
        broken.direct_reply(
            object(),  # type: ignore[arg-type]
            "t",
            has_image_attachment=False,
            verified_request_text=None,
        )
        is None
    )
    assert broken.answers_part(object(), 2) is None  # type: ignore[arg-type]
    followups = broken.followups
    assert followups.problem("q", []) is None
    assert followups.continues("q", []) is False
    assert followups.previous_result("r") is None
    assert followups.continues_alone("graph it") is False
    assert followups.borrows_earlier("5") is False
    assert followups.asks_to_see("draw it") is False
    assert followups.shown_problem("draw it", []) is None
    assert followups.changed_problem("p", [(None, "10 s")]) is None
    assert followups.restates("p", "l") is False
    assert followups.takes_every_change("p", "r", "l", ["10 s"]) is False
    assert broken.photo is not None
    assert await broken.photo.read(
        "caption", image_attachments=[], load_image=_aboom, settings=settings, on_status=None
    ) == PhotoReading(None, "caption")
    assert broken.tool is not None
    # A tool check that fails refuses the call.
    assert broken.tool.refuses("sympy", "{}", "t") is True
    assert broken.tool.call_matches("{}", ["t"]) is None
    assert broken.tool.draws_curve(None) is False
    assert broken.tool.asks_for_earlier_curve("t") is False
    assert broken.figure is not None
    assert await broken.figure.draw("q", [], settings) is None
    assert broken.figure.shown(None) is True
    assert broken.figure.whole("t") is True
    assert broken.figure.adds_to("t", "f") is False
    assert broken.figure.without_substitutes("t", "f") == "t"
    assert await broken.figure.described(["d"], ["q"], "reply", settings) == []
    assert broken.figure.without_drawn_substitutes("reply", "q") == "reply"
    assert broken.formal is not None
    assert await broken.formal.answer("q", settings) is None


def test_subject_guard_logs_each_failing_member_once(
    broken: GuardedSubject, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger="app.services.subjects.guard"):
        for _ in range(3):
            broken.asks("text")
            broken.followups.continues_alone("text")
    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert [record.getMessage() for record in errors] == [
        "subject chemistry.asks failed; the turn goes on without it",
        "subject chemistry.followups.continues_alone failed; the turn goes on without it",
    ]
    assert all(record.exc_info for record in errors)


def test_subject_guard_leaves_the_fence_to_the_finalize_passes(broken: GuardedSubject) -> None:
    # A fence check that raises gives way to its pass's strip: a guard keeping the text
    # would let a model's forged card through.
    assert broken.fence is _BrokenSubject.fence


@pytest.mark.parametrize("adapter", SUBJECTS, ids=lambda adapter: adapter.name)
def test_subject_guard_every_registered_subject_is_guarded_and_pickles(adapter: Any) -> None:
    assert isinstance(adapter, GuardedSubject)
    # The SymPy pool runs some members (``direct_reply``, a follow-up's shown problem).
    assert pickle.loads(pickle.dumps(adapter.direct_reply)).__self__.name == adapter.name  # noqa: S301
    assert pickle.loads(pickle.dumps(adapter.followups.shown_problem)) is not None  # noqa: S301
    timeouts = adapter.solve_timeouts()
    assert isinstance(timeouts, AbstractContextManager)


async def test_money_guard_every_member_answers_as_no_money(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chat asks money of every turn (its prepare beside the prompt, its reads in routing
    and card rounding): a money bug must cost only the money card (audit, 2026-11-25)."""
    from app.services.subjects.guard import GuardedMoney
    from app.services.subjects.registry import MONEY

    monkeypatch.setattr(guard, "_FAILED", set())
    money = GuardedMoney(_Raising())
    settings = Settings()
    common: dict[str, Any] = {"user": None, "location": None}
    loan: dict[str, Any] = {**common, "earlier": [], "last_reply": ""}
    assert await money.prepare("t", settings, None, **loan) is None
    assert await money.prepare_standing("t", settings, None, **loan) is None
    assert await money.prepare_read("t", settings, None, **common, conversation=[]) is None
    assert money.reads("t") is False
    money.read_requests(["t"], [])  # a pool read that raises reads nothing ahead
    # Yields: the line stays its science's, with no money card.
    assert money.yields_to("t", "physics") is True
    assert money.names_currency("$") is False
    assert money.owns(object()) is False
    # The finish runs in the money finalize pass, which falls back on its own.
    with pytest.raises(RuntimeError):
        await money.finish(object(), "reply", settings, english=True)  # type: ignore[arg-type]
    assert isinstance(MONEY, GuardedMoney)


async def test_a_money_bug_never_fails_a_turn_that_is_not_money(
    monkeypatch: pytest.MonkeyPatch, fake_redis: Any
) -> None:
    """The money prepare runs beside the prompt on every turn (``server_parts``)."""
    from types import SimpleNamespace

    from app.modules.chat.turn_prep import money as money_prep
    from app.modules.money import subject as money_subject
    from app.modules.turn_reading.plan import single_plan

    monkeypatch.setattr(guard, "_FAILED", set())
    monkeypatch.setattr(money_subject.MoneyPeer, "prepare", _aboom)
    monkeypatch.setattr(money_subject.MoneyPeer, "prepare_standing", _aboom)
    request = SimpleNamespace(
        content="hi there", has_image_attachment=False, recent_messages=[], search_budget=None
    )
    identity = SimpleNamespace(user=None, geo=SimpleNamespace(user_location=None))
    turn = await money_prep.money_turn(
        request,  # type: ignore[arg-type]
        identity,  # type: ignore[arg-type]
        Settings(money_read_enabled=False),
        fake_redis,
        single_plan("hi there"),
    )
    assert turn is None
