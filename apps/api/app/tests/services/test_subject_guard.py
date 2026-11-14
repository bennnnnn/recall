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
        return _aboom if member in {"solve", "read", "draw"} else _boom


class _BrokenSubject:
    name = "chemistry"
    hints = object()
    status_phase = "chemistry"
    followups = _Raising()
    fence = object()
    photo = _Raising()
    tool = _Raising()
    figure = _Raising()

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
    followups = broken.followups
    assert followups.problem("q", []) is None
    assert followups.continues("q", []) is False
    assert followups.previous_result("r") is None
    assert followups.continues_alone("graph it") is False
    assert followups.borrows_earlier("5") is False
    assert followups.asks_to_see("draw it") is False
    assert followups.shown_problem("draw it", []) is None
    assert followups.changed_problem("p", None, "10 s") is None
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
    assert broken.figure.without_substitutes("t") == "t"


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
