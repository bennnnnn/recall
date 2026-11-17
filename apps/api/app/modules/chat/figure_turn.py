"""A maths question's picture: started beside the reply, added under it.

The turn's read (``chat.turn_decision``) says what the message asks to see. When it is a
maths question asking for a graph or a diagram, and no solve drew the whole picture already
(a graph), maths reads what to draw and draws it from the question's own values
(``SubjectFigure``), while the reply streams. A maths question that asks to see nothing is
read too, told to draw only a figure that helps teach it (a shape it measures, angles,
points, a number line), so a student need not ask (``teaching_figures_enabled``); a
chemistry question likewise gets the structure of the one compound it is about. Finalize waits a little for it once the reply
is done, and adds it under the reply when it shows what the reply's own pictures do not,
taking the model's own sketch of it out. No read, a read that says no picture, or a picture
that does not hold: the reply is saved as it is. Nothing here raises into a turn.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal

from app.core.config import Settings
from app.modules.chat.finalize_subjects import fallback_text
from app.modules.chat.turn_decision import TurnDecision
from app.services.solving import SubjectName
from app.services.subjects.registry import SubjectFigure, subject_adapter
from app.services.text_normalize import collapse_ws

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState
    from app.modules.chat.turn_prep.context import StreamContext

logger = logging.getLogger(__name__)

# The pictures a figure draws, as the read names them (a molecule or a photo is not maths').
_DRAWN = frozenset({"graph", "diagram"})
# A message that asks to see none of them (or the read left the picture unsaid).
_UNASKED = frozenset({"none", None})
# How many earlier user messages "draw it" may point back to.
_EARLIER = 3
# The subject whose figure a read's subject gets. A chemistry question that asks to see a
# molecule gets it from its solve; one that asks for nothing gets its compound's structure.
_FIGURES: dict[str, SubjectName] = {"maths": "math", "chemistry": "chemistry"}
_Wanted = tuple[SubjectName, Literal["asked", "teach"]]


def _figure(subject: SubjectName = "math") -> SubjectFigure | None:
    return subject_adapter(subject).figure


def _shown_already(verified: Any) -> bool:
    """The turn's solve already draws the whole picture (a graph, a structure), asked of
    the solving subject's own figure; a subject with no figure (physics' scene) draws its
    own picture, which no other subject's figure adds to."""
    if verified is None:
        return False
    figure = _figure(verified.subject)
    return figure is None or figure.shown(verified)


def earlier_user_lines(recent: Sequence[Any] | None, line: str) -> list[str]:
    """The user's earlier messages, newest first, without the turn's own line."""
    texts = [
        content
        for message in recent or []
        if getattr(message, "role", None) == "user"
        and isinstance(content := getattr(message, "content", None), str)
        and content.strip()
    ]
    if texts and collapse_ws(texts[-1]) == collapse_ws(line):
        texts.pop()
    return list(reversed(texts))[:_EARLIER]


def start_figure(settings: Settings, ctx: StreamContext) -> asyncio.Task[str | None] | None:
    """The picture's task, when the turn has a read to wait for and no picture of its own.

    A reply the server made without a solve (the time in Tokyo, a settings line, a plan's
    limit) answers no maths question, so it never waits at finalize for a read that could
    only say "no picture" (it waited 1.7 s for one, 2026-11-13)."""
    if (
        ctx.live_read is None
        or not settings.figure_read_enabled
        or _shown_already(ctx.verified_subject)
        or (ctx.instant_reply and ctx.verified_subject is None)
    ):
        return None
    line = ctx.user_message_content or ""
    earlier = earlier_user_lines(ctx.recent_messages, line)
    solved_by = getattr(ctx.verified_subject, "subject", None)
    return asyncio.create_task(_draw(settings, ctx.live_read, line, earlier, solved_by))


def _figure_wanted(read: asyncio.Task[TurnDecision | None]) -> _Wanted | None:
    """The subject whose figure the turn gets, and how: "asked", a maths question asking
    to see a graph or a diagram; "teach", a maths or chemistry question asking to see
    nothing, which gets a figure only if one helps teach it."""
    if not read.done() or read.cancelled() or read.exception() is not None:
        return None
    decision = read.result()
    subject = _FIGURES.get(decision.subject or "") if decision is not None else None
    if decision is None or subject is None:
        return None
    if read_asks_for_a_picture(decision):
        return subject, "asked"
    return (subject, "teach") if decision.picture in _UNASKED else None


