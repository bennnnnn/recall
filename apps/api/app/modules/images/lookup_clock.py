"""One answer-photo lookup's steps, timed, for the one line it logs.

A lookup ran past the reply's wait on 2026-11-09 ("where is Ethiopia") while the same
search, timed later, took 0.1 s and its fetch 0.2 s: one step had stalled, and nothing
said which. Each lookup now logs every step it ran, in order, with its milliseconds, the
host its photo came from, and how it ended. The words looked up are never logged.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)


class LookupClock:
    """The steps of one lookup: the cache read, the spend and allowance checks, the image
    search, the candidate fetch, the storage write and the database row."""

    def __init__(self) -> None:
        self._started = time.perf_counter()
        self._steps: list[tuple[str, int]] = []
        # found, cached, none (nothing usable), limit (spend cap or the day's lookups),
        # failed or stopped.
        self.outcome = "none"
        self.host: str | None = None

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            self._steps.append((name, round((time.perf_counter() - started) * 1000)))

    def won(self, image_url: str) -> None:
        """The candidate whose photo was kept: its host goes in the line."""
        if self.host is None:
            self.host = urlsplit(image_url).hostname or "-"

    def steps(self) -> str:
        return " ".join(f"{name}_ms={elapsed}" for name, elapsed in self._steps)

    def log(self) -> None:
        total = round((time.perf_counter() - self._started) * 1000)
        steps = self.steps()
        logger.info(
            "answer_photo_lookup outcome=%s %s host=%s total_ms=%d",
            self.outcome,
            steps,
            self.host or "-",
            total,
        )
