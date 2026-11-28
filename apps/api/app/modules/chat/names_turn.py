"""Each recommended name written as a link, when the turn's read says the answer names things
to look up.

"We need a link to any name that needs a user to check" (the owner, 2026-11-27). The rules
ask for it on every turn (``prompt_constants.format.NAME_LINK_RULE``), and the reply's model
followed them on 12 of 18 recommending replies. The read decides (``decider_read.
NAMES_QUESTION``, asked in the steps question's call), and its note goes beside the message,
after the prompt was built, as the steps card's does (``steps_turn``). No read in time, or a
read that says anything else, and the rules alone ask. Where each link opens is the server's
(``reply_links``, ``name_links``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.chat.prompt_constants.format import NAME_LINK_NOTE
from app.modules.chat.prompt_inject import inject_before_last_user
from app.modules.chat.turn_trace import note_prompt_rule

if TYPE_CHECKING:
    from app.modules.chat.turn_decision import TurnDecision
    from app.modules.chat.turn_prep.context import StreamContext


def link_the_names(ctx: StreamContext, read: TurnDecision | None) -> None:
    """The names' note beside the message when the read says the answer recommends named
    things to look up and no server path answered or worked its numbers; otherwise the prompt
    stands. Any layout takes it, a ranking's ("best restaurants in …") or a choice's ("which
    museums should I visit?") as well as the scan layout's."""
    if read is None or read.names is not True:
        return
    if ctx.instant_reply or ctx.verified_subject is not None or ctx.money is not None:
        return
    note_prompt_rule("read.names")
    ctx.prompt_messages = inject_before_last_user(ctx.prompt_messages, NAME_LINK_NOTE)
