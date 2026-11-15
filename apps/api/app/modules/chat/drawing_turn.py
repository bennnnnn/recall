"""The picture a maths reply describes: asked for beside the message, drawn under the reply.

Owner decision (2026-11-14): the reply model decides what a picture shows; the server
checks every item and computes every coordinate; an item that fails its check is left out,
never drawn wrong. On a maths turn asking to see a picture the reply gets maths' contract
(a ```draw block in a closed vocabulary) beside the message. The block never reaches the
phone (``draw_stream``). Finalize draws under the reply one picture of each kind (a figure,
a graph), each the first description of its kind that checks (``SubjectFigure.described``),
in place of the figure read's picture of that kind (``figure_turn``) and of any sketch or
Mermaid diagram the reply drew for it; one that does not check is left out, with no note. A reply that was not asked for one, or whose read says
the message asks to see no maths picture, keeps no block and gets no picture. Nothing here
raises into a turn.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from app.core.config import Settings
from app.modules.chat.figure_turn import earlier_user_lines, read_asks_for_a_picture
from app.modules.chat.finalize_subjects import fallback_text
from app.modules.chat.prompt_inject import inject_before_last_user
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_trace import note_prompt_rule
from app.modules.turn_reading.turn import current_turn_reading
from app.services.md_fence_scan import has_closed_fence, iter_closed_fences, strip_closed_fences
from app.services.solving import VerifiedMathBlock
from app.services.subjects.registry import SubjectFigure, subject_adapter

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState
    from app.modules.chat.turn_prep.context import StreamContext

logger = logging.getLogger(__name__)

_LANG = "draw"
# When the read has not answered by the reply's call: a maths message that asks to see a
# picture in so many words ("draw the cone", "show P in space"; "show that" is a proof).
_ASKS_TO_SEE = re.compile(
    r"\b(?:draw|sketch|graph|plot|illustrate|show(?!\s+(?:that|how|why|whether)\b))\b",
    re.IGNORECASE,
)


@dataclass
class ReplyDrawing:
    """The turn's described picture: why the reply was asked for it, and what came of it."""

    # "read": the turn's read says the message asks to see a maths picture; "words": the read
    # had not answered by the reply's call, and the maths message asks to see one.
    asked: Literal["read", "words"]
    # The reply's ```draw blocks, as the stream kept them aside.
    descriptions: list[str] = field(default_factory=list)
    # The pictures drawn from them: one of each kind, a figure and a graph.
    fences: list[str] = field(default_factory=list)

    @property
    def drawn(self) -> bool:
        return bool(self.fences)


def _figure() -> SubjectFigure | None:
    return subject_adapter("math").figure


def _a_maths_turn(ctx: StreamContext) -> bool:
    """The subject readers read the message as maths, or a maths solve verified it."""
    if isinstance(ctx.verified_subject, VerifiedMathBlock):
        return True
    kept = current_turn_reading()
    return kept is not None and kept.text == ctx.user_message_content and kept.subject == "math"


def _asks_in_words(ctx: StreamContext) -> bool:
    return _ASKS_TO_SEE.search(ctx.user_message_content or "") is not None


async def _read_for_a_picture(ctx: StreamContext, settings: Settings) -> TurnDecision | None:
    """The read, when the message asks in so many words to see something and the reply's
    call did not wait for it: waited for as long as the reply waits for a read (c081 and
    c082 of round 3 went out before theirs, and drew nothing). Waited on, never cancelled:
    the figure read waits for the same read."""
    task = ctx.live_read
    if task is None or not _asks_in_words(ctx):
        return None
    await asyncio.wait([task], timeout=settings.live_read_wait_seconds)
    if not task.done() or task.cancelled() or task.exception() is not None:
        return None
    return task.result()


