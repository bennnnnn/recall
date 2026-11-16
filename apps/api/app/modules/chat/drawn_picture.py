"""A picture the app draws itself: no photo and no painting stands in for it.

"A 12 V battery is connected to a 4 Ω and a 2 Ω resistor in series. Find the current and
draw the circuit" put a painted circuit with gibberish labels above the server's schematic,
and "How far does it travel before landing? Show the path." looked a photo up for "the
path" (live, 2026-11-15). A multi-part message's picture part was painted unless the read
called it a *maths* figure, and its photo part searched whatever answered the rest.

One rule decides whether the app draws the picture, and the prompt and finalize both ask it
(``app_draws``): the read calls the message a maths question asking to see a graph or a
diagram, which maths' figure draws from its values as before; or the read asks a maths,
physics or chemistry question's graph, diagram or molecule and the subject's solve drew that
very kind (``solve_draws``, from its cards). Never the words, and never a kind the solve did
not draw: "Draw a cat wearing a hat and also find the current …" keeps its painting, "Show me
a photo of Marie Curie and calculate the molar mass of NaCl" its photo, and "find the current
and draw the circuit" that no solver read its painting (reviews, 2026-11-15). The solve runs
before the reply's prompt and before a picture is started, so every side can ask.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.modules.chat.decider_read import READ_SUBJECTS
from app.modules.chat.figure_turn import read_asks_for_a_picture
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


def app_draws(decision: TurnDecision | None, verified: VerifiedSolveBlock | None) -> bool:
    """The app draws the picture the read says the message asks to see: maths' figure, or
    the subject's solve that drew that kind."""
    if decision is None:
        return False
    if read_asks_for_a_picture(decision):
        return True
    return asks_for_a_drawing(decision) and solve_draws(verified, decision.picture)


async def read_says_the_app_draws(
    read: asyncio.Task[TurnDecision | None] | None, verified: VerifiedSolveBlock | None
) -> bool:
    """``app_draws`` once the read ends (its own timeout bounds it). Waited on, never awaited
    or cancelled: the reply waits for the same read."""
    if read is None:
        return False
    await asyncio.wait([read])
    return app_draws(_answered(read), verified)


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
    """At finalize, whether no photo or painting stands in for the picture: what the reply's
    prompt was told (``StreamContext.problem_picture``), else ``app_draws`` with the read, if
    it is in. Nothing is waited for."""
    if isinstance(ctx.problem_picture, bool):
        return ctx.problem_picture
    read = ctx.live_read
    if not isinstance(read, asyncio.Future):
        return False
    return app_draws(_answered(read), ctx.verified_subject)
