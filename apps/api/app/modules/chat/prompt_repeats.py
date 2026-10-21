"""An instruction is stated once per prompt, in its last place.

Some instructions reached one prompt twice: a subject's reply policy closes the
system prompt and the verified-solve block before the user turn (and again after a
SymPy tool round), and the contract a lesson or plan gets in the style pack is
repeated beside the user turn. A repeat costs tokens on every turn and tells the
model nothing new. Each keeps only its last copy, the one closest to the user turn,
which is the place the code that repeated it wanted it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.modules.chat.prompt_subjects import SUBJECT_HINTS

# Every subject's reply policy: a solve block and the tool loop repeat it.
REPLY_POLICIES: tuple[str, ...] = tuple(
    policy for hints in SUBJECT_HINTS.values() for policy in hints.closing
)


def last_copies(*groups: Sequence[str]) -> list[list[str]]:
    """The groups' parts in order, a part repeated later (in any group) left out."""
    seen: set[str] = set()
    kept: list[list[str]] = []
    for group in reversed(groups):
        parts: list[str] = []
        for part in reversed(group):
            if part not in seen:
                seen.add(part)
                parts.append(part)
        kept.append(parts[::-1])
    return kept[::-1]


def policies_once(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """``messages`` with each reply policy left only in the last message that states it.

    A message left empty is dropped. The messages are not changed in place.
    """
    out = list(messages)
    for policy in REPLY_POLICIES:
        holders = [index for index, message in enumerate(out) if policy in _text(message)]
        for index in reversed(holders[:-1]):
            content = _without(_text(out[index]), policy)
            if content:
                out[index] = {**out[index], "content": content}
            else:
                del out[index]
    return out


def _text(message: dict[str, Any]) -> str:
    content = message.get("content")
    return content if isinstance(content, str) else ""


def _without(text: str, part: str) -> str:
    """``text`` without every copy of ``part``, each with the space that joined it on."""
    while part in text:
        start = text.index(part)
        before, after = text[:start], text[start + len(part) :]
        head, tail = before.rstrip(), after.lstrip()
        text = f"{head}{before[len(head) :]}{tail}" if head and tail else head or tail
    return text