async def write_for_a_picture(ctx: StreamContext, settings: Settings) -> None:
    """A solver's instant reply gives way to the model's when the message asks to see a
    maths picture: the instant reply carries the card alone, and no picture can be
    described for it (round 3's c031, "find the maximum ... and sketch its graph", got only
    the maximum). The model writes around the same checked card, and describes the graph."""
    if ctx.instant_reply is None or not isinstance(ctx.verified_subject, VerifiedMathBlock):
        return
    if _figure() is None or not settings.draw_descriptions_enabled or not _asks_in_words(ctx):
        return
    read = await _read_for_a_picture(ctx, settings)
    if read is not None and read_asks_for_a_picture(read):
        ctx.instant_reply = None
        note_prompt_rule("subject.draw_over_instant")


async def ask_for_a_drawing(
    ctx: StreamContext, settings: Settings, read: TurnDecision | None
) -> None:
    """Maths' draw contract beside the message, when it asks to see a maths picture."""
    figure = _figure()
    if figure is None or not settings.draw_descriptions_enabled or ctx.drawing is not None:
        return
    if ctx.instant_reply is not None:
        return
    if read is None:
        read = await _read_for_a_picture(ctx, settings)
    asked: Literal["read", "words"] | None = None
    if read is not None and read.subject is not None and read.picture is not None:
        asked = "read" if read_asks_for_a_picture(read) else None
    elif _a_maths_turn(ctx) and _asks_in_words(ctx):
        asked = "words"
    if asked is None:
        return
    ctx.drawing = ReplyDrawing(asked)
    ctx.prompt_messages = inject_before_last_user(ctx.prompt_messages, figure.contract)
    note_prompt_rule(f"subject.draw_{asked}")


def _still_wanted(ctx: StreamContext, drawing: ReplyDrawing) -> bool:
    """A contract asked for on the message's words holds only if the read, in by now, does
    not say otherwise."""
    if drawing.asked == "read":
        return True
    read = ctx.live_read
    if read is None or not read.done() or read.cancelled() or read.exception() is not None:
        return True
    decision = read.result()
    if decision is None or decision.subject is None or decision.picture is None:
        return True
    return read_asks_for_a_picture(decision)


def _taken_out(text: str) -> tuple[str, list[str]]:
    """``text`` without its ```draw blocks, and their bodies (a reply that did not stream
    through ``draw_stream``)."""
    bodies = [body for _start, _end, body in iter_closed_fences(text, _LANG)]
    return (strip_closed_fences(text, _LANG) if bodies else text), bodies


async def attach_drawing(state: FinalizeState) -> str:
    """The reply's described picture under it, what stood in for it taken out."""
    ctx = state.ctx
    text, written = _taken_out(state.text)
    drawing = ctx.drawing
    figure = _figure()
    if drawing is None or figure is None or state.was_cancelled:
        return text
    descriptions = [*drawing.descriptions, *written]
    if not descriptions or not _still_wanted(ctx, drawing):
        return text
    line = ctx.user_message_content or ""
    texts = [line, *earlier_user_lines(ctx.recent_messages, line)]
    try:
        fences = await figure.described(descriptions, texts, text, state.settings)
    except Exception as exc:  # A drawing that fails is no drawing: the reply stands.
        logger.info("described picture failed (%s)", type(exc).__name__)
        return text
    if not fences:
        return text
    drawing.fences = list(fences)
    text = figure.without_drawn_substitutes(text)
    if any(has_closed_fence(fence, "graph") for fence in fences):
        # The checked graph stands in for every other graph of the turn: a solve's plot of
        # the curve alone (round 3's c009 showed both) or the reply's own chart of it (c020).
        text = strip_closed_fences(strip_closed_fences(text, "graph"), "chart")
    text = text.rstrip()
    pictures = "\n\n".join(fences)
    text = f"{text}\n\n{pictures}\n" if text else f"{pictures}\n"
    # Committed, so a later pass that falls back keeps the picture.
    state.committed = fallback_text(text, server_text=state.server_text)
    return text
