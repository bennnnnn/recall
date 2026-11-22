"""A picture the app draws itself: no photo and no painting stands in for it.

"A 12 V battery is connected to a 4 Ω and a 2 Ω resistor in series. Find the current and
draw the circuit" put a painted circuit with gibberish labels above the server's schematic,
and "How far does it travel before landing? Show the path." looked a photo up for "the
path" (live, 2026-11-15). A multi-part message's picture part was painted unless the read
called it a *maths* figure, and its photo part searched whatever answered the rest.

One gate, the turn's read, decides every picture (Grade 8 round, 2026-11-18: seven of seven
pictures a student asked for failed, four paths each deciding on its own). The read calls the
message a maths, physics or chemistry question asking to see a graph, a diagram or a
molecule: the app draws it, from a solve, a figure or a checked description, or says in one
line that it could not (``owed_picture``), and no photo or painting stands in for it
(``app_draws``). A photo search or a painting answers any turn only when the read asks for
exactly that (``read_asks``), and a turn whose read has no answer gets neither. Never the
words: "Draw a cat wearing a hat and also find the current …" keeps its painting, "Show me
a photo of Marie Curie and calculate the molar mass of NaCl" its photo, and "Man this is so
bad" after a painting gets no other one.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal

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


def _answered(read: asyncio.Future[TurnDecision | None]) -> TurnDecision | None:
    if not read.done() or read.cancelled() or read.exception() is not None:
        return None
    return read.result()


def answered_read(read: object) -> TurnDecision | None:
    """The turn's read when it is in and answered; nothing is waited for."""
    return _answered(read) if isinstance(read, asyncio.Future) else None


# What answers a turn in place of an ordinary reply: a photo search, or a painting.
StandIn = Literal["photo", "image"]


def read_asks(decision: TurnDecision | None, stand_in: StandIn) -> bool:
    """Whether the turn's read says the message asks for exactly this picture: a real photo
    to look up, or an imagined picture to paint. The one decider of either (owner,
    2026-11-22): the words only say whether a message could ask for a picture at all
    (``images.intent``). After the app painted a picture for "No you displayed an image",
    a picture each came for "You keep generating an image", "did i ask about an image?"
    and "Man this is so bad", decided by word rules before any model read them. A turn
    whose read has no answer gets neither: a missed picture is far better than one nobody
    asked for. A maths, physics or chemistry turn asking for a graph, a diagram or a
    molecule is the app's to draw, never either of these."""
    return decision is not None and decision.picture == stand_in


async def read_picture(
    read: asyncio.Future[TurnDecision | None] | None, wait: float | None = None
) -> StandIn | None:
    """``photo`` or ``image`` once the read ends (its own timeout bounds it) or ``wait``
    seconds pass, when it says the message asks for one; None otherwise, with no read, and
    with a read still out. Waited on, never awaited or cancelled: the reply waits for the
    same read."""
    if read is None:
        return None
    await asyncio.wait([read], timeout=wait)
    decision = _answered(read)
    if read_asks(decision, "image"):
        return "image"
    return "photo" if read_asks(decision, "photo") else None


def app_draws(decision: TurnDecision | None, verified: VerifiedSolveBlock | None) -> bool:
    """The app draws the picture the read says the message asks to see: a maths, physics or
    chemistry graph, diagram or molecule is the app's, drawn by a solve, a figure or a
    checked description, or said in one line not to be (``owed_picture``); never a painting
    or a photo in its place, whether or not a solve drew it ("find the current and draw the
    circuit" that no solver read was painted, Grade 8 round, 2026-11-18). ``verified`` is
    kept for the callers that pass the turn's solve."""
    return asks_for_a_drawing(decision) or (
        decision is not None and read_asks_for_a_picture(decision)
    )


async def read_paints_none(
    read: asyncio.Future[TurnDecision | None] | None, verified: VerifiedSolveBlock | None
) -> bool:
    """Whether no painting goes with the reply: the read does not say the message asks for
    an imagined picture (``read_asks``), or it says the app draws the picture itself
    (``app_draws``). The words found the picture part of the message; the read decides it."""
    if read is None:
        return True
    await asyncio.wait([read])
    decision = _answered(read)
    return not read_asks(decision, "image") or app_draws(decision, verified)


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
