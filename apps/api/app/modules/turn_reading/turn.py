"""What one turn's message is, read once: the turn's ``TurnReading`` (structure ticket ST-05).

The turn's decisions used to be recomputed where each was used, from whatever text that
caller held. The reading is built once from the pooled read of the message
(``chat.turn_prep.reading.read_turn``) and kept for the turn; callers read its fields.
It holds the plan for now; the lightweight, teaching and subject decisions join it one
at a time, each with the reason code the turn's trace line records.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.readings import keep_for_turn, kept_for_turn
from app.modules.turn_reading.plan import TurnPlan

# Why the plan is what it is: one request, several, or the pool read gave up (the whole
# message as one request, as every turn before plans).
PlanReason = Literal["one_request", "several_requests", "read_declined"]

_KEPT = "turn_reading"


@dataclass(frozen=True)
class TurnReading:
    # The message read, and the setting that reads chemistry in it.
    text: str
    chemistry_enabled: bool
    plan: TurnPlan
    plan_reason: PlanReason

    def reads(self, text: str, *, chemistry_enabled: bool) -> bool:
        """Whether this is the reading of ``text``: a caller holding another text (a part,
        a rewritten line) reads that text itself."""
        return self.text == text and self.chemistry_enabled == chemistry_enabled


def keep_turn_reading(reading: TurnReading) -> None:
    keep_for_turn(_KEPT, reading)


def current_turn_reading() -> TurnReading | None:
    """This turn's reading, or None outside a turn or before its message was read."""
    kept = kept_for_turn(_KEPT)
    return kept if isinstance(kept, TurnReading) else None
