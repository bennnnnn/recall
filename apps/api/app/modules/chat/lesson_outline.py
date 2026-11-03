# ruff: noqa: RUF001
"""An outline of a whole subject, held to its shape: numbered topics with bold names, then
its closing question last (``prompt_constants.teaching._SUBJECT_OUTLINE``).

The next turn reads an outline by its closing question (``outline_awaits_pick``), and the
learner picks a topic by its number and name. Live (2026-11-02), "teach me python" was
answered with only two questions about the learner's level, "teach me american history"
with the eras as plain numbered lines, and an outline ended on a line after its question.

What the model wrote stays; only the missing parts are added. Each numbered topic gets its
name in bold ("1. Colonial America - …" -> "1. **Colonial America** — …"). A reply with no
list gets the subject's topics from a cheap model (``lesson_calls.subject_topics``), laid
out above its questions. A question that is not last moves to the end, and a reply that
asks nothing ends on the server's own question, in the reply's language. A reply that only
picks up where memory says the learner got to ("Last time we got to dictionaries. Pick up
with functions, or start over?") gets no list: the prompt asks for exactly that.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.modules.chat.lesson_blocks import blocks, is_list, is_question, joined
from app.modules.chat.lesson_calls import OutlineTopics, subject_topics
from app.modules.chat.lesson_copy import LessonCopy
from app.modules.chat.lesson_progress import PROGRESS_LINE
from app.modules.turn_reading.lesson_flow import outline_topics as count_topics
from app.services.md_fence_scan import line_fences, without_fences

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

# Fewer numbered topics than this is no outline yet.
MIN_TOPICS = 3
_LABEL_WORDS = 8
_ITEM = re.compile(
    r"^(?P<lead>\s{0,3}\d{1,2}[.)]\s+)(?P<emoji>[^\w\s*`\[(]{1,4}\s+)?(?P<body>\S.*)$"
)
_LABELLED = re.compile(r"^(?P<label>[^*`\n:—–]{1,60}?)(?:\s+[-—–]\s+|:\s+)(?P<rest>\S.*)$")
_SENTENCE = re.compile(r"[.!?;]")
_NUMBERED_ITEM = re.compile(r"^\s{0,3}\d{1,2}[.)]\s", re.MULTILINE)


def numbered_items(text: str) -> int:
    """How many numbered list items the reply has outside fences, bold names or not."""
    return len(_NUMBERED_ITEM.findall(without_fences(text, "")))


def _bold_item(line: str) -> str:
    item = _ITEM.match(line)
    if item is None or item.group("body").startswith(("**", "__")):
        return line
    lead, emoji, body = item.group("lead"), item.group("emoji") or "", item.group("body")
    labelled = _LABELLED.match(body)
    if labelled is not None and len(labelled.group("label").split()) <= _LABEL_WORDS:
        label = labelled.group("label").strip()
        return f"{lead}{emoji}**{label}** — {labelled.group('rest')}"
    if len(body.split()) <= _LABEL_WORDS and not _SENTENCE.search(body.rstrip(".")):
        return f"{lead}{emoji}**{body.rstrip('.').strip()}**"
    return line


def bold_topic_names(text: str) -> str:
    """Each numbered topic outside fences with its name in bold."""
    lines = text.split("\n")
    owners = line_fences(text)
    return "\n".join(
        line if owner is not None else _bold_item(line)
        for line, owner in zip(lines, owners, strict=True)
    )


def _topic_list(found: OutlineTopics) -> str:
    return "\n".join(
        f"{n}. **{topic.name}**" + (f" — {topic.what}" if topic.what else "")
        for n, topic in enumerate(found.topics, 1)
    )


def with_topics(text: str, found: OutlineTopics) -> str:
    """The topic list placed above the reply's closing questions (or last)."""
    parts = blocks(text)
    at = len(parts)
    while at > 1 and is_question(parts[at - 1]):
        at -= 1
    return joined([*parts[:at], _topic_list(found), *parts[at:]])


def ending_on_question(text: str, copy: LessonCopy) -> str:
    """The outline with its question last: a question after the list moves to the end;
    with none, the server's own question closes it."""
    parts = blocks(text)
    if parts and is_question(parts[-1].strip().split("\n")[-1]):
        return text
    last_list = max((i for i, part in enumerate(parts) if is_list(part)), default=-1)
    asks = [i for i, part in enumerate(parts) if i > last_list and is_question(part)]
    if asks:
        moved = asks[-1]
        return joined([*parts[:moved], *parts[moved + 1 :], parts[moved]])
    return joined([*parts, copy.where_to_start])


def _resumes_a_lesson(state: FinalizeState) -> bool:
    """Memory says the learner is already on a lesson: the reply picks up, with no list."""
    return any(
        isinstance(message.get("content"), str) and PROGRESS_LINE.search(message["content"])
        for message in state.ctx.prompt_messages
        if message.get("role") == "system"
    )


async def hold_outline(state: FinalizeState, copy: LessonCopy) -> str:
    """The pass's outline step (``lesson_shape``)."""
    text = bold_topic_names(state.text)
    # A list of its own whose names could not be told apart stays the model's.
    if count_topics(text) < MIN_TOPICS and numbered_items(text) < MIN_TOPICS:
        if _resumes_a_lesson(state):
            return text
        found = await subject_topics(state)
        if found is None:
            return text
        text = with_topics(text, found)
    return ending_on_question(text, copy)
