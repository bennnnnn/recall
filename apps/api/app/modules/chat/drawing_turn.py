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
from app.modules.chat.draw_stream import without_draw_blocks
from app.modules.chat.figure_turn import earlier_user_lines, read_asks_for_a_picture
from app.modules.chat.finalize_subjects import fallback_text
from app.modules.chat.prompt_inject import inject_before_last_user
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_intercepts import may_be_a_maths_picture
from app.modules.chat.turn_trace import note_prompt_rule
from app.modules.turn_reading.turn import current_turn_reading
from app.services.solving import VerifiedMathBlock, VerifiedPhysicsBlock, VerifiedSolveBlock
from app.services.subjects.registry import SubjectFigure, subject_adapter

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState
    from app.modules.chat.turn_prep.context import StreamContext

logger = logging.getLogger(__name__)

# Words that may ask to see a maths picture. They decide only whether a turn waits for the
# read (an instant card), or, when the read is late, whether the reply is asked for a
# description, which finalize keeps only if the read, in by then, agrees. Broad on purpose,
# in whole words and each verb's own forms ("sketching", "graph it", "graphically", "use
# graphing", "Graph of it please", "on a graph"). Not a word's other senses: "drawn", "as
# shown", "a plot of land", "the shaded region", and "the graph of" naming a curve ("the
# x-intercepts of the graph of y = x² - 4", "the graphs' intersection"). "Show that"
# is a proof and "show your steps" asks for working.
_GRAPH = r"graph(?:s|ed|ing|ically)?"
_ASKS_TO_SEE = re.compile(
    r"\b(?:draw|sketch(?:es|ing)?|illustrate|shade|visuali[sz]e|diagram|plot(?!\s+of\b)"
    r"|(?:(?<!\bthe\s)(?<!\ba\s)(?<!\bits\s)(?<!\bthis\s)(?<!\btheir\s)"
    + _GRAPH
    + r"|"
    + _GRAPH
    + r"(?!\s+of\b))(?!')"
    r"|show(?!\s+(?:that|how|why|whether|your|all|each|every|(?:the\s+)?(?:steps?|working|work))\b))\b",
    re.IGNORECASE,
)


# The pictures the read may ask for that a description draws: a figure, and a graph (kind
# "plot").
_DESCRIBED = frozenset({"diagram", "graph"})


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


def _a_physics_turn(ctx: StreamContext) -> bool:
    """The subject readers read the message as physics, or a physics solve verified it."""
    if isinstance(ctx.verified_subject, VerifiedPhysicsBlock):
        return True
    kept = current_turn_reading()
    return kept is not None and kept.text == ctx.user_message_content and kept.subject == "physics"


def _physics_read(ctx: StreamContext) -> bool:
    """The turn is physics', by its read or its readers: its words' quantities (a
    particle's v(t)) are physics' to read for the graph (``graph_facts``)."""
    read = ctx.live_read
    if read is not None and read.done() and not read.cancelled() and read.exception() is None:
        decision = read.result()
        if decision is not None and decision.subject is not None:
            return decision.subject == "physics"
    return _a_physics_turn(ctx)


def _asks_in_words(ctx: StreamContext) -> bool:
    return _ASKS_TO_SEE.search(ctx.user_message_content or "") is not None


async def _read_for_a_picture(ctx: StreamContext, deadline: float) -> TurnDecision | None:
    """The read, when a message that may be maths asks in so many words to see something
    and the reply's call did not wait for it: waited for until ``deadline``, the one the
    reply's own wait for the read keeps (c081 and c082 of round 3 went out before theirs,
    and drew nothing; round 2's review saw "plot of Hamlet" wait twice). Waited on, never
    cancelled: the figure read waits for the same read."""
    task = ctx.live_read
    line = ctx.user_message_content or ""
    if task is None or not _asks_in_words(ctx):
        return None
    if not (_a_maths_turn(ctx) or _a_physics_turn(ctx) or may_be_a_maths_picture(line)):
        return None
    left = deadline - asyncio.get_running_loop().time()
    if left > 0:
        await asyncio.wait([task], timeout=left)
    if not task.done() or task.cancelled() or task.exception() is not None:
        return None
    return task.result()


# The kind of graph a physics solve draws against time (a v-t or x-t trajectory).
_TIME_GRAPH = "trajectory"


def _solver_graphed(verified: VerifiedSolveBlock | None) -> bool:
    """A physics solve's card already draws a graph against time: no second graph of the
    reply's beside it."""
    if not isinstance(verified, VerifiedPhysicsBlock):
        return False
    blocks = [verified, *verified.question_parts]
    specs = [s for b in blocks for s in (b.canonical_fence, *b.canonical_fences) if s]
    return any(spec.get("type") == _TIME_GRAPH for spec in specs)


