"""Which subjects a "show it" line is read by, in which order (``dispatch.subject_shows_it``).

Each subject's look is a SymPy-pool read on the path before the model. When the registry
became the list, physics was asked before maths, so every maths "show it" or "draw it"
paid a physics read first (review of PR #2420). The order is written down again.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from app.core.config import Settings
from app.services.subjects import dispatch
from app.services.subjects.dispatch import SHOWING, subject_shows_it
from app.services.subjects.registry import SUBJECTS, subject_adapter

_RECENT = [
    {"role": "user", "content": "graph y = sin(x)"},
    {"role": "assistant", "content": "Here is the graph of y = sin(x)."},
]


def test_every_subject_is_asked_once() -> None:
    assert sorted(SHOWING) == sorted(adapter.name for adapter in SUBJECTS)
    assert len(set(SHOWING)) == len(SHOWING)


def test_maths_is_asked_before_physics() -> None:
    assert SHOWING.index("math") < SHOWING.index("physics")


@pytest.mark.parametrize(
    "line", ["show it", "draw it", "can you show me it", "a picture of it", "let me see it"]
)
@pytest.mark.asyncio
async def test_a_maths_show_line_reads_no_physics(
    line: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    read: list[Callable[..., Any]] = []

    async def run_in_place(function: Callable[..., Any], *args: Any, **_kwargs: Any) -> Any:
        read.append(function)
        return function(*args)

    monkeypatch.setattr(dispatch, "run_sympy", run_in_place)
    assert await subject_shows_it(Settings(), line, _RECENT, referent="y = sin(x)")
    assert subject_adapter("math").followups.shown_problem in read
    assert subject_adapter("physics").followups.shown_problem not in read
