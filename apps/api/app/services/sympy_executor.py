"""Bounded executor for SymPy work — isolates CPU-bound math in subprocesses
with a hard kill on timeout.

SymPy's ``solve``/``integrate``/``simplify`` are synchronous, CPU-bound, and
unbounded in runtime on pathological inputs. ``asyncio.to_thread`` on the
shared default thread pool:

1. Shares that pool with every other ``to_thread`` caller — a hung SymPy call
   starves unrelated async work.
2. Cannot be hard-killed: cancelling the await leaves the underlying thread
   running the bad SymPy call until it finishes (or forever), leaking the
   thread and its CPU.

This module provides dedicated, bounded ``ProcessPoolExecutor`` slots so
SymPy work is isolated and a runaway can be SIGTERM'd without killing
siblings. The executor is injectable so tests can swap in a thread-based
variant (which preserves monkeypatching of module-level functions, since the
subprocess can't resolve test-local patches).

Uses the ``spawn`` start method (not ``fork``) so the worker doesn't inherit
the parent's threads/locks — the API process is multi-threaded (asyncio +
thread pool) and ``fork`` in a multi-threaded process can deadlock in the
child. The first call on a slot pays a one-time SymPy-import cost in the
fresh worker; subsequent calls reuse that worker.
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing as mp
import time
from collections.abc import Callable
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

# Use the spawn start method so the worker doesn't inherit the parent's
# threads/locks (the API process is multi-threaded; fork() in a multi-
# threaded process can deadlock in the child). Each slot's worker is
# created once and reused, so the spawn cost (re-importing SymPy) is
# paid once per slot lifetime, not per call.
_MP_CONTEXT = mp.get_context("spawn")

# Interactive chat must not sit behind someone else's integral. Slot acquire
# is independent of the per-job solve timeout and does not kill the occupant.
DEFAULT_SYMPY_MAX_WORKERS = 3
DEFAULT_SYMPY_QUEUE_WAIT_SECONDS = 2.0
_MAX_SYMPY_WORKERS = 8
# After a slot is acquired the 1-worker pool may still be spawning (first
# SymPy import). That is not "queued behind another request" and must not
# share the 2s interactive wait.
_SPAWN_WAIT_SECONDS = 20.0
_QUEUE_POLL_SECONDS = 0.01


def _clamp_workers(max_workers: int) -> int:
    return max(1, min(max_workers, _MAX_SYMPY_WORKERS))


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
    """Isolated 1-worker process pools for SymPy work.

    A shared ``ProcessPoolExecutor(max_workers=N)`` cannot hard-kill one
    runaway without terminating every in-flight sibling. Each slot is its
    own ``max_workers=1`` pool so timeout/cancel SIGTERM's only that worker.
    """

    def __init__(
        self,
        max_workers: int = DEFAULT_SYMPY_MAX_WORKERS,
        *,
        queue_wait_seconds: float = DEFAULT_SYMPY_QUEUE_WAIT_SECONDS,
    ) -> None:
        self._max_workers = _clamp_workers(max_workers)
        self._queue_wait_seconds = queue_wait_seconds
        self._slots: list[ProcessPoolExecutor | None] = [None] * self._max_workers
        self._free: asyncio.Queue[int] | None = None

    def _free_queue(self) -> asyncio.Queue[int]:
        q = self._free
        if q is None:
            q = asyncio.Queue()
            for i in range(self._max_workers):
                q.put_nowait(i)
            self._free = q
        return q

    def _ensure_slot(self, slot: int) -> ProcessPoolExecutor:
        pool = self._slots[slot]
        if pool is None:
            pool = ProcessPoolExecutor(max_workers=1, mp_context=_MP_CONTEXT)
            self._slots[slot] = pool
        return pool

    def _kill_slot(self, slot: int) -> None:
        """Hard-kill one worker subprocess and drop that slot's pool.

        ``shutdown(wait=False)`` returns immediately but does NOT kill running
        workers — they keep executing their current task. Terminate directly
        via the pool's ``_processes`` map (PID -> multiprocessing.Process) so a
        runaway SymPy call is actually stopped, not just orphaned.
        """
        pool = self._slots[slot]
        self._slots[slot] = None
        if pool is None:
            return
        for proc in getattr(pool, "_processes", {}).values():
            try:
                proc.terminate()
            except Exception:  # best-effort cleanup of a dying process
                logger.debug("proc.terminate failed during sympy slot kill", exc_info=True)
        try:
            pool.shutdown(wait=False, cancel_futures=True)
        except Exception:  # best-effort cleanup
            logger.debug("pool.shutdown failed during sympy slot kill", exc_info=True)

    def _kill_all_slots(self) -> None:
        for i in range(self._max_workers):
            self._kill_slot(i)
        self._free = None

    async def run(
        self,
        fn: Callable[..., _T],
        *args: Any,
        timeout: float,  # noqa: ASYNC109 - we IMPLEMENT the timeout, not consume it
    ) -> _T:
        slot: int | None = None
        future: Future[_T] | None = None
        t_submit = time.monotonic()
        try:
            try:
                slot = await asyncio.wait_for(
                    self._free_queue().get(),
                    timeout=self._queue_wait_seconds,
                )
            except TimeoutError as exc:
                logger.warning(
                    "sympy queued %.3fs without a free worker slot",
                    time.monotonic() - t_submit,
                )
                raise TimeoutError("SymPy worker slot wait timed out") from exc

            queue_s = time.monotonic() - t_submit
            pool = self._ensure_slot(slot)
            future = pool.submit(_sympy_worker, fn, *args)
            t_spawn = time.monotonic()
            while not future.running() and not future.done():
                if time.monotonic() - t_spawn >= _SPAWN_WAIT_SECONDS:
                    logger.warning("sympy worker failed to start after %.3fs", _SPAWN_WAIT_SECONDS)
                    future.cancel()
                    self._kill_slot(slot)
                    raise TimeoutError("SymPy worker failed to start")
                await asyncio.sleep(_QUEUE_POLL_SECONDS)
            t_start = time.monotonic()
            afut = asyncio.wrap_future(future)
            try:
                async with asyncio.timeout(timeout):
                    result = await afut
            except TimeoutError:
                logger.warning(
                    "sympy worker timed out after %.3fs (queued %.3fs)",
                    timeout,
                    queue_s,
                )
                future.cancel()
                self._kill_slot(slot)
                raise
            if queue_s >= 0.05:
                logger.info(
                    "sympy queued=%.3fs ran=%.3fs",
                    queue_s,
                    time.monotonic() - t_start,
                )
            return result
        except BaseException:
            # Request/WS cancel must kill the subprocess if *this* call owns
            # a slot. A cancel while still queued has slot is None.
            if slot is not None:
                if future is not None:
                    future.cancel()
                self._kill_slot(slot)
            raise
        finally:
            if slot is not None:
                self._free_queue().put_nowait(slot)

    def _schedule_warm(self) -> None:
        """Import SymPy in a fresh worker so the next request is not cold."""
        try:
            pool = self._ensure_pool()
            pool.submit(_sympy_worker, _warmup_import_sympy)
        except Exception:
            logger.debug("sympy re-warm submit failed", exc_info=True)

    def shutdown(self) -> None:
        self._kill_all_slots()


class ThreadSympyExecutor(BoundedSympyExecutor):
    """In-process thread-based executor — for tests (monkeypatch-friendly).

    Uses a dedicated thread pool (NOT the shared default) so SymPy work is
    still isolated from other ``to_thread`` callers. No hard kill on
    timeout — the thread keeps running — but tests verify the
    timeout-fallback behavior, not the kill itself.
    """

    def __init__(
        self,
        max_workers: int = 1,
        *,
        queue_wait_seconds: float = DEFAULT_SYMPY_QUEUE_WAIT_SECONDS,
    ) -> None:
        self._max_workers = _clamp_workers(max_workers)
        self._queue_wait_seconds = queue_wait_seconds
        self._pool = ThreadPoolExecutor(max_workers=self._max_workers)

    async def run(
        self,
        fn: Callable[..., _T],
        *args: Any,
        timeout: float,  # noqa: ASYNC109 - we IMPLEMENT the timeout, not consume it
    ) -> _T:
        t_submit = time.monotonic()
        future = self._pool.submit(fn, *args)
        while not future.running() and not future.done():
            if time.monotonic() - t_submit >= self._queue_wait_seconds:
                future.cancel()
                raise TimeoutError("SymPy worker slot wait timed out")
            await asyncio.sleep(_QUEUE_POLL_SECONDS)
        afut = asyncio.wrap_future(future)
        try:
            async with asyncio.timeout(timeout):
                return await afut
        except TimeoutError:
            raise

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


_executor: BoundedSympyExecutor | None = None


def get_sympy_executor() -> BoundedSympyExecutor:
    global _executor
    if _executor is None:
        from app.core.config import get_settings

        settings = get_settings()
        _executor = ProcessPoolSympyExecutor(
            max_workers=settings.sympy_max_workers,
            queue_wait_seconds=settings.sympy_queue_wait_seconds,
        )
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


def _warmup_import_sympy() -> None:
    """Picklable no-op that pays the spawn worker's SymPy import."""
    import sympy  # noqa: F401


async def warm_sympy_pool() -> None:
    """Create the spawn worker and import SymPy so the first chat is not cold."""
    try:
        await run_sympy(_warmup_import_sympy, timeout=20.0)
    except Exception:
        logger.warning("sympy pool warmup failed", exc_info=True)


async def run_sympy(
    fn: Callable[..., _T],
    *args: Any,
    timeout: float,  # noqa: ASYNC109 - we IMPLEMENT the timeout, not consume it
) -> _T:
    """Run a picklable callable in the bounded SymPy pool with a hard timeout.

    Raises ``TimeoutError`` if the callable does not complete within
    ``timeout`` seconds of the worker starting (the subprocess is SIGTERM'd
    in that case). Time spent waiting for a free slot does not count toward
    ``timeout`` and does not kill the occupant. Interactive slot wait is capped
    separately (default 2s) so one slow integral cannot stall ``1+1=x``.
    """
    return await get_sympy_executor().run(fn, *args, timeout=timeout)