def read_asks_for_a_picture(
    decision: TurnDecision, subjects: frozenset[str] = frozenset({"maths"})
) -> bool:
    """The read calls the message a question of ``subjects`` (maths, unless a caller names
    physics too) asking to see a graph or a diagram: the one check every picture path asks
    of the read."""
    return decision.subject in subjects and decision.picture in _DRAWN


def _asks_for_a_picture(read: asyncio.Task[TurnDecision | None]) -> bool:
    wanted = _figure_wanted(read)
    return wanted is not None and wanted[1] == "asked"


async def read_asks_for_a_figure(read: asyncio.Task[TurnDecision | None] | None) -> bool:
    """The turn's read calls the message a maths question asking to see a graph or a
    diagram: a figure the app draws, never a photo or a painted picture. Waited for until it
    ends (its own timeout bounds it: a read later than a fixed wait let "draw the box" be
    painted), and never cancelled: the reply and the figure wait for the same read."""
    if read is None:
        return False
    await asyncio.wait([read])
    return _asks_for_a_picture(read)


async def _draw(
    settings: Settings,
    read: asyncio.Task[TurnDecision | None],
    line: str,
    earlier: list[str],
    solved_by: SubjectName | None = None,
) -> str | None:
    # Waited on, never awaited: the reply may cancel the read when it stops waiting for it.
    await asyncio.wait([read])
    wanted = _figure_wanted(read)
    figure = _figure(wanted[0]) if wanted is not None else None
    # A solved turn gets only its own subject's figure, never another's over its solve.
    if wanted is None or figure is None or solved_by not in (None, wanted[0]):
        return None
    return await figure.draw(line, earlier, settings, asked=wanted[1] == "asked")


# The figure read's graphs a described plot never draws: its lettered points (A, B) and
# its number lines stay beside a plot ("Plot A(1, 2) and B(4, 8) and the line through them").
_GRAPHS_OF_THEIR_OWN = (
    '"type":"points"',
    '"type": "points"',
    '"type":"number_line"',
    '"type": "number_line"',
)


def _kind(fence: str) -> str:
    lang = fence.split("\n", 1)[0].removeprefix("```")
    if lang == "graph" and any(mark in fence for mark in _GRAPHS_OF_THEIR_OWN):
        return "graph:own"
    return lang


def _kinds(fences: Sequence[str]) -> set[str]:
    return {_kind(fence) for fence in fences}


def _without(text: str, fences: Sequence[str]) -> str:
    for fence in fences:
        text = text.replace(fence, "")
    return text


def stop_figure(ctx: StreamContext) -> None:
    if ctx.figure is not None and not ctx.figure.done():
        ctx.figure.cancel()


async def attach_figure(state: FinalizeState) -> str:
    """The picture under the reply, the reply's own sketch of it taken out."""
    ctx = state.ctx
    task = ctx.figure
    if task is None:
        return state.text
    wanted = _figure_wanted(ctx.live_read) if ctx.live_read is not None else None
    # No read, or one that has not said the message is a maths or chemistry question (or
    # said it is not): an everyday reply waits for nothing (it waited 1.75 s).
    figure = _figure(wanted[0]) if wanted is not None else None
    # The reply's own described pictures, checked and drawn (``drawing_turn``), are no reply
    # picture this one is judged against: only what they stand for is (below).
    drawn = ctx.drawing.fences if ctx.drawing is not None else []
    if state.was_cancelled or figure is None or figure.whole(_without(state.text, drawn)):
        stop_figure(ctx)
        return state.text
    # Waited on, never awaited: a picture that failed or was stopped is no picture.
    await asyncio.wait([task], timeout=state.settings.figure_wait_seconds)
    if not task.done():
        stop_figure(ctx)
        return state.text
    if task.cancelled() or task.exception() is not None:
        logger.info("figure task failed: %r", None if task.cancelled() else task.exception())
        return state.text
    fence = task.result()
    # The reply's own described picture of that kind, checked and drawn, stands
    # (``drawing_turn``); one of the other kind leaves room for this one.
    if not fence or _kind(fence) in _kinds(drawn):
        return state.text
    if not figure.adds_to(_without(state.text, drawn), fence):
        return state.text
    text = figure.without_substitutes(state.text).rstrip()
    text = f"{text}\n\n{fence}\n" if text else f"{fence}\n"
    # Committed, so a later pass that falls back keeps the picture.
    state.committed = fallback_text(text, server_text=state.server_text)
    return text
