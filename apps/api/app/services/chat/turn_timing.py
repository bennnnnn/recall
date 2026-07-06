"""Time-to-first-token and phase timing for chat streams."""

from __future__ import annotations

import logging
import time
from uuid import UUID

logger = logging.getLogger(__name__)


class TurnTimingTracker:
    """Monotonic timing for a single chat stream turn (logging only)."""

    def __init__(self) -> None:
        self._start = time.perf_counter()
        self._phases_ms: dict[str, float] = {}
        self._prompt_ready_ms: float | None = None
        self._first_token_ms: float | None = None

    def _elapsed_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000.0

    def mark_phase(self, phase: str) -> None:
        self._phases_ms[phase] = self._elapsed_ms()

    def mark_prompt_ready(self) -> None:
        self._prompt_ready_ms = self._elapsed_ms()

    def mark_first_token(self) -> None:
        if self._first_token_ms is None:
            self._first_token_ms = self._elapsed_ms()

    def log_summary(
        self,
        *,
        user_id: UUID,
        chat_id: UUID,
        model: str,
        lightweight: bool = False,
    ) -> None:
        logger.info(
            "chat_stream_timing user_id=%s chat_id=%s model=%s lightweight=%s "
            "prompt_ready_ms=%s first_token_ms=%s phases_ms=%s",
            user_id,
            chat_id,
            model,
            lightweight,
            round(self._prompt_ready_ms, 1) if self._prompt_ready_ms is not None else None,
            round(self._first_token_ms, 1) if self._first_token_ms is not None else None,
            {phase: round(ms, 1) for phase, ms in self._phases_ms.items()},
        )
