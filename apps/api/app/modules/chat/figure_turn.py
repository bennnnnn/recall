"""A picture a maths question asks to see: started beside the reply, added under it.

The turn's read (``chat.turn_decision``) says what the message asks to see. When it is a
maths question asking for a graph or a diagram, and no solve drew the whole picture already
(a graph), maths reads what to draw and draws it from the question's own values
(``SubjectFigure``), while the reply streams. Finalize waits a little for it once the reply
is done, and adds it under the reply when it shows what the reply's own pictures do not,
taking the model's own sketch of it out. No read, a read that says no picture, or a picture
that does not hold: the reply is saved as it is. Nothing here raises into a turn.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from app.core.config import Settings
from app.modules.chat.finalize_subjects import fallback_text
from app.modules.chat.turn_decision import TurnDecision
from app.services.subjects.registry import SubjectFigure, subject_adapter
from app.services.text_normalize import collapse_ws

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState
    from app.modules.chat.turn_prep.context import StreamContext

logger = logging.getLogger(__name__)

# The pictures a figure draws, as the read names them (a molecule or a photo is not maths').
_DRAWN = frozenset({"graph", "diagram"})
# How many earlier user messages "draw it" may point back to.
_EARLIER = 3


def _figure() -> SubjectFigure | None:
    return subject_adapter("math").figure


def _earlier(recent: Sequence[Any] | None, line: str) -> list[str]:
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
    """The picture's task, when the turn has a read to wait for and no picture of its own."""
    figure = _figure()
    if (
        figure is None
        or ctx.live_read is None
        or not settings.figure_read_enabled
        or figure.shown(ctx.verified_subject)
    ):
        return None
    line = ctx.user_message_content or ""
    earlier = _earlier(ctx.recent_messages, line)
    return asyncio.create_task(_draw(settings, figure, ctx.live_read, line, earlier))


def _asks_for_a_picture(read: asyncio.Task[TurnDecision | None]) -> bool:
    if not read.done() or read.cancelled() or read.exception() is not None:
        return False
    decision = read.result()
    return decision is not None and decision.subject == "maths" and decision.picture in _DRAWN


async def read_asks_for_a_figure(
    read: asyncio.Task[TurnDecision | None] | None, seconds: float
) -> bool:
    """The turn's read calls the message a maths question asking to see a graph or a
    diagram: a figure the app draws, never a photo or a painted picture. Waited for at most
    ``seconds``, and never cancelled: the reply and the figure wait for the same read."""
    if read is None:
        return False
    await asyncio.wait([read], timeout=seconds)
    return _asks_for_a_picture(read)


async def _draw(
    settings: Settings,
    figure: SubjectFigure,
    read: asyncio.Task[TurnDecision | None],
    line: str,
    earlier: list[str],
) -> str | None:
    # Waited on, never awaited: the reply may cancel the read when it stops waiting for it.
    await asyncio.wait([read])
    if not _asks_for_a_picture(read):
        return None
    return await figure.draw(line, earlier, settings)


def stop_figure(ctx: StreamContext) -> None:
    if ctx.figure is not None and not ctx.figure.done():
        ctx.figure.cancel()


async def attach_figure(state: FinalizeState) -> str:
    """The picture under the reply, the reply's own sketch of it taken out."""
    ctx = state.ctx
    task = ctx.figure
    figure = _figure()
    if task is None or figure is None:
        return state.text
    if state.was_cancelled or figure.whole(state.text):
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
    if not fence or not figure.adds_to(state.text, fence):
        return state.text
    text = figure.without_substitutes(state.text).rstrip()
    text = f"{text}\n\n{fence}\n" if text else f"{fence}\n"
    # Committed, so a later pass that falls back keeps the picture.
    state.committed = fallback_text(text, server_text=state.server_text)
    return text
