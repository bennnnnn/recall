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

Physics describes its pictures the same way: on a physics message no solve drew a picture
for, the reply gets physics' contract, its setup's scene (``physics.scene_drawing``: a
projectile, an incline, an Atwood machine, ...) and an electric field's lines
(``physics.field_lines``), and physics checks and draws what it describes. The field
questions of a GCSE set came back as ASCII art (live, 2026-11-16), and 29 of 30 hard
problems in parts had no picture at all: no solver reads a question in parts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from app.core.config import Settings
from app.modules.chat.draw_stream import without_draw_blocks
from app.modules.chat.drawn_picture import solve_draws
from app.modules.chat.figure_turn import earlier_user_lines
from app.modules.chat.finalize_subjects import fallback_text
from app.modules.chat.prompt_inject import inject_before_last_user
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_intercepts import may_be_a_maths_picture
from app.modules.chat.turn_trace import note_prompt_rule
from app.modules.turn_reading.turn import current_turn_reading
from app.services.solving import SubjectName, VerifiedMathBlock, VerifiedPhysicsBlock
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


# The pictures the read may ask for that a description draws, by the read's subject: maths'
# figure and graph (kind "plot"), and physics' diagram (a field's lines).
_DESCRIBED: dict[str, tuple[SubjectName, frozenset[str]]] = {
    "maths": ("math", frozenset({"diagram", "graph"})),
    # Physics' scene is its setup's picture: a problem asking to see nothing gets it too, as
    # maths' teaching figure does, when no solve drew one.
    "physics": ("physics", frozenset({"diagram", "graph", "none"})),
}


@dataclass
class ReplyDrawing:
    """The turn's described picture: why the reply was asked for it, and what came of it."""

    # "read": the turn's read says the message asks to see a maths picture; "words": the read
    # had not answered by the reply's call, and the maths message asks to see one.
    asked: Literal["read", "words"]
    # The subject whose contract the reply was given, and whose figure draws its blocks.
    subject: SubjectName = "math"
    # The reply's ```draw blocks, as the stream kept them aside.
    descriptions: list[str] = field(default_factory=list)
    # The pictures drawn from them: one of each kind, a figure and a graph.
    fences: list[str] = field(default_factory=list)

    @property
    def drawn(self) -> bool:
        return bool(self.fences)


def _figure(subject: SubjectName = "math") -> SubjectFigure | None:
    return subject_adapter(subject).figure


def _a_maths_turn(ctx: StreamContext) -> bool:
    """The subject readers read the message as maths, or a maths solve verified it."""
    if isinstance(ctx.verified_subject, VerifiedMathBlock):
        return True
    kept = current_turn_reading()
    return kept is not None and kept.text == ctx.user_message_content and kept.subject == "math"


def _words_subject(ctx: StreamContext) -> SubjectName | None:
    """The subject whose reply may describe a picture the message asks for in words, when
    the read is late: maths, or physics, as the subject readers read the message."""
    if _a_maths_turn(ctx):
        return "math"
    kept = current_turn_reading()
    if kept is not None and kept.text == ctx.user_message_content and kept.subject == "physics":
        return "physics"
    return None


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
    physics = isinstance(ctx.verified_subject, VerifiedPhysicsBlock)
    if not physics and _words_subject(ctx) is None and not may_be_a_maths_picture(line):
        return None
    left = deadline - asyncio.get_running_loop().time()
    if left > 0:
        await asyncio.wait([task], timeout=left)
    if not task.done() or task.cancelled() or task.exception() is not None:
        return None
    return task.result()


def _described_by(read: TurnDecision) -> SubjectName | None:
    """The subject whose reply describes the picture the read says the message asks to see:
    a maths question's figure or graph, a physics question's diagram."""
    entry = _DESCRIBED.get(read.subject or "")
    return entry[0] if entry is not None and read.picture in entry[1] else None


