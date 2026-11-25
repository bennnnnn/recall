"""A turn solves its physics line once: routing's question, the solve and the follow-ups
share it (audit 2026-11-25: routing ran a full solve for a bool, then the solve ran again)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from app.core.config import Settings, get_settings
from app.core.readings import begin_turn
from app.modules.chat.model_routing.route import route_chat_model
from app.modules.chat.turn_prep.reading import read_turn_message
from app.modules.physics import lane
from app.modules.physics import prompt as physics_prompt
from app.modules.physics.prompt import build_physics_augmentation

_LINE = "A 2 kg ball falls 5 m. Find its speed."


@pytest.fixture
def solves(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    calls: list[str] = []
    real = physics_prompt._solve_physics_request

    def counting(*args: Any) -> Any:
        calls.append(args[0])
        return real(*args)

    monkeypatch.setattr(physics_prompt, "_solve_physics_request", counting)
    lane._physics_solves.cache_clear()
    yield calls
    lane._physics_solves.cache_clear()


async def test_routing_and_the_solve_share_one_solve(solves: list[str]) -> None:
    settings = get_settings()
    begin_turn()
    await read_turn_message(_LINE, [], settings)
    route_chat_model(_LINE, settings=settings)
    assert solves == [_LINE]  # routing asked whether the solver answers it
    _prompt, verified, failed, _ = await build_physics_augmentation(
        _LINE, settings, needs_subject=True
    )

    assert verified is not None and not failed
    assert solves == [_LINE]


async def test_other_settings_solve_on_their_own(solves: list[str]) -> None:
    """A turn under settings of its own never takes the app's solve."""
    begin_turn()
    await read_turn_message(_LINE, [], get_settings())
    before = len(solves)
    await build_physics_augmentation(
        _LINE, Settings(stem_solve_timeout_seconds=7.0), needs_subject=True
    )

    assert len(solves) == before + 1


async def test_outside_a_turn_every_solve_runs(solves: list[str]) -> None:
    for _ in range(2):
        await build_physics_augmentation(_LINE, get_settings(), needs_subject=True)

    assert solves == [_LINE, _LINE]


async def test_the_cross_check_reading_starts_beside_the_solve(
    solves: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A line routing already solved to a checked answer: the cross-check's reading starts
    with the turn's solve, not after it (audit 2026-11-25: it waited on the solve first)."""
    from app.modules.physics import subject as physics_subject
    from app.modules.physics.subject import PHYSICS_SUBJECT
    from app.services.subjects.registry import SubjectRequest

    events: list[str] = []
    solve = physics_subject.build_physics_augmentation

    async def solving(*args: Any, **kwargs: Any) -> Any:
        found = await solve(*args, **kwargs)
        events.append("solved")
        return found

    async def reading(*_args: Any, **_kwargs: Any) -> None:
        events.append("reading")

    monkeypatch.setattr(physics_subject, "build_physics_augmentation", solving)
    monkeypatch.setattr("app.modules.physics.formal_read.formal_reading", reading)
    settings = get_settings()
    assert settings.physics_cross_check_enabled and settings.formal_reader_enabled
    begin_turn()
    await read_turn_message(_LINE, [], settings)
    route_chat_model(_LINE, settings=settings)

    found = await PHYSICS_SUBJECT.solve(SubjectRequest(text=_LINE, math_text=_LINE), settings)

    assert found.verified is not None
    assert events == ["reading", "solved"]
    assert solves == [_LINE]
