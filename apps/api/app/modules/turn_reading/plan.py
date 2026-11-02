"""A turn's plan: the separate requests one message holds (``turn_prep.intents`` makes it).

Only data, so the prompt sections, the tool loop and turn prep can all read a plan
without importing each other.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PartKind = Literal["settings", "image", "photo", "reminder", "solve", "live", "ask"]

# Requests the server carries out itself (a settings card, a picture, a photo): the
# tool loop never takes them, and the reply only makes room for them.
HANDLED_KINDS: frozenset[PartKind] = frozenset({"settings", "image", "photo"})


@dataclass(frozen=True)
class TurnPart:
    # The user's words for this request, without the "and also" before it.
    text: str
    # Read only on a multi-part plan; a one-part plan is the whole message.
    kind: PartKind = "ask"


@dataclass(frozen=True)
class TurnPlan:
    parts: tuple[TurnPart, ...]
    # What the user said about themselves before asking ("I'm a backend dev.").
    context: str = ""

    @property
    def multi(self) -> bool:
        return len(self.parts) > 1

    def texts(self) -> tuple[str, ...]:
        return tuple(part.text for part in self.parts)

    def of_kind(self, *kinds: PartKind) -> tuple[TurnPart, ...]:
        return tuple(part for part in self.parts if part.kind in kinds)


def single_plan(text: str) -> TurnPlan:
    """The whole message as one request: every turn before plans existed."""
    return TurnPlan((TurnPart(text),))


def solved_parts(plan: TurnPlan) -> tuple[TurnPart, ...]:
    """The plan's parts when it holds two or more and a subject solves every one: separate
    questions about one problem, or separate problems ("A car goes 100 m in 5 s; find its
    speed. A train goes 300 m in 10 s; find its speed."). A message of them is its parts'
    subject's homework even when the whole line, read as one problem, is no subject's."""
    if plan.multi and all(part.kind == "solve" for part in plan.parts):
        return plan.parts
    return ()
