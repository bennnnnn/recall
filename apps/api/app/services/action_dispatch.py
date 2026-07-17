"""Shared apply-loop for LLM-extracted project/todo action batches.

Callers load a mutable snapshot, supply `{action_name: handler}`, and get
try/except-per-action + one home-cache invalidation when anything applied.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import TypeVar

logger = logging.getLogger(__name__)

TAction = TypeVar("TAction")
TState = TypeVar("TState")

# Handler mutates ``state`` as needed and returns how many mutations applied.
type ActionHandler[TState, TAction] = Callable[[TState, TAction], Awaitable[int]]


async def apply_action_batch(
    *,
    actions: Sequence[TAction],
    state: TState,
    handlers: Mapping[str, ActionHandler[TState, TAction]],
    action_name: Callable[[TAction], str],
    prepare: Callable[[TAction], TAction | None] | None = None,
    on_error: Callable[[TAction], None] | None = None,
    log_summary: Callable[[int], None] | None = None,
    invalidate_home: Callable[[], Awaitable[None]] | None = None,
) -> int:
    """Run ``handlers`` over ``actions`` against a preloaded ``state``.

    Flow: optional prepare/skip → try handler → accumulate applied → one
    post-loop summary log → invalidate home cache once if anything applied.
    """
    applied = 0
    for action in actions:
        prepared = prepare(action) if prepare is not None else action
        if prepared is None:
            continue
        handler = handlers.get(action_name(prepared))
        if handler is None:
            continue
        try:
            applied += await handler(state, prepared)
        except Exception:
            if on_error is not None:
                on_error(prepared)
            else:
                logger.exception("Failed action %s", action_name(prepared))
    if applied > 0:
        if log_summary is not None:
            log_summary(applied)
        if invalidate_home is not None:
            await invalidate_home()
    return applied
