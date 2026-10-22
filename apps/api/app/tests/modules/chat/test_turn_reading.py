"""A message is read off the event loop: a slow read never stalls the machine.

One maths question once held a machine's event loop for 56 s, and every WebSocket,
SSE stream and health check with it (code-health audit SCALE-01). These run on the
tests' thread executor, which schedules as the process pool does.
"""

from __future__ import annotations

import asyncio
import pickle
import threading
from collections.abc import Iterator
from typing import Any

import pytest

from app.core.config import Settings
from app.core.readings import begin_turn, read_off_loop
from app.core.sympy_executor import set_sympy_executor
from app.modules.chat.related_questions import follow_up_topic
from app.modules.chat.turn_plan import TurnPlan, single_plan
from app.modules.chat.turn_prep.followups import read_prompt_inputs
from app.modules.chat.turn_prep.reading import read_turn_message
from app.modules.math.tools.prompt import build_math_augmentation
from app.modules.physics.prompt import build_physics_augmentation
from app.services.subject_solving import detect_subject, read_direct_reply
from app.tests.sympy_support import ThreadSympyExecutor


@pytest.fixture
def release() -> Iterator[threading.Event]:
    gate = threading.Event()
    yield gate
    gate.set()


async def _loop_ticks_while(work: asyncio.Future[object] | asyncio.Task[object]) -> int:
    ticks = 0

    async def tick() -> None:
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0.01)

    ticker = asyncio.create_task(tick())
    try:
        await work
    finally:
        ticker.cancel()
    return ticks


async def test_a_slow_message_read_leaves_the_loop_free_and_reads_no_subject(
    monkeypatch: pytest.MonkeyPatch, release: threading.Event
) -> None:
    def slow_plan(text: str, *, chemistry_enabled: bool = True) -> TurnPlan:
        release.wait(5)
        return single_plan(text)

    monkeypatch.setattr("app.modules.chat.turn_prep.intents.plan_turn", slow_plan)
    begin_turn()
    read = asyncio.ensure_future(
        read_turn_message("solve 2x + 3 = 7", [], Settings(subject_read_timeout_seconds=0.3))
    )

    ticks = await _loop_ticks_while(read)

    assert ticks >= 10
    # The read gave up: nothing on the loop reads this message again this turn.
    assert detect_subject("solve 2x + 3 = 7") is None


async def test_a_slow_maths_read_answers_with_the_unverified_note(
    monkeypatch: pytest.MonkeyPatch, release: threading.Event
) -> None:
    def slow_read(*_args: object, **_kwargs: object) -> None:
        release.wait(5)

    monkeypatch.setattr("app.modules.math.tools.prompt.read_math_request", slow_read)
    settings = Settings(math_tools_enabled=True, subject_read_timeout_seconds=0.3)
    begin_turn()
    work = asyncio.ensure_future(build_math_augmentation("graph y = 9^9^9 + x", settings))

    ticks = await _loop_ticks_while(work)

    note, verified = work.result()
    assert ticks >= 10
    assert verified is None
    assert note is not None and "Do NOT claim the answer was verified" in note


async def test_a_message_read_once_answers_the_sync_readers() -> None:
    begin_turn()
    await read_turn_message("A 2 kg ball falls 5 m. Find its speed.", [], Settings())

    assert detect_subject("A 2 kg ball falls 5 m. Find its speed.") == "physics"


class _PicklingExecutor(ThreadSympyExecutor):
    """The thread executor, with the process boundary's pickling on the way in and out."""

    async def run(self, fn: Any, *args: Any, timeout: float) -> Any:  # noqa: ASYNC109 - implements it
        # This process's own objects, round-tripped as the pool does (S301: no outside data).
        fn, args = pickle.loads(pickle.dumps((fn, args)))  # noqa: S301
        result = await super().run(fn, *args, timeout=timeout)
        return pickle.loads(pickle.dumps(result))  # noqa: S301


@pytest.fixture
def pickling_pool() -> Iterator[None]:
    set_sympy_executor(_PicklingExecutor(max_workers=1))
    yield
    set_sympy_executor(None)


async def test_every_read_crosses_the_process_boundary(pickling_pool: None) -> None:
    settings = Settings(math_tools_enabled=True)
    exchange = [
        {"role": "user", "content": "solve 2x + 3 = 7"},
        {"role": "assistant", "content": "x = 2"},
    ]
    begin_turn()
    car = "A car goes from 0 to 100 km/h in 8 s. Find its acceleration"
    await read_turn_message(car, exchange, settings)
    assert detect_subject(car) == "physics"

    note, verified = await build_math_augmentation("solve 2x + 3 = 7", settings)
    assert verified is not None and note is not None
    reply = await read_direct_reply(verified, "solve 2x + 3 = 7", settings)
    assert reply is not None and "x = 2" in reply

    _note, physics, failed = await build_physics_augmentation(
        "A 2 kg ball falls 5 m. Find its speed.", settings
    )
    assert physics is not None and not failed
    assert await read_off_loop(read_prompt_inputs, "how?", exchange, timeout=3) == "math"
    assert await read_off_loop(
        follow_up_topic, "solve 2x + 3 = 7", "x = 2", exchange, allow_general=True, timeout=3
    ) == ("subject", "solve 2x + 3 = 7")
