"""Ordinary chat's shorter prompt: the turn's read calls the message everyday chat, and the
reply gets its turn rules without the packs that drafts, code, lessons and calculations need.

"For ordinary chat, it must be fast" (the owner, 2026-11-22). The everyday model's first word
came 2.8 s after the request on a median prompt of 9.9k tokens, about 1.2 s on 2.5k; most of
the difference was the format contract, the calculation layout and the draft, privacy and
clarification rules every turn carried, chat about dinner included.

The prompt is built before the read is in (``prompt_builder``). A turn whose words ask for
no shape of their own (no draft, code, lesson, chart, subject or several requests;
``prompt_format.allows_ordinary``) also gets its second system message rendered the ordinary
way (``PromptTurn.ordinary``), held beside the prompt. When the read says the message is
everyday chat, with no result to work out, no picture to draw and no hard reasoning
(``is_ordinary``), ``decided_turn`` puts it in place of the full one before anything else
changes the prompt. With no read in time, or any other answer, the full prompt stands.

Only that message changes: the first system message (the same on every turn) and the
history keep their place, so a provider caching the prefix still can.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.modules.chat.turn_decision import TurnDecision

# The effort of a question an ordinary reply answers: one the read calls hard keeps the full
# rules, as its thinking does.
_ORDINARY_EFFORTS = frozenset({"none", "low"})
# A photo above the answer is an everyday reply's; a graph, a diagram, a molecule or a
# painting is drawn under its own contract.
_ORDINARY_PICTURES = frozenset({"none", "photo"})


@dataclass(frozen=True)
class OrdinaryPrompt:
    """The turn's rules message as built, and the same message for ordinary chat."""

    full: str
    compact: str

    def apply(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        """``messages`` with the compact rules in place of the full ones; None when no system
        message holds the full rules as built (something changed them since)."""
        for index, message in enumerate(messages):
            if message.get("role") == "system" and message.get("content") == self.full:
                return [
                    *messages[:index],
                    {**message, "content": self.compact},
                    *messages[index + 1 :],
                ]
        return None


def is_ordinary(read: TurnDecision) -> bool:
    """The read calls the message everyday chat: no subject, no result worked out, no picture
    drawn for it, and not a hard question."""
    return (
        read.subject == "everyday"
        and read.work is not True
        and read.effort in _ORDINARY_EFFORTS
        and (read.picture is None or read.picture in _ORDINARY_PICTURES)
    )
