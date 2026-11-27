"""The ```steps card, when the turn's read says the answer is one procedure done in order.

"If I ask how to do something, I need to see a flow with arrows" (the owner, 2026-11-14): the
phone draws a ```steps card as boxes joined by arrows. A word rule gave it to every "how to
…" and "how do I …": "How to look handsome" got six independent tips in the card, its reply
opening "It's a how-to" (the owner, 2026-11-27). Tips, ways and advice are the scan layout's
numbered list (``prompt_constants.format.SCAN_LAYOUT``); the card is for a task or a method
carried out step after step (tie a tie, renew a passport, balance a chemical equation).

The read decides (``decider_read.STEPS_QUESTION``), on a turn whose words left its layout
open (``prompt_format.layout_is_open``: no draft, code, lesson, plan, comparison, checklist
and the like). Its note goes beside the message, after the prompt was built, so the rules
before the history stay as they were. Steps asked for in words ("step by step", "walk me
through") get the card from the prompt itself (``format.asks_for_steps``). No read in time,
or a read that says anything else, and the reply keeps the scan layout: a numbered list is
never wrong for a procedure, while a card on tips is.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.chat.prompt_constants.format import STEPS_FORMAT_HINT
from app.modules.chat.prompt_inject import inject_before_last_user
from app.modules.chat.turn_trace import note_prompt_rule

if TYPE_CHECKING:
    from app.modules.chat.turn_decision import TurnDecision
    from app.modules.chat.turn_prep.context import StreamContext

# A photo above the steps is an everyday reply's; a graph, a diagram, a molecule or a
# painting is drawn under its own contract.
_STEPS_PICTURES = frozenset({"none", "photo"})


def gives_the_steps_card(ctx: StreamContext, read: TurnDecision | None) -> bool:
    """The read calls the answer one procedure, on a turn whose layout its words left open,
    and no server path worked numbers for it (a solve, a money card, a calculation laid out)."""
    if read is None or read.steps is not True or not ctx.steps_open:
        return False
    worked = ctx.verified_subject is not None or ctx.money is not None or ctx.worked is not None
    if worked or ctx.solver_unverified or ctx.instant_reply:
        return False
    if read.subject == "money" or read.work is True:
        return False
    return read.picture is None or read.picture in _STEPS_PICTURES


def lay_out_the_steps(ctx: StreamContext, read: TurnDecision | None) -> None:
    """The steps card's layout beside the message when the read calls the answer one
    procedure; otherwise the prompt stands, and the reply takes the scan layout."""
    if not gives_the_steps_card(ctx, read):
        return
    note_prompt_rule("read.steps")
    ctx.prompt_messages = inject_before_last_user(ctx.prompt_messages, STEPS_FORMAT_HINT)
