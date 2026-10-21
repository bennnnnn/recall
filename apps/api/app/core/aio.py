"""Await several coroutines as one: if any fails, the rest are cancelled.

``asyncio.gather`` leaves the siblings of a failed branch running: a paid model
call, a search or a download keeps going after its turn already failed, and its
own error is never retrieved.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Iterable
from typing import Any


async def gather_or_cancel(aws: Iterable[Awaitable[Any]]) -> list[Any]:
    """Results in order; the first error cancels the others (awaited) and is raised."""
    tasks = [asyncio.ensure_future(aw) for aw in aws]
    try:
        return list(await asyncio.gather(*tasks))
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
