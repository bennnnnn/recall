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
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.readings import keep_for_turn, kept_for_turn
from app.modules.chat.follow_up_thread import Followed
from app.modules.chat.posed_read import PosedPick, picked, posed_started, stated_problem
from app.modules.chat.prompt_constants.follow_up import follow_up_note
from app.modules.chat.prompt_inject import inject_before_last_user
from app.modules.chat.turn_trace import note_prompt_rule
from app.services.question_parts import part_named
from app.services.text_normalize import collapse_ws

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.modules.chat.turn_prep.context import StreamContext

# The kinds that name the message the line follows.
_FOLLOWS = frozenset({"solve", "change", "explain"})
# A part's label as a line names it: "b", "(b)", "part b", "(ii)".
_PART_LABEL = re.compile(r"^(?:part\s+)?\(?([a-h]|i{1,3}|iv|vi{0,3})\)?$", re.IGNORECASE)
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
    def problem(self) -> str:
        """The problem the line follows: as the user typed it, or as the assistant posed it."""
        if self.role == "user":
            return self.text
        return self.posed or self.asked or self.text


def _part(said: str | None, texts: Sequence[str | None]) -> tuple[str | None, str | None]:
    """The part the line names and its words: a label only when a message labels it so (a
    label no message has names nothing); a step or an item in the line's words."""
    named = collapse_ws(said or "").strip(" .:?")
    if not named:
        return None, None
    label = _PART_LABEL.match(named)
    if label is None:
        return named, None
    for text in texts:
        words = part_named(text, label.group(1)) if text else None
        if words:
            return label.group(1).lower(), words
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
    if ctx.instant_reply or not settings.referent_read_enabled:
        return
    left = deadline - asyncio.get_running_loop().time()
    follow = await follow_up_for_turn(ctx.user_message_content or "", seconds=left)
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


def followed_for_questions(ctx: StreamContext) -> Followed | None:
    """What the follow-up questions under the reply follow: the problem the read named, or
    nothing when the turn's read says the line stands alone; None with neither read, and the
    questions are chosen as before (``follow_up_thread``)."""
    follow = kept_for_turn(_KEPT)
    problem = follow.problem if isinstance(follow, FollowUp) else None
    task = ctx.live_read
    read = (
        task.result()
        if task is not None and task.done() and not task.cancelled() and not task.exception()
        else None
    )
    if problem is None and (read is None or read.follow != "none"):
        return None
    return Followed(problem)