async def write_for_a_picture(ctx: StreamContext, settings: Settings) -> None:
    """A solver's instant reply gives way to the model's when the read says the message asks
    to see a picture its subject's reply describes (maths' figure or graph, physics' field
    lines its solve did not draw): the instant reply carries the card alone, and no picture can be
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
    subject: SubjectName = "math" if isinstance(verified, VerifiedMathBlock) else "physics"
    figure = _figure(subject)
    if figure is None or not settings.draw_descriptions_enabled or not _asks_in_words(ctx):
        return
    if subject == "math" and figure.shown(verified):
        return  # the card already draws the picture ("Graph y = x² and y = 2x")
    if subject == "physics" and not subject_adapter("physics").enabled(settings):
        return
    deadline = asyncio.get_running_loop().time() + settings.live_read_wait_seconds
    read = await _read_for_a_picture(ctx, deadline)
    if read is None and ctx.live_read is not None and not ctx.live_read.done():
        note_prompt_rule("subject.instant_read_late")
    # Only a picture the message asks to see: a problem's setup (physics' "none") is drawn
    # beside its card, never in its place.
    if read is None or read.picture not in ("diagram", "graph") or _described_by(read) != subject:
        return
    # A physics solve that drew the picture asked for keeps its card ("calculate the field
    # and draw its lines" whose solve drew none gives way, so the reply can describe them).
    if subject == "physics" and solve_draws(verified, read.picture):
        return
    ctx.instant_reply = None
    note_prompt_rule("subject.draw_over_instant")


async def ask_for_a_drawing(
    ctx: StreamContext, settings: Settings, read: TurnDecision | None, deadline: float
) -> None:
    """A subject's draw contract beside the message, when it asks to see a picture that
    subject's reply describes: maths' figure or graph, physics' field. ``deadline``: the
    loop time the reply stops waiting for the read."""
    if not settings.draw_descriptions_enabled or ctx.drawing is not None:
        return
    if ctx.instant_reply is not None:
        return
    if read is None:
        read = await _read_for_a_picture(ctx, deadline)
    asked: Literal["read", "words"] | None = None
    subject: SubjectName | None = "math"
    if read is not None and read.subject is not None and read.picture is not None:
        subject = _described_by(read)
        asked = "read" if subject is not None else None
    elif _asks_in_words(ctx):
        subject = _words_subject(ctx)
        asked = "words" if subject is not None else None
    if asked is None or subject is None:
        return
    # A physics solve that drew the picture asked for (a scene, a circuit, rays) needs no
    # description; one that drew none ("calculate the field strength and draw its lines")
    # still gets the contract.
    asked_kind = read.picture if read is not None else None
    kind = asked_kind if asked_kind in ("diagram", "graph") else "diagram"
    if subject == "physics" and solve_draws(ctx.verified_subject, kind):
        return
    # A subject turned off draws nothing, and its reply is asked for no description.
    figure = _figure(subject) if subject_adapter(subject).enabled(settings) else None
    if figure is None:
        return
    # A message the read says asks to see nothing gets only its problem's setup, and none
    # when the read says it works nothing out ("why does a 1 kg mass fall as fast as a
    # 10 kg one?" states masses but poses no problem).
    sees = read is None or read.picture in ("diagram", "graph")
    if not sees and read is not None and read.work is False:
        return
    contract = figure.contract_for(ctx.user_message_content or "", sees)
    if not contract:
        return
    ctx.drawing = ReplyDrawing(asked, subject=subject)
    ctx.prompt_messages = inject_before_last_user(ctx.prompt_messages, contract)
    note_prompt_rule(f"subject.draw_{asked}" if subject == "math" else f"{subject}.draw_{asked}")


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
    return _described_by(decision) == drawing.subject


async def attach_drawing(state: FinalizeState) -> str:
    """The reply's described picture under it, what stood in for it taken out."""
    ctx = state.ctx
    text, written = without_draw_blocks(state.text)
    text = text.strip() if written else state.text
    drawing = ctx.drawing
    figure = _figure(drawing.subject) if drawing is not None else None
    if drawing is None or figure is None or state.was_cancelled:
        return text
    descriptions = list(dict.fromkeys([*drawing.descriptions, *written]))
    if not descriptions or not _still_wanted(ctx, drawing):
        return text
    line = ctx.user_message_content or ""
    # A physics scene is of the problem a follow-up points back to, when there is one
    # (maths reads its own follow-ups from the lines).
    physics = drawing.subject == "physics" and ctx.followup_problem
    problem = [ctx.followup_problem] if physics and ctx.followup_problem else []
    texts = [*problem, line, *earlier_user_lines(ctx.recent_messages, line)]
    try:
        fences = await figure.described(descriptions, texts, text, state.settings)
    except Exception as exc:  # A drawing that fails is no drawing: the reply stands.
        logger.info("described picture failed (%s)", type(exc).__name__)
        return text
    # What came of the reply's descriptions, so a picture that did not check shows.
    logger.info(
        "described pictures blocks=%d drawn=%d shapes=%s",
        len(descriptions),
        len(fences),
        [_shape(body) for body in descriptions],
    )
    if not fences:
        return text
    drawing.fences = list(fences)
    text = text.rstrip()
    pictures = "\n\n".join(fences)
    text = f"{text}\n\n{pictures}\n" if text else f"{pictures}\n"
    # Beside the pictures, what stood in for them goes: a sketch, a Mermaid diagram, a
    # solve's graph of a curve the checked graph draws (round 3's c009 showed both). A
    # solver's number line, inequality or points graph stays (2026-11-15 review).
    text = figure.without_drawn_substitutes(text, line)
    # Committed, so a later pass that falls back keeps the picture.
    state.committed = fallback_text(text, server_text=state.server_text)
    return text


def _shape(body: str) -> str:
    """What a description describes, for the log: its kind, scene and part names, no value."""
    try:
        data = json.loads(body)
    except ValueError:
        return "not JSON"
    if not isinstance(data, dict):
        return "not an object"
    parts = data.get("values")
    names = sorted(parts) if isinstance(parts, dict) else []
    return f"{data.get('kind')}:{data.get('scene', '')}:{','.join(names)}"
