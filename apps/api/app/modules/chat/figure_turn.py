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
import json
import logging
import re
from collections.abc import Iterator, Sequence
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
# How many earlier user messages "draw it" may point back to, with no read to name them.
_EARLIER = 3
_DIGIT = re.compile(r"\d")
_LABEL_KEYS = frozenset({"label", "labels"})
# The most messages of one problem the figure reads: the problem and its follow-ups.
_TOPIC = 6
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


def earlier_user_lines(recent: Sequence[Any] | None, line: str, most: int = _EARLIER) -> list[str]:
    """The user's earlier messages, newest first, without the turn's own line: ``most``."""
    texts = [
        content
        for message in recent or []
        if getattr(message, "role", None) == "user"
        and isinstance(content := getattr(message, "content", None), str)
        and content.strip()
    ]
    if texts and collapse_ws(texts[-1]) == collapse_ws(line):
        texts.pop()
    return list(reversed(texts))[:most]


# The turn's read, kept for the turn (``core.readings.keep_for_turn``) by the stream.
LIVE_READ = "live_read"


async def will_draw(settings: Settings) -> bool:
    """Whether this turn's figure path will draw, as the prep must know before it leaves a
    shape to it: the turn's read, waited on for at most its usual wait, names a subject
    with a figure and wants one. No read, a late one or an empty one: no (a review,
    2026-11-21: "draw it" lost maths' drawing to a read that came back empty)."""
    from app.core.readings import kept_for_turn

    read = kept_for_turn(LIVE_READ)
    if not settings.figure_read_enabled or not isinstance(read, asyncio.Task):
        return False
    await asyncio.wait([read], timeout=settings.live_read_wait_seconds)
    return _figure_wanted(read) is not None


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
    recent = list(ctx.recent_messages or [])
    solved_by = getattr(ctx.verified_subject, "subject", None)
    return asyncio.create_task(_draw(settings, ctx.live_read, line, recent, solved_by))


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


def read_asks_for_a_picture(decision: TurnDecision, *, described: bool = False) -> bool:
    """The read calls the message a maths question asking to see a graph or a diagram, or
    a physics question asking to see a graph (drawn as maths draws one), or, for a picture
    the reply ``described`` (``drawing_turn``), a physics diagram (a field's lines): the one
    check every picture path asks of the read."""
    if decision.subject == "physics":
        return decision.picture == "graph" or (described and decision.picture == "diagram")
    return decision.subject == "maths" and decision.picture in _DRAWN


async def _draw(
    settings: Settings,
    read: asyncio.Task[TurnDecision | None],
    line: str,
    recent: Sequence[Any],
    solved_by: SubjectName | None = None,
) -> str | None:
    # Waited on, never awaited: the reply may cancel the read when it stops waiting for it.
    await asyncio.wait([read])
    wanted = _figure_wanted(read)
    figure = _figure(wanted[0]) if wanted is not None else None
    # A solved turn gets only its own subject's figure, never another's over its solve.
    if wanted is None or figure is None or solved_by not in (None, wanted[0]):
        return None
    topic = await _topic(settings, read, line, recent)
    fence = await figure.draw(line, topic, settings, asked=wanted[1] == "asked")
    # A picture no one asked for teaches only what it names: "What is the formula for the
    # area of a circle?" got a bare circle, nothing on it (live, 2026-11-21).
    if fence and wanted[1] != "asked" and _kind(fence) == "geometry" and not _names_anything(fence):
        logger.info("figure left out: it names nothing")
        return None
    logger.info(
        "figure %s: %s (%d earlier lines)",
        wanted[1],
        _kind(fence) if fence else "none drawn",
        len(topic),
    )
    return fence


