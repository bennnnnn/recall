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
from app.modules.chat.figure_turn import earlier_user_lines, read_asks_for_a_picture
from app.modules.chat.finalize_subjects import fallback_text
from app.modules.chat.prompt_inject import inject_before_last_user
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_trace import note_prompt_rule
from app.modules.turn_reading.turn import current_turn_reading
from app.services.md_fence_scan import iter_fences
from app.services.part_place import part_key, place_after_part
from app.services.solving import (
    SubjectName,
    VerifiedMathBlock,
    VerifiedPhysicsBlock,
    VerifiedSolveBlock,
)
from app.services.subjects.registry import SubjectFigure, subject_adapter

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState
    from app.modules.chat.turn_prep.context import StreamContext

logger = logging.getLogger(__name__)

# A reply in parts draws at most this many pictures, one per part.
_MOST_PARTS = 4

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


# A line with a digit or a relation sign ("x ≥ 4 on a number line") may ask for a maths
# picture: such a line waits for the read before its reply is asked for a description.
_MATHS_MARK = re.compile("[0-9<>=\u2264\u2265\u2212+/^]")


def may_be_a_maths_picture(line: str) -> bool:
    return _MATHS_MARK.search(line) is not None


# The pictures the read may ask for that a description draws: a figure, and a graph (kind
# "plot").
_DESCRIBED = frozenset({"diagram", "graph"})


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


def _a_physics_turn(ctx: StreamContext) -> bool:
    """The subject readers read the message as physics, or a physics solve verified it."""
    if isinstance(ctx.verified_subject, VerifiedPhysicsBlock):
        return True
    kept = current_turn_reading()
    return kept is not None and kept.text == ctx.user_message_content and kept.subject == "physics"


def _physics_read(ctx: StreamContext) -> bool:
    """The turn is physics', by its read or its readers: its words' quantities (a
    particle's v(t)) are physics' to read for the graph (``graph_facts``)."""
    if _a_physics_turn(ctx):
        return True  # u5-088's kinematics, which the read may call maths
    read = ctx.live_read
    if read is None or not read.done() or read.cancelled() or read.exception() is not None:
        return False
    decision = read.result()
    return decision is not None and decision.subject == "physics"


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


def _described_by(ctx: StreamContext, read: TurnDecision) -> SubjectName | None:
    """The subject whose reply describes the picture the read asks for: maths for its
    figure or graph and for a physics question's graph (drawn as any curve is), physics for
    a physics diagram (a field's lines); none when a physics card already draws its graph
    against time. One check, the read's own (``read_asks_for_a_picture``)."""
    if _solver_graphed(ctx.verified_subject):
        return None
    if not read_asks_for_a_picture(read, described=True) or read.picture not in _DESCRIBED:
        return None
    return "physics" if read.subject == "physics" and read.picture == "diagram" else "math"


def _setup_of(read: TurnDecision) -> SubjectName | None:
    """Physics' scene is its setup's picture: a problem whose read asks to see nothing gets
    it too, as maths' teaching figure does, when no solve drew one (never a picture asked
    for, which ``_described_by`` holds to the read's asks check)."""
    return "physics" if read.subject == "physics" and read.picture == "none" else None


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
    subject = _described_by(ctx, read) if read is not None else None
    if read is None or subject is None:
        return
    # Physics' own picture (a field's lines) only when physics is on and its solve drew none
    # ("calculate the field and draw its lines" gives way, so the reply can describe them).
    if subject == "physics" and (
        not subject_adapter("physics").enabled(settings) or solve_draws(verified, read.picture)
    ):
        return
    ctx.instant_reply = None
    note_prompt_rule("subject.draw_over_instant")


async def ask_for_a_drawing(
    ctx: StreamContext, settings: Settings, read: TurnDecision | None, deadline: float
) -> None:
    """A subject's draw contract beside the message, when it asks to see a picture that
    subject's reply describes: maths' figure or graph (a physics graph's too), physics'
    field. ``deadline``: the loop time the reply stops waiting for the read."""
    if not settings.draw_descriptions_enabled or ctx.drawing is not None:
        return
    if ctx.instant_reply is not None:
        return
    if read is None:
        read = await _read_for_a_picture(ctx, deadline)
    asked: Literal["read", "words"] | None = None
    subject: SubjectName | None = None
    if read is not None and read.subject is not None and read.picture is not None:
        subject = _described_by(ctx, read) or _setup_of(read)
        asked = "read" if subject is not None else None
    elif _asks_in_words(ctx):
        subject = _words_subject(ctx)
        asked = "words" if subject is not None else None
    if asked is None or subject is None:
        return
    # A physics solve that drew the picture asked for (a scene, a circuit, rays) needs no
    # description; one that drew none ("calculate the field strength and draw its lines")
    # still gets the contract.
    kind = read.picture if read is not None and read.picture is not None else "diagram"
    if subject == "physics" and solve_draws(ctx.verified_subject, kind):
        return
    # A solve that drew its scene gets no second one ("hang over a pulley ... and sketch a
    # velocity-time graph" drew the Atwood machine twice; Gemini, PR #2490). A physics graph
    # is maths' to draw (``_described_by``), never a scene.
    if subject == "physics" and solve_draws(ctx.verified_subject, "diagram"):
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
    # The problem a follow-up points to, as the turn's resolution rewrote it, else the line.
    question = ctx.followup_problem or ctx.user_message_content or ""
    contract = "\n".join(
        part
        for part in (
            figure.contract_for(question, sees),
            _physics_graph(read, question, settings),
        )
        if part
    )
    if not contract:
        return
    ctx.drawing = ReplyDrawing(asked, subject=subject)
    ctx.prompt_messages = inject_before_last_user(ctx.prompt_messages, contract)
    note_prompt_rule(f"subject.draw_{asked}" if subject == "math" else f"{subject}.draw_{asked}")


