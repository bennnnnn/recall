"""Bounded executor for SymPy work — isolates CPU-bound math in a subprocess
with a hard kill on timeout.

SymPy's ``solve``/``integrate``/``simplify`` are synchronous, CPU-bound, and
unbounded in runtime on pathological inputs. ``asyncio.to_thread`` on the
shared default thread pool:

1. Shares that pool with every other ``to_thread`` caller — a hung SymPy call
   starves unrelated async work.
2. Cannot be hard-killed: cancelling the await leaves the underlying thread
   running the bad SymPy call until it finishes (or forever), leaking the
   thread and its CPU.

This module provides a dedicated, bounded ``ProcessPoolExecutor`` so SymPy
work is isolated to a single subprocess and a runaway can be SIGTERM'd. The
executor is injectable so tests can swap in a thread-based variant (which
preserves monkeypatching of module-level functions, since the subprocess
can't resolve test-local patches).

Uses the ``spawn`` start method (not ``fork``) so the worker doesn't inherit
the parent's threads/locks — the API process is multi-threaded (asyncio +
thread pool) and ``fork`` in a multi-threaded process can deadlock in the
child. The first call pays a one-time SymPy-import cost in the fresh worker;
subsequent calls reuse the worker.
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing as mp
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

# Use the spawn start method so the worker doesn't inherit the parent's
# threads/locks (the API process is multi-threaded; fork() in a multi-
# threaded process can deadlock in the child). The worker is created once
# and reused, so the spawn cost (re-importing SymPy) is paid once per pool
# lifetime, not per call.
_MP_CONTEXT = mp.get_context("spawn")


def _sympy_worker(fn: Callable[..., _T], *args: Any) -> _T:
    """Top-level worker entry point — picklable so it can cross the
    subprocess boundary. Receives a picklable callable + args, runs them."""
    return fn(*args)


class BoundedSympyExecutor:
    """Abstract: run a picklable callable with a hard timeout."""

    async def run(
        self,
        fn: Callable[..., _T],
        *args: Any,
        timeout: float,  # noqa: ASYNC109 - we IMPLEMENT the timeout, not consume it
    ) -> _T:
        raise NotImplementedError

    def shutdown(self) -> None:
        pass


class ProcessPoolSympyExecutor(BoundedSympyExecutor):
    """Dedicated, bounded ``ProcessPoolExecutor`` for SymPy work.

    ``max_workers=1`` so a runaway SymPy call is isolated to one subprocess
    and can be hard-killed on timeout by SIGTERM'ing the worker. The pool is
    recreated lazily after a kill so subsequent calls get a fresh worker.
    """

    def __init__(self, max_workers: int = 1) -> None:
        self._max_workers = max_workers
        self._pool: ProcessPoolExecutor | None = None

    def _ensure_pool(self) -> ProcessPoolExecutor:
        if self._pool is None:
            self._pool = ProcessPoolExecutor(max_workers=self._max_workers, mp_context=_MP_CONTEXT)
        return self._pool

    def _kill_pool(self) -> None:
        """Hard-kill the worker subprocess(es) and drop the pool.

        ``shutdown(wait=False)`` returns immediately but does NOT kill running
        workers — they keep executing their current task. Terminate directly
        via the pool's ``_processes`` map (PID -> multiprocessing.Process) so a
        runaway SymPy call is actually stopped, not just orphaned.
        """
        pool = self._pool
        self._pool = None
        if pool is None:
            return
        for proc in getattr(pool, "_processes", {}).values():
            try:
                proc.terminate()
            except Exception:  # best-effort cleanup of a dying process
                logger.debug("proc.terminate failed during sympy pool kill", exc_info=True)
        try:
            pool.shutdown(wait=False, cancel_futures=True)
        except Exception:  # best-effort cleanup
            logger.debug("pool.shutdown failed during sympy pool kill", exc_info=True)

    async def run(
        self,
        fn: Callable[..., _T],
        *args: Any,
        timeout: float,  # noqa: ASYNC109 - we IMPLEMENT the timeout, not consume it
    ) -> _T:
        pool = self._ensure_pool()
        future = pool.submit(_sympy_worker, fn, *args)
        afut = asyncio.wrap_future(future)
        try:
            async with asyncio.timeout(timeout):
                return await afut
        except TimeoutError:
            future.cancel()
            self._kill_pool()
            raise
        except BaseException:
            future.cancel()
            raise

    def shutdown(self) -> None:
        self._kill_pool()


class ThreadSympyExecutor(BoundedSympyExecutor):
    """In-process thread-based executor — for tests (monkeypatch-friendly).

    Uses a dedicated single-worker thread pool (NOT the shared default) so
    SymPy work is still isolated from other ``to_thread`` callers. No hard
    kill on timeout — the thread keeps running — but tests verify the
    timeout-fallback behavior, not the kill itself.
    """

    def __init__(self, max_workers: int = 1) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max_workers)

    async def run(
        self,
        fn: Callable[..., _T],
        *args: Any,
        timeout: float,  # noqa: ASYNC109 - we IMPLEMENT the timeout, not consume it
    ) -> _T:
        loop = asyncio.get_running_loop()
        try:
            async with asyncio.timeout(timeout):
                return await loop.run_in_executor(self._pool, fn, *args)
        except TimeoutError:
            raise

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


_executor: BoundedSympyExecutor | None = None


def get_sympy_executor() -> BoundedSympyExecutor:
    global _executor
    if _executor is None:
        _executor = ProcessPoolSympyExecutor(max_workers=1)
    return _executor


def set_sympy_executor(executor: BoundedSympyExecutor | None) -> None:
    """Test helper — inject a custom executor. Pass None to reset to the
    default; the previous executor is shut down."""
    global _executor
    if _executor is not None:
        _executor.shutdown()
    _executor = executor


def reset_sympy_executor() -> None:
    """Test helper — drop the current executor so the next call creates a
    fresh default (picking up any monkeypatches, since the pool forks after
    the patch is applied)."""
    set_sympy_executor(None)


async def run_sympy(
    fn: Callable[..., _T],
    *args: Any,
    timeout: float,  # noqa: ASYNC109 - we IMPLEMENT the timeout, not consume it
) -> _T:
    """Run a picklable callable in the bounded SymPy pool with a hard timeout.

    Raises ``TimeoutError`` if the callable does not complete within
    ``timeout`` seconds (the subprocess is SIGTERM'd in that case).
    """
    return await get_sympy_executor().run(fn, *args, timeout=timeout)
