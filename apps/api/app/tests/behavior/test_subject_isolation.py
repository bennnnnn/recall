"""One subject's bug costs only that subject's answer: every other turn still routes and solves.

With chemistry's ``continues_alone`` raising, every turn crashed, "hi there" included; with
its ``fast_lane`` raising, chemistry and plain chat did; with a reader the subject order asks
raising, no line had a subject (audit REL-01, 2026-11-13). Ending the order at the raising step
then left "Solve 2x + 5 = 17" with none too (review, 2026-11-13).
"""

from __future__ import annotations

from contextlib import ExitStack
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


_CHEMISTRY_READERS = [
    ("app.modules.chemistry.request.is_chemistry_question",),
    (
        "app.services.subjects.order._closed_chemistry",
        "app.services.subjects.order._chemistry_shaped",
    ),
]


async def _route_with(targets: tuple[str, ...], prompt: str) -> Any:
    with ExitStack() as stack:
        for target in targets:
            stack.enter_context(patch(target, _boom))
        return await route_case(Case("isolation", "subject", prompt, Expect(), ""))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("targets", "failed"),
    [
        *((targets, "chemistry") for targets in _CHEMISTRY_READERS),
        (("app.services.subjects.order.needs_physics",), "physics"),
    ],
)
@pytest.mark.parametrize(("prompt", "subject"), _LINES)
async def test_a_raising_subject_reader_drops_only_its_own_subject(
    targets: tuple[str, ...], failed: str, prompt: str, subject: str
) -> None:
    """A step of the subject order whose reader raises switches its subject off for the line,
    which is read again: every other subject still reads and solves it (review, 2026-11-13),
    and the broken subject never has it."""
    route = await _route_with(targets, prompt)
    if subject == failed:
        assert route.subject != failed
    else:
        assert route.subject == subject
        assert route.solved is bool(subject)


@pytest.mark.asyncio
@pytest.mark.parametrize("targets", _CHEMISTRY_READERS)
async def test_a_chemistry_line_goes_to_no_subject_when_its_readers_raise(
    targets: tuple[str, ...],
) -> None:
    """Answered "no" by its failed chemistry steps, a Ka problem fell to maths, which certified
    a negative concentration (review, 2026-11-13): its symbols keep it from maths."""
    prompt = (
        "The Ka of HA is 1.8 x 10^-5 and [HA] = 0.10 M. Solve x^2/(0.10 - x) = 1.8 x 10^-5 for x."
    )
    route = await _route_with(targets, prompt)
    assert route.subject == ""
    assert route.solved is False


@pytest.mark.asyncio
async def test_a_raising_chemistry_solve_leaves_its_turn_unverified() -> None:
    with patch("app.modules.chemistry.subject.ChemistrySubject.solve", _aboom):
        route = await route_case(
            Case("isolation", "subject", "What is the molar mass of H2SO4?", Expect(), "")
        )
    assert route.subject == "chemistry" and not route.solved
