"""The working check's hand-off to the SymPy pool: run there when a job could start at
once, else here; and here too when the pool fails (review 2 of #2612)."""

from __future__ import annotations

import asyncio
from concurrent.futures.process import BrokenProcessPool
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.core import sympy_executor
from app.modules.chat.finalize_passes import FinalizeState
from app.modules.chat.finalize_subjects import check_working

_REPLY = (
    "**Solution**\n\n$H = \\frac{70}{\\frac{2.0}{400 \\times 1.0 \\times 10^{-4}}}$  \n"
    "$H = \\frac{70}{50000}$  \n$H = 1.4 \\times 10^{-3}\\,\\mathrm{W}$\n\n**Answer**\n\n"
    "```answer\nverified: false\n1.4 \\times 10^{-3}\\,\\mathrm{W}\n```"
)


def _state() -> FinalizeState:
    state = SimpleNamespace(
        text=_REPLY,
        server_text=False,
        was_cancelled=False,
        settings=SimpleNamespace(stem_solve_timeout_seconds=10.0),
        ctx=SimpleNamespace(
            verified_subject=None, solver_unverified=True, user_message_content="", worked=None
        ),
    )
    return cast(FinalizeState, state)


class _Executor:
    def __init__(self, can_start: bool | None) -> None:
        self.can_start = can_start

    def can_start_now(self, lane: str = "solve") -> bool | None:
        return self.can_start


@pytest.mark.parametrize(
    "failure", [sympy_executor.WorkerBusyError("busy"), TimeoutError(), BrokenProcessPool()]
)
def test_a_pool_that_fails_leaves_the_check_to_run_here(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    async def failing(*_args: Any, **_kwargs: Any) -> str:
        raise failure

    monkeypatch.setattr(sympy_executor, "get_sympy_executor", lambda: _Executor(True))
    monkeypatch.setattr(sympy_executor, "run_sympy", failing)
    text = asyncio.run(check_working(_state()))
    assert "verified: false\n0.0014" in text or "Corrected:" in text


def test_a_pool_with_no_slot_for_the_job_is_never_waited_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def pooled(*_args: Any, **_kwargs: Any) -> str:
        calls.append("pool")
        return _REPLY

    monkeypatch.setattr(sympy_executor, "get_sympy_executor", lambda: _Executor(False))
    monkeypatch.setattr(sympy_executor, "run_sympy", pooled)
    text = asyncio.run(check_working(_state()))
    assert calls == []
    assert "Corrected:" in text
