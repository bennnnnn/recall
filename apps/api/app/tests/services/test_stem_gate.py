"""One corpus through extract, solve, and direct reply for math, physics, and chemistry."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.services.subject_solving import (
    build_subject_augmentation,
    detect_subject,
    maybe_direct_subject_reply,
)
from app.services.sympy_executor import ThreadSympyExecutor, run_sympy, set_sympy_executor

_CORPUS = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "stem_gate_corpus.json").read_text()
)


def _sleep(seconds: float) -> int:
    time.sleep(seconds)
    return 1


async def _direct(text: str) -> str | None:
    settings = get_settings()
    detected = detect_subject(text, chemistry_enabled=settings.chemistry_enabled)
    prepared = await build_subject_augmentation(
        text,
        settings,
        detected_subject=detected,
    )
    return maybe_direct_subject_reply(
        prepared.verified,
        text,
        verified_request_text=text,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _CORPUS["solve"], ids=[case["id"] for case in _CORPUS["solve"]])
async def test_stem_corpus_solve(case: dict[str, object]) -> None:
    text = str(case["text"])
    reply = await _direct(text)
    if case["direct"]:
        assert reply is not None
        assert detect_subject(text) == case["subject"]
        contains = case.get("contains")
        if isinstance(contains, str):
            assert contains in reply
    else:
        assert reply is None


@pytest.mark.asyncio
async def test_busy_sympy_slot_does_not_stall_a_second_slot() -> None:
    """One slow SymPy job occupies a slot. A second slot's 1+1, and closed
    physics and chemistry answers, still finish while that job is running."""
    executor = ThreadSympyExecutor(max_workers=3, queue_wait_seconds=2.0)
    set_sympy_executor(executor)
    try:
        occupier = asyncio.create_task(run_sympy(_sleep, 0.8, timeout=5))
        await asyncio.sleep(0.05)
        started = time.monotonic()
        added, math_reply, physics_reply, chemistry_reply = await asyncio.gather(
            run_sympy(_add, 1, 1, timeout=2),
            _direct("what is 1+1"),
            _direct("find the work done by a force of 10 N over a distance of 3 m"),
            _direct("Find Gibbs free energy when delta H=-40 kJ, delta S=-100 J and T=300 K"),
        )
        elapsed = time.monotonic() - started
        assert added == 2
        assert math_reply is not None and "2" in math_reply
        assert physics_reply is not None and "30" in physics_reply
        assert chemistry_reply is not None and "ΔG" in chemistry_reply
        assert elapsed < 0.5
        assert await occupier == 1
    finally:
        set_sympy_executor(None)


def _add(a: int, b: int) -> int:
    return a + b
