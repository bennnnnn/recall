"""One subject's bug costs only that subject's answer: every other turn still routes and solves.

With chemistry's ``continues_alone`` raising, every turn crashed, "hi there" included; with
its ``fast_lane`` raising, chemistry and plain chat did; with a reader the subject order asks
raising, no line had a subject (audit REL-01, 2026-11-13).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from app.tests.behavior.cases import Case, Expect
from app.tests.behavior.harness import route_case

_LINES = [
    ("Solve 2x + 5 = 17", "math"),
    ("A car accelerates from 0 to 30 m/s in 6 s. What is its acceleration?", "physics"),
    ("hi there", ""),
]


def _boom(*_args: Any, **_kwargs: Any) -> Any:
    raise RuntimeError("an injected chemistry bug")


async def _aboom(*_args: Any, **_kwargs: Any) -> Any:
    raise RuntimeError("an injected chemistry bug")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target",
    [
        "app.modules.chemistry.subject.ChemistryFollowups.continues_alone",
        "app.modules.chemistry.subject.ChemistrySubject.fast_lane",
        "app.modules.chemistry.subject.ChemistrySubject.asks",
        "app.modules.chemistry.subject.ChemistrySubject.solve",
        "app.modules.chemistry.request.is_chemistry_question",
    ],
)
@pytest.mark.parametrize(("prompt", "subject"), _LINES)
async def test_a_raising_chemistry_member_fails_no_other_turn(
    target: str, prompt: str, subject: str
) -> None:
    with patch(target, _aboom if target.endswith(".solve") else _boom):
        route = await route_case(Case("isolation", "subject", prompt, Expect(), ""))
    assert route.subject == subject
    assert route.solved is bool(subject)


@pytest.mark.asyncio
async def test_a_raising_chemistry_solve_leaves_its_turn_unverified() -> None:
    with patch("app.modules.chemistry.subject.ChemistrySubject.solve", _aboom):
        route = await route_case(
            Case("isolation", "subject", "What is the molar mass of H2SO4?", Expect(), "")
        )
    assert route.subject == "chemistry" and not route.solved