async def _topic(
    settings: Settings,
    read: asyncio.Task[TurnDecision | None],
    line: str,
    recent: Sequence[Any],
) -> list[str]:
    """The earlier messages the figure reads with the line: the conversation's current
    problem, from the message that set it to the follow-ups since, oldest first.

    A message that stands alone (follow none) gets none: a rectangle's area after a
    question about vectors drew nothing, read beside the vectors (owner, 2026-11-20). One
    that follows on gets the problem it follows, named by the chat's referent read ("draw
    it") or continuation read ("find the diagonal"): "Draw it" after "If a rectangle is 4 by
    5 …" and "Find the diagonal" read the three last messages, vectors among them, and drew
    nothing. With neither read, the last few user messages, as before."""
    from app.modules.chat.referent_read import (
        asks_for_a_referent,
        continuation_for_turn,
        referent_for_turn,
    )
    from app.modules.turn_reading.continued_problem import adds_to_problem

    decision = read.result() if read.done() and not read.cancelled() else None
    if decision is not None and decision.follow == "none":
        return []
    problem: str | None = None
    if asks_for_a_referent(line):
        referent = await referent_for_turn(settings, line, recent)
        problem = referent.problem if referent is not None else None
    elif adds_to_problem(line):
        problem = await continuation_for_turn(settings, line, recent)
    # A named problem is looked for further back than the plain window: "Draw it" after the
    # problem and three follow-ups found no start in the last three and lost the follow-ups
    # (a review, 2026-11-21); ``topic_lines`` keeps the problem and at most ``_TOPIC`` lines.
    users = list(reversed(earlier_user_lines(recent, line, _TOPIC if problem else _EARLIER)))
    return topic_lines(users, problem) if problem else users


def topic_lines(users: Sequence[str], problem: str) -> list[str]:
    """The user's messages from the one that set ``problem`` to the latest, oldest first:
    the problem and every follow-up since ("Find the diagonal", then "Draw it"). A problem
    that names no message of these is given whole."""
    whole = collapse_ws(problem)
    # The problem's text begins with the message that set it (later pieces are added after):
    # the latest message it begins with, so a short "5" inside it is never taken for its start.
    for index in range(len(users) - 1, -1, -1):
        text = collapse_ws(users[index])
        if text and whole.startswith(text):
            return list(users[index:])[-_TOPIC:]
    return [problem]


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


def _spec(fence: str) -> Any:
    body = fence.split("\n", 1)[1] if "\n" in fence else ""
    try:
        return json.loads(body.rsplit("```", 1)[0])
    except ValueError:
        return None


def _shows_a_value(fence: str) -> bool:
    """Whether a picture labels any number: a side's "8 cm", an angle's "35°"."""
    return any(_DIGIT.search(label) for label in _labels(_spec(fence)))


def _names_anything(fence: str) -> bool:
    """Whether a picture labels or letters anything: a value, a letter ("x", "r"), a
    point's name drawn beside it ("O", "A": ``show``); a vertex kept unlettered is none."""
    spec = _spec(fence)
    if any(label.strip() for label in _labels(spec)):
        return True
    points = spec.get("points", []) if isinstance(spec, dict) else []
    return any(isinstance(point, dict) and point.get("show") is True for point in points)


def _labels(value: Any, *, inside: bool = False) -> Iterator[str]:
    """Every label's text: a part's "label", and the strings of a "labels" table."""
    if isinstance(value, str):
        if inside:
            yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _labels(item, inside=inside or key in _LABEL_KEYS)
    elif isinstance(value, list):
        for item in value:
            yield from _labels(item, inside=inside)


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
        logger.info("figure late: not drawn within %.1f s", state.settings.figure_wait_seconds)
        stop_figure(ctx)
        return state.text
    if task.cancelled() or task.exception() is not None:
        logger.info("figure task failed: %r", None if task.cancelled() else task.exception())
        return state.text
    fence = task.result()
    # The reply's own described picture of that kind, checked and drawn, stands
    # (``drawing_turn``); one of the other kind leaves room for this one. One that shows
    # none of the question's values gives way to the figure that does: "Draw it" after a
    # rectangle's 8 cm, 6 cm and diagonal got the reply's bare 3-by-2 rectangle, and this
    # figure, the 8 by 6 with its diagonals, was dropped (live, 2026-11-21).
    if not fence:
        return state.text
    reply = state.text
    same = [drawn_fence for drawn_fence in drawn if _kind(drawn_fence) == _kind(fence)]
    if same:
        bare = [drawn_fence for drawn_fence in same if not _shows_a_value(drawn_fence)]
        if len(bare) < len(same) or not _shows_a_value(fence):
            return state.text
        reply, drawn = _without(reply, bare), [f for f in drawn if f not in bare]
    if not figure.adds_to(_without(reply, drawn), fence):
        logger.info("figure left out: the reply already shows it")
        return state.text
    text = figure.without_substitutes(reply, fence).rstrip()
    text = f"{text}\n\n{fence}\n" if text else f"{fence}\n"
    # Committed, so a later pass that falls back keeps the picture.
    state.committed = fallback_text(text, server_text=state.server_text)
    return text
