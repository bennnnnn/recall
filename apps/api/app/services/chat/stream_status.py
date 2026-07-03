"""Stream status phases emitted to clients during chat turn prep."""

from typing import Literal

StreamStatusPhase = Literal[
    "preparing",
    "loading_calendar",
    "checking_inbox",
    "searching",
    "calculating",
    "thinking",
    "composing",
]

STREAM_STATUS_PHASES: tuple[StreamStatusPhase, ...] = (
    "preparing",
    "loading_calendar",
    "checking_inbox",
    "searching",
    "calculating",
    "thinking",
    "composing",
)