def _physics_graph(read: TurnDecision | None, question: str, settings: Settings) -> str:
    """A physics graph is maths' to draw from a formula the question writes, and physics'
    from a motion in stages ("6 km/h for 5 min, then 2 km/h for 3 min"): its reply gets
    physics' contract beside maths' (``physics.scene_drawing.motion_graph``)."""
    physics = subject_adapter("physics")
    if read is None or read.subject != "physics" or read.picture != "graph":
        return ""
    if physics.figure is None or not physics.enabled(settings):
        return ""  # physics turned off draws nothing of its own (review)
    return physics.figure.contract_for(question, True, graph=True)


def _still_wanted(ctx: StreamContext, drawing: ReplyDrawing) -> bool:
    """A contract asked for on the message's words holds only if the read, in by now, does
    not say otherwise."""
    if drawing.asked == "read":
        return True
    decision = _read_in(ctx)
    if decision is None or decision.subject is None or decision.picture is None:
        return True
    # A setup's scene the read would ask for too ("none": a problem's own picture) stands,
    # unless the read says the message works nothing out ("just explain").
    setup = _setup_of(decision) if decision.work is not False else None
    return drawing.subject in (_described_by(ctx, decision), setup)


def _asks_to_see(ctx: StreamContext) -> bool:
    """The message asks to see a picture, unless the read, in by now, says it asks for none
    ("Don't draw the field, just explain"): then only a problem's setup is drawn."""
    decision = _read_in(ctx)
    return decision is None or decision.picture != "none"


def _read_in(ctx: StreamContext) -> TurnDecision | None:
    """The turn's read, when it is in by now and answered."""
    read = ctx.live_read
    if read is None or not read.done() or read.cancelled() or read.exception() is not None:
        return None
    return read.result()


async def _described(
    state: FinalizeState,
    drawing: ReplyDrawing,
    figure: SubjectFigure,
    descriptions: list[str],
    texts: list[str],
    reply: str,
    problem: str | None,
) -> list[str]:
    """The pictures the descriptions draw: the drawing subject's, and on a physics turn
    whose graph maths' figure did not draw, physics' own (a motion in stages)."""
    ctx = state.ctx
    physics = _physics_read(ctx)
    facts = subject_adapter("physics").graph_facts if physics else None
    asks = _asks_to_see(ctx)
    fences = await figure.described(
        descriptions, texts, reply, state.settings, facts, problem, asks
    )
    if fences or drawing.subject != "math" or not physics:
        return list(fences)
    physics_figure = subject_adapter("physics").figure
    if physics_figure is None or not subject_adapter("physics").enabled(state.settings):
        return []
    scene_texts = [ctx.followup_problem, *texts] if ctx.followup_problem else texts
    drawn = await physics_figure.described(
        descriptions, scene_texts, reply, state.settings, None, None, asks
    )
    # The graph asked for, never a scene or a field in its place.
    return [fence for fence in drawn if any(f.lang == "graph" for f in iter_fences(fence))]


def _part_of(body: str) -> str | None:
    """The part a description says it draws ("part": "b"), or None."""
    try:
        data = json.loads(body)
    except ValueError:
        return None
    return part_key(data.get("part")) if isinstance(data, dict) else None


async def _by_part(
    state: FinalizeState,
    drawing: ReplyDrawing,
    figure: SubjectFigure,
    descriptions: list[str],
    texts: list[str],
    text: str,
    problem: str | None,
) -> tuple[str, list[str]] | None:
    """A reply in parts whose descriptions name their parts: each picture drawn on its own and
    placed right after its part is answered (owner, 2026-11-21: never all of them at the end).
    None when no description names a part the reply has, so the pictures go under it."""
    descriptions = descriptions[:_MOST_PARTS]
    parts = [_part_of(body) for body in descriptions]
    logger.info("described pictures: %d, parts %s", len(descriptions), parts)
    if not any(key is not None and place_after_part(text, key, "") for key in parts):
        return None
    fences: list[str] = []
    under: list[str] = []
    for key, body in zip(parts, descriptions, strict=True):
        drawn = await _described(state, drawing, figure, [body], texts, text, problem)
        fence = drawn[0] if drawn else None
        if fence is None or fence in fences:
            continue
        fences.append(fence)
        placed = place_after_part(text, key, fence) if key is not None else None
        if placed is None:
            under.append(fence)
        else:
            text = placed
    text = text.rstrip()
    if under:
        text = "\n\n".join([text, *under]) if text else "\n\n".join(under)
    return (f"{text}\n", fences) if fences else None


async def attach_drawing(state: FinalizeState) -> str:
    """The reply's described picture under it, what stood in for it taken out; in a reply in
    parts, each part's picture right after that part's answer."""
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
    texts = [line, *earlier_user_lines(ctx.recent_messages, line)]
    # A physics scene is of the problem a follow-up points back to, when there is one
    # (maths reads its own follow-ups from the lines); a field picture, of the line.
    problem = ctx.followup_problem if drawing.subject == "physics" else None
    try:
        parted = await _by_part(state, drawing, figure, descriptions, texts, text, problem)
        fences = (
            parted[1]
            if parted is not None
            else await _described(state, drawing, figure, descriptions, texts, text, problem)
        )
    except Exception as exc:  # A drawing that fails is no drawing: the reply stands.
        logger.info("described picture failed (%s)", type(exc).__name__)
        return text
    if not fences:
        return text
    drawing.fences = list(fences)
    if parted is not None:
        text = parted[0]
    else:
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
