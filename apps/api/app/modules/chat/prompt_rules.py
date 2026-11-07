"""An ordered table of prompt rules: when each applies to a turn and the text it adds.

The format hints (``prompt_format.HINT_RULES``) and the prompt sections
(``prompt_sections``) are tables of these.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.modules.chat.turn_trace import note_prompt_rule


@dataclass(frozen=True)
class PromptRule[T]:
    """An ordered prompt rule: when it applies to a turn, the text it adds, and the name
    a turn's trace calls it (``turn_trace``), unique in its table."""

    applies: Callable[[T], bool]
    render: Callable[[T], Sequence[str]]
    name: str


def render_rules[T](rules: Sequence[PromptRule[T]], turn: T, *, table: str = "rules") -> list[str]:
    """Every applying rule's text, in table order; the turn's trace names each one that
    added text (``table.name``)."""
    texts: list[str] = []
    for rule in rules:
        if not rule.applies(turn):
            continue
        added = rule.render(turn)
        if added:
            note_prompt_rule(f"{table}.{rule.name}")
        texts.extend(added)
    return texts