def _wants_a_drawing(read: TurnDecision) -> bool:
    """The read calls the message a maths question asking to see a picture a description
    draws, a diagram's figure or a graph, or a physics question asking to see a graph: a
    force against displacement or a velocity against time is drawn as any curve is, held
    to the question's own formula (u5-087's F = 9 - x/2)."""
    return read.picture in _DESCRIBED and read_asks_for_a_picture(read)


def _wanted(ctx: StreamContext, read: TurnDecision) -> bool:
    """The read asks for a picture the reply describes, and no physics card of the turn
    already draws its graph against time."""
    if read.subject == "physics" and _solver_graphed(ctx.verified_subject):
        return False
    return _wants_a_drawing(read)


async def write_for_a_picture(ctx: StreamContext, settings: Settings) -> None:
    """A solver's instant reply gives way to the model's when the read says the message asks
    to see a maths picture, or a graph of a physics question whose card draws none: the instant reply carries the card alone, and no picture can be
    described for it (round 3's c031, "find the maximum ... and sketch its graph", got only
    the maximum). The model writes around the same checked card, and describes the graph.
    The read decides, never a word: a message whose words may ask (``_ASKS_TO_SEE``) waits
    for it up to ``live_read_wait_seconds``; a read later than that keeps the card, which
    loses a picture, never the card to a guess; any other message never waits."""
    verified = ctx.verified_subject
    if ctx.instant_reply is None or not isinstance(
        verified, VerifiedMathBlock | VerifiedPhysicsBlock
    ):
        return
    figure = _figure()
    if figure is None or not settings.draw_descriptions_enabled or not _asks_in_words(ctx):
        return
    if isinstance(verified, VerifiedMathBlock) and figure.shown(verified):
        return  # the card already draws the picture ("Graph y = x² and y = 2x")
    if _solver_graphed(verified):
        return  # the physics card already draws its graph against time
    deadline = asyncio.get_running_loop().time() + settings.live_read_wait_seconds
    read = await _read_for_a_picture(ctx, deadline)
    if read is None and ctx.live_read is not None and not ctx.live_read.done():
        note_prompt_rule("subject.instant_read_late")
    if read is not None and _wanted(ctx, read):
        ctx.instant_reply = None
        note_prompt_rule("subject.draw_over_instant")


async def ask_for_a_drawing(
    ctx: StreamContext, settings: Settings, read: TurnDecision | None, deadline: float
) -> None:
    """Maths' draw contract beside the message, when it asks to see a maths picture.
    ``deadline``: the loop time the reply stops waiting for the read."""
    figure = _figure()
    if figure is None or not settings.draw_descriptions_enabled or ctx.drawing is not None:
        return
    if ctx.instant_reply is not None:
        return
    if read is None:
        read = await _read_for_a_picture(ctx, deadline)
    asked: Literal["read", "words"] | None = None
    if read is not None and read.subject is not None and read.picture is not None:
        asked = "read" if _wanted(ctx, read) else None
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
    return _wanted(ctx, decision)


async def attach_drawing(state: FinalizeState) -> str:
    """The reply's described picture under it, what stood in for it taken out."""
    ctx = state.ctx
    text, written = without_draw_blocks(state.text)
    text = text.strip() if written else state.text
    drawing = ctx.drawing
    figure = _figure()
    if drawing is None or figure is None or state.was_cancelled:
        return text
    descriptions = list(dict.fromkeys([*drawing.descriptions, *written]))
    if not descriptions or not _still_wanted(ctx, drawing):
        return text
    line = ctx.user_message_content or ""
    texts = [line, *earlier_user_lines(ctx.recent_messages, line)]
    try:
        facts = subject_adapter("physics").graph_facts if _physics_read(ctx) else None
        fences = await figure.described(descriptions, texts, text, state.settings, facts)
    except Exception as exc:  # A drawing that fails is no drawing: the reply stands.
        logger.info("described picture failed (%s)", type(exc).__name__)
        return text
    if not fences:
        return text
    drawing.fences = list(fences)
    text = text.rstrip()
    pictures = "\n\n".join(fences)
    text = f"{text}\n\n{pictures}\n" if text else f"{pictures}\n"
    # Beside the pictures, what stood in for them goes: a sketch, a Mermaid diagram, a
    # solve's graph of a curve the checked graph draws (round 3's c009 showed both). A
    # solver's number line, inequality or points graph stays (2026-11-15 review).
    text = figure.without_drawn_substitutes(text)
    # Committed, so a later pass that falls back keeps the picture.
    state.committed = fallback_text(text, server_text=state.server_text)
    return text
