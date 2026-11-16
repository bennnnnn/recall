"""A picture the app draws itself: no photo and no painting stands in for it.

"A 12 V battery is connected to a 4 Ω and a 2 Ω resistor in series. Find the current and
draw the circuit" put a painted circuit with gibberish labels above the server's schematic,
and "How far does it travel before landing? Show the path." looked a photo up for "the
path" (live, 2026-11-15). A multi-part message's picture part was painted unless the read
called it a *maths* figure, and its photo part searched whatever answered the rest.

A maths, physics or chemistry question asking to see a graph, a diagram or a molecule is
the app's to draw from the question's own values. The turn's read (``turn_decision``) says
so, never the words, and never the solve alone: "Draw a cat wearing a hat and also find the
current …" is a painting beside a solve, and "Show me a photo of Marie Curie and calculate the
molar mass of NaCl" a photo beside one (review, 2026-11-15). Whether the solve drew the very
picture asked for is read from its cards (``SubjectFence.cards``) by kind (``solve_draws``):
a kinematics solve's velocity-time graph is no free-body diagram.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.modules.chat.decider_read import READ_SUBJECTS
from app.modules.chat.turn_decision import TurnDecision
from app.services.md_fence_scan import iter_fences
from app.services.solving import VerifiedSolveBlock
from app.services.subjects.registry import subject_adapter

if TYPE_CHECKING:
    from app.modules.chat.turn_prep.context import StreamContext

# What the read calls a picture the app draws: a curve or a chart, a diagram (a circuit,
# forces, rays, a figure), a molecule. A photo or an imagined image is something else.
DRAWN_PICTURES = frozenset({"graph", "diagram", "molecule"})


def asks_for_a_drawing(decision: TurnDecision | None) -> bool:
    """The read calls the message a maths, physics or chemistry question asking to see a
    graph, a diagram or a molecule."""
    return (
        decision is not None
        and decision.subject in READ_SUBJECTS
        and decision.picture in DRAWN_PICTURES
    )


def _answered(read: asyncio.Task[TurnDecision | None]) -> TurnDecision | None:
    if not read.done() or read.cancelled() or read.exception() is not None:
        return None
    return read.result()


async def read_asks_for_a_drawing(read: asyncio.Task[TurnDecision | None] | None) -> bool:
    """``asks_for_a_drawing`` once the read ends (its own timeout bounds it). Waited on, never
    awaited or cancelled: the reply waits for the same read."""
    if read is None:
        return False
    await asyncio.wait([read])
    return asks_for_a_drawing(_answered(read))


# The kind of picture, as the read names it, each fence a solve writes draws. A scene is a
# diagram (a circuit, rays, forces) and, for motion, the path's curve too.
_DRAWN_AS: dict[str, frozenset[str]] = {
    "graph": frozenset({"graph"}),
    "chart": frozenset({"graph"}),
    "geometry": frozenset({"diagram"}),
    "simulation": frozenset({"diagram", "graph"}),
    "smiles": frozenset({"molecule"}),
    "molecule": frozenset({"molecule"}),
    "molecule3d": frozenset({"molecule"}),
}


def solve_draws(verified: VerifiedSolveBlock | None, kind: str | None) -> bool:
    """The subject's solve writes a picture of ``kind`` (the read's graph, diagram or
    molecule) among its cards."""
    if not isinstance(verified, VerifiedSolveBlock) or kind is None:
        return False
    cards = subject_adapter(verified.subject).fence.cards(verified)
    return any(
        kind in _DRAWN_AS.get(fence.lang.lower(), frozenset())
        for card in cards
        for fence in iter_fences(card)
    )


def app_draws_the_picture(ctx: StreamContext) -> bool:
    """At finalize: the read (if it is in) calls the message a STEM question asking to see a
    graph, a diagram or a molecule, so no photo or painting stands in for it. Nothing is
    waited for."""
    read = ctx.live_read
    return read is not None and asks_for_a_drawing(_answered(read))
