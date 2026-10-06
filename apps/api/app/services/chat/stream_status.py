"""Stream status phases emitted to clients during chat turn prep."""

from collections.abc import Awaitable
from typing import Literal, Protocol

StreamStatusPhase = Literal[
    "preparing",
    "remembering",
    "reading_files",
    "loading_calendar",
    "checking_inbox",
    "searching",
    "calculating",
    "physics",
    "chemistry",
    "thinking",
    "composing",
]

STREAM_STATUS_PHASES: tuple[StreamStatusPhase, ...] = (
    "preparing",
    "remembering",
    "reading_files",
    "loading_calendar",
    "checking_inbox",
    "searching",
    "calculating",
    "physics",
    "chemistry",
    "thinking",
    "composing",
)

_SUBJECT_STATUS_PHASE: dict[Literal["math", "physics", "chemistry"], StreamStatusPhase] = {
    "math": "calculating",
    "physics": "physics",
    "chemistry": "chemistry",
}

# Status detail is rendered inline in the client label ("Searching — “…”"),
# so keep it short on the wire.
STATUS_DETAIL_MAX_CHARS = 80


def status_phase_for_subject(
    subject: Literal["math", "physics", "chemistry"],
) -> StreamStatusPhase:
    """Bubble phase for one subject. Math keeps the calculating label."""
    return _SUBJECT_STATUS_PHASE[subject]


class StreamStatusFn(Protocol):
    """Status emitter; `detail` optionally carries turn context (e.g. the
    web-search query) so clients can render an activity-specific label."""

    def __call__(self, phase: str, detail: str | None = None) -> Awaitable[None]: ...


def clip_status_detail(detail: str | None) -> str | None:
    """Normalize whitespace and bound the detail string for the wire."""
    if not detail:
        return None
    flattened = " ".join(detail.split()).strip()
    if not flattened:
        return None
    if len(flattened) > STATUS_DETAIL_MAX_CHARS:
        return flattened[: STATUS_DETAIL_MAX_CHARS - 1].rstrip() + "…"
    return flattened
