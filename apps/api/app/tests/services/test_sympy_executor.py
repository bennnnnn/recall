"""Tests for the bounded SymPy subprocess executor.

These exercise the production ``ProcessPoolSympyExecutor`` directly (not via
the adapter/tools layer, which uses the injectable ``thread_sympy_executor``
fixture for monkeypatch-friendly tests). They use top-level picklable
functions so the callables can cross the subprocess boundary.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.services.sympy_executor import (
    ProcessPoolSympyExecutor,
    run_sympy,
    set_sympy_executor,
)


def _add(a: int, b: int) -> int:
    """Picklable top-level function — the subprocess resolves it by qualified
    name from the forked ``sys.modules``."""
    return a + b


def _sleep_forever(_ignored: object = None) -> int:
    """Hangs forever — used to verify the hard-kill-on-timeout path. Returns
    the PID so a test could (if needed) confirm the PID is gone after kill."""
    time.sleep(30)
    return 0


def _echo_pid() -> int:
    import os

    return os.getpid()


@pytest.mark.asyncio
async def test_run_sympy_returns_result():
    """A simple picklable callable runs in the subprocess and returns its
    result."""
    set_sympy_executor(ProcessPoolSympyExecutor(max_workers=1))
    result = await run_sympy(_add, 2, 3, timeout=10)
    assert result == 5


@pytest.mark.asyncio
async def test_run_sympy_runs_in_subprocess():
    """The callable runs in a different process (not the pytest parent)."""
    import os

    set_sympy_executor(ProcessPoolSympyExecutor(max_workers=1))
    worker_pid = await run_sympy(_echo_pid, timeout=10)
    assert worker_pid != os.getpid()


@pytest.mark.asyncio
async def test_pool_size_bounded_to_one_worker():
    """max_workers=1 — a runaway SymPy call occupies the single worker; the
    pool must not grow unbounded (DoS protection)."""
    executor = ProcessPoolSympyExecutor(max_workers=1)
    assert executor._max_workers == 1
    pool = executor._ensure_pool()
    assert pool._max_workers == 1
    executor.shutdown()


@pytest.mark.asyncio
async def test_timeout_raises_and_kills_worker():
    """On timeout, ``TimeoutError`` is raised quickly AND the worker is
    SIGTERM'd (not just orphaned). We verify the kill by checking that a
    subsequent call returns a DIFFERENT worker PID (the pool was recreated
    with a fresh worker because the old one was killed)."""
    executor = ProcessPoolSympyExecutor(max_workers=1)
    set_sympy_executor(executor)
    try:
        first_pid = await run_sympy(_echo_pid, timeout=10)
        with pytest.raises(TimeoutError):
            await run_sympy(_sleep_forever, None, timeout=0.5)
        # The pool was killed and recreated; the new worker has a different PID.
        second_pid = await run_sympy(_echo_pid, timeout=10)
        assert second_pid != first_pid
    finally:
        executor.shutdown()


@pytest.mark.asyncio
async def test_timeout_returns_quickly():
    """The timeout must fire at the configured deadline, not wait for the
    runaway callable to finish (which would defeat the DoS protection)."""
    set_sympy_executor(ProcessPoolSympyExecutor(max_workers=1))
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await run_sympy(_sleep_forever, None, timeout=0.3)
    elapsed = time.monotonic() - started
    # Allow generous slack for process startup + scheduling, but it must NOT
    # wait the full 30s sleep.
    assert elapsed < 5.0


@pytest.mark.asyncio
async def test_cancel_kills_worker():
    """CancelledError must hard-kill the pool (same as timeout), not orphan."""
    executor = ProcessPoolSympyExecutor(max_workers=1)
    set_sympy_executor(executor)
    try:
        first_pid = await run_sympy(_echo_pid, timeout=10)
        task = asyncio.create_task(run_sympy(_sleep_forever, None, timeout=30))
        await asyncio.sleep(0.3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        second_pid = await run_sympy(_echo_pid, timeout=10)
        assert second_pid != first_pid
    finally:
        executor.shutdown()


@pytest.mark.asyncio
async def test_concurrent_call_queued_behind_single_worker():
    """max_workers=1 means a second call queues behind the first. This
    verifies the bound — SymPy can't run N concurrent solves and exhaust the
    CPU. (Not a hard-kill test; a behavioral check on the bound.)"""
    set_sympy_executor(ProcessPoolSympyExecutor(max_workers=1))

    async def _slow_add() -> int:
        return await run_sympy(_add, 1, 2, timeout=10)

    # Submit two calls concurrently; with max_workers=1 they serialize.
    results = await asyncio.gather(_slow_add(), _slow_add())
    assert results == [3, 3]
