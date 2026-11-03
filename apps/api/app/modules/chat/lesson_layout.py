"""Which lesson layout a turn's prompt asks for, and the contract it restates beside the message.

A teach-me ("teach me Python") gets ``TEACHING_HINT``: an outline of a whole subject, or a
lesson on one idea. A walkthrough ("I don't understand recursion") gets ``WALKTHROUGH_HINT``:
a lesson. The style hints decide it (``prompt_format``); this module only reads their choice,
so the contract beside the message and the finalize pass that holds the reply to it
(``lesson_shape``) never disagree with the layout the prompt gave.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from app.modules.chat.prompt_constants.teaching import (
    LESSON_CONTRACT,
    TEACH_CONTRACT,
    TEACHING_HINT,
    WALKTHROUGH_HINT,
)

LessonLayout = Literal["teaching", "walkthrough"]

_CONTRACTS: dict[LessonLayout, str] = {"teaching": TEACH_CONTRACT, "walkthrough": LESSON_CONTRACT}


def lesson_layout_of(style_hints: Sequence[str]) -> LessonLayout | None:
    """The lesson layout among a turn's style hints, or None."""
    if TEACHING_HINT in style_hints:
        return "teaching"
    return "walkthrough" if WALKTHROUGH_HINT in style_hints else None


def lesson_contract(style_hints: Sequence[str]) -> list[str]:
    """The contract restated beside the user's message for the turn's lesson layout."""
    layout = lesson_layout_of(style_hints)
    return [_CONTRACTS[layout]] if layout else []


def prompt_lesson_layout(prompt_messages: Sequence[dict[str, Any]]) -> LessonLayout | None:
    """The lesson layout the turn's prompt carried, read from the contract beside its
    message: the finalize pass holds the reply to what the prompt asked."""
    for message in prompt_messages:
        content = message.get("content")
        if message.get("role") != "system" or not isinstance(content, str):
            continue
        for layout, contract in _CONTRACTS.items():
            if contract in content:
                return layout
    return None
