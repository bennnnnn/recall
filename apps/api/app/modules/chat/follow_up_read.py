"""What a short follow-up line is about, for every subject: one read, for the reply and the
follow-up questions under it.

In a 53-turn Grade 8 physics chat (2026-11-18) "explain step 2", after a water-pressure
answer, explained Newton's second law from seven turns back; "and b?" answered half of part
b; and the questions under three replies were about the problem before. The reply guessed
what the line pointed at, and the questions came from word rules that walk back to the last
line naming a subject.

So the posed read (``posed_read``), begun as the turn loads, names the message a short line
follows, the assistant's or the user's, and the labelled part or step it names. The server
holds it to the chat: the message is one the read was shown, and a part label is one that
message (or the question it answered) labels, whose own words it quotes; a step or an item
is kept in the line's words. Two things use it:

- the reply, told beside the line which message, and which part of it, the line follows
  (``note_the_follow_up``), whatever the subject;
- the follow-up questions, which stay on that problem, or on none when the turn's read says
  the line stands alone (``followed_for_questions``).

With no read in time (off, mocked, failed or slow), nothing is said and the questions are
chosen as before. Nothing here raises into a turn.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.readings import keep_for_turn, kept_for_turn
from app.modules.chat.follow_up_thread import Followed
from app.modules.chat.posed_read import PosedPick, picked, posed_started, stated_problem
from app.modules.chat.prompt_constants.follow_up import follow_up_note
from app.modules.chat.prompt_inject import inject_before_last_user
from app.modules.chat.turn_trace import note_prompt_rule
from app.modules.turn_reading.lesson_flow import active_lesson_step, outline_awaits_pick
from app.services.question_parts import named_label, part_named
from app.services.text_normalize import collapse_ws

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.modules.chat.turn_decision import TurnDecision
    from app.modules.chat.turn_prep.context import StreamContext

# The kinds that name the message the line follows.
_FOLLOWS = frozenset({"solve", "change", "explain"})
_KEPT = "follow_up"


@dataclass(frozen=True)
class FollowUp:
    """The message a short line follows, held to the chat the read saw."""

    kind: str
    role: str
    text: str
    # The user's line an assistant message answered, when it follows one.
    asked: str | None
    # The problem as the read copied it, when the message holds the copy word for word.
    posed: str | None
    # The part or step the line names ("b", "step 2"), and a labelled part's own words.
    part: str | None = None
    part_text: str | None = None

    @property
    def problem(self) -> str | None:
        """The problem the line follows: as the user typed it, as the assistant posed it, or
        the user's line the reply answered; None for a reply whose question the read was not
        shown (a whole reply is no problem to ask questions about)."""
        if self.role == "user":
            return self.text
        return self.posed or self.asked


def _part(said: str | None, texts: Sequence[str | None]) -> tuple[str | None, str | None]:
    """The part the line names and its words: a label only when a message labels it so (a
    label no message has names nothing); a step or an item in the line's words."""
    named = collapse_ws(said or "").strip(" .:?")
    if not named:
        return None, None
    label = named_label(named)
    if label is None:
        return named, None
    for text in texts:
        words = part_named(text, label) if text else None
        if words:
            return label, words
    return None, None


def follow_up_from(pick: PosedPick | None, exchanges: Sequence[tuple[str, str]]) -> FollowUp | None:
    """The message ``pick`` names, checked against the chat it read; None when it names none."""
    if pick is None or pick.kind not in _FOLLOWS or pick.message is None:
        return None
    if not 1 <= pick.message <= len(exchanges):
        return None
    index = pick.message - 1
    role, text = exchanges[index]
    before = exchanges[index - 1] if index > 0 else None
    asked = before[1] if role == "assistant" and before and before[0] == "user" else None
    part, words = _part(pick.part, (text, asked))
    posed = stated_problem(role, text, pick.problem)
    return FollowUp(
        pick.kind, role, text, asked, posed if role == "assistant" else None, part, words
    )


async def follow_up_for_turn(line: str, *, seconds: float) -> FollowUp | None:
    """The begun read's answer for ``line``, waited for at most ``seconds``, and kept
    for the turn's follow-up questions; None with no read."""
    begun = posed_started(line)
    if begun is None:
        return None
    exchanges, task = begun
    follow = follow_up_from(await picked(task, max(0.0, seconds)), exchanges)
    keep_for_turn(_KEPT, follow)
    return follow


async def note_the_follow_up(ctx: StreamContext, settings: Settings, deadline: float) -> None:
    """Beside the line, the message and part it follows, read by a model and held to the
    chat: "explain step 2" is about the answer just above, "and b?" about part b of the
    problem. Waited for no later than ``deadline`` (the reply's wait for the turn's read)."""
    if ctx.instant_reply or not settings.referent_read_enabled or _reads_its_own_way(ctx):
        return
    left = deadline - asyncio.get_running_loop().time()
    # Small talk, or a line the turn's read says stands alone, waits for nothing: a read that
    # is in by now still counts.
    seconds = 0.0 if ctx.lightweight_turn or _stands_alone(ctx) else left
    follow = await follow_up_for_turn(ctx.user_message_content or "", seconds=seconds)
    if follow is None:
        return
    note_prompt_rule(f"follow_up.{follow.kind}")
    note = follow_up_note(
        role=follow.role,
        text=follow.text,
        asked=follow.asked,
        part=follow.part,
        part_text=follow.part_text,
    )
    ctx.prompt_messages = inject_before_last_user(ctx.prompt_messages, note)


def _reads_its_own_way(ctx: StreamContext) -> bool:
    """A lesson's step, an outline awaiting a pick and the turn after a clarify card read the
    reply their own way (``message_notes``), as the turn read's notes leave them."""
    recent = ctx.recent_messages
    return bool(ctx.after_card or active_lesson_step(recent) or outline_awaits_pick(recent))


def _turn_read(ctx: StreamContext) -> TurnDecision | None:
    task = ctx.live_read
    if task is None or not task.done() or task.cancelled() or task.exception() is not None:
        return None
    return task.result()


def _stands_alone(ctx: StreamContext) -> bool:
    read = _turn_read(ctx)
    return read is not None and read.follow == "none"


def followed_for_questions(ctx: StreamContext) -> Followed | None:
    """What the follow-up questions under the reply follow: the problem the read named, or
    nothing when the turn's read says the line stands alone; None with neither read, and the
    questions are chosen as before (``follow_up_thread``)."""
    follow = kept_for_turn(_KEPT)
    if not isinstance(follow, FollowUp):
        follow = _read_by_now(ctx.user_message_content or "")
    problem = follow.problem if follow is not None else None
    if problem is None and not _stands_alone(ctx):
        return None
    return Followed(problem)


def _read_by_now(line: str) -> FollowUp | None:
    """The begun read's answer when it is in by now, for a turn that never noted it: an
    instant reply ("and b?" answered by the solver) asks for no note, and its follow-up
    questions still follow the problem the read named (review)."""
    begun = posed_started(line)
    if begun is None:
        return None
    exchanges, task = begun
    if not task.done() or task.cancelled() or task.exception() is not None:
        return None
    return follow_up_from(task.result(), exchanges)
