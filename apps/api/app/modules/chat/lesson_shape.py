"""Finalize pass: a lesson reply carries its title and practice card, an outline its topics
and closing question, whatever the model wrote.

The app reads both shapes back. A lesson is ``### Lesson N: <topic>`` and a ```quiz card
(``lesson_flow.lesson_step``): the next turn grades the card and teaches Lesson N+1, and the
chat's "Learning X: reached Lesson N" memory line is written from the title. An outline ends
on its question, and the next turn starts Lesson 1 from the learner's pick.

The prompt asks for both (``TEACHING_HINT``, ``WALKTHROUGH_HINT``, and the contract beside
the message), and prompts do not hold: in the behaviour battery (2026-11-02) "I don't
understand recursion" got a good explanation with no title and no card on every run, and
"teach me python" sometimes got only questions about the learner's level. So the server
holds the shape, for the turn whose prompt carried the lesson contract
(``lesson_layout.prompt_lesson_layout``):

- A walkthrough is a lesson, unless the reply only asks back in a few lines ("Can you paste
  the message?"): the model read the message as no topic, and there is nothing to practise.
  A teach-me is a lesson when the reply teaches (a title, a card, code, numbered sections,
  or a long explanation with no topic list), else an outline (``lesson_outline``).
- A lesson missing its card gets one written from the lesson by a cheap model
  (``lesson_calls.lesson_practice``), under the lesson's own "Your turn" heading, which
  replaces the prose practice under it, or under a new one that replaces a closing question.
  A lesson missing its title gets ``### Lesson N: <topic>`` after its opening hook: the topic
  as the learner named it, N one past the chat's last lesson. Title and card land together
  or not at all: a call that fails leaves the reply as written.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from app.modules.chat.lesson_blocks import blocks, is_heading, is_paragraph, is_question, joined
from app.modules.chat.lesson_calls import QuizCard, lesson_practice
from app.modules.chat.lesson_copy import LessonCopy, lesson_copy
from app.modules.chat.lesson_layout import prompt_lesson_layout
from app.modules.chat.lesson_outline import MIN_TOPICS, hold_outline, numbered_items
from app.modules.turn_reading.lesson_flow import has_lesson_title, lesson_step, lesson_topic
from app.services.md_fence_scan import iter_fences, without_fences

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

# A teach-me reply with no topic list and more prose than an outline's 150 words teaches.
_OUTLINE_MAX_WORDS = 150
# A reply this short that ends on a question asked back instead of teaching.
_ASKS_BACK_MAX_WORDS = 80
# A closing question longer than this is part of the lesson, not a sign-off.
_CLOSER_MAX_CHARS = 400
_NUMBERED_SECTION = re.compile(r"^\s{0,3}#{2,4}\s+\d{1,2}[.)]\s", re.MULTILINE)
# A heading's marks and section number, before its words.
_HEADING_NAME = re.compile(r"^#{1,6}\s+(?:\*\*)?(?:\d{1,2}[.)]\s+)?")


def teaches(text: str) -> bool:
    """A teach-me reply that is a lesson, not an outline of the subject."""
    if has_lesson_title(text) or any(True for _ in iter_fences(text)):
        return True
    prose = without_fences(text, "")
    if _NUMBERED_SECTION.search(prose):
        return True
    if numbered_items(prose) >= MIN_TOPICS:
        return False
    return len(prose.split()) > _OUTLINE_MAX_WORDS


def asks_back(text: str) -> bool:
    """A short reply with no fence or heading that ends on a question: it asked instead of
    teaching."""
    parts = blocks(text)
    if len(text.split()) > _ASKS_BACK_MAX_WORDS or any(True for _ in iter_fences(text)):
        return False
    return bool(parts) and is_question(parts[-1]) and not any(map(is_heading, parts))


def next_lesson_number(recent: Sequence[Any] | None, *, redoing: Any = None) -> int:
    """One past the highest lesson this chat has taught.

    ``recent`` is read before this turn's message is saved, so its last reply is the one
    before this turn: every reply counts but the one a regenerate redoes (``redoing``, its
    message id). Counting only replies before the last user row restarted at Lesson 1.
    """
    taught = [
        lesson_step(content)
        for message in recent or []
        if getattr(message, "role", None) == "assistant"
        and (redoing is None or getattr(message, "id", None) != redoing)
        and isinstance(content := getattr(message, "content", None), str)
    ]
    return max((n for n in taught if n is not None), default=0) + 1


def with_title(text: str, title: str) -> str:
    """``title`` after the opening hook (a first paragraph), else first."""
    parts = blocks(text)
    at = 1 if len(parts) > 1 and is_paragraph(parts[0]) else 0
    return joined([*parts[:at], title, *parts[at:]])


def _card(quiz: QuizCard, copy: LessonCopy) -> str:
    body = json.dumps({"label": copy.exercise, **quiz.model_dump()}, ensure_ascii=False)
    return f"```quiz\n{body}\n```"


def with_practice(text: str, quiz: QuizCard, copy: LessonCopy) -> str:
    """The card last, under the lesson's practice heading."""
    parts = blocks(text)
    names = {_folded(copy.your_turn), "your turn"}
    own = [i for i, part in enumerate(parts) if is_heading(part) and _heading_name(part) in names]
    if own:
        # The card takes the place of the prose practice under the heading; the sections
        # after it ("Common mistakes", a closing note under its own heading) stay.
        at = own[-1]
        end = next((j for j in range(at + 1, len(parts)) if is_heading(parts[j])), len(parts))
        return joined([*parts[: at + 1], _card(quiz, copy), *parts[end:]])
    if parts and is_question(parts[-1]) and len(parts[-1]) <= _CLOSER_MAX_CHARS:
        parts = parts[:-1]
    sections = len(_NUMBERED_SECTION.findall(without_fences(text, "")))
    heading = f"### {sections + 1}. {copy.your_turn}" if sections else f"### {copy.your_turn}"
    return joined([*parts, heading, _card(quiz, copy)])


def _folded(name: str) -> str:
    return " ".join(name.casefold().split())


def _heading_name(heading: str) -> str:
    """A heading's own words: no #s, no section number, no closing colon or mark, so
    "### 2. Your turn:" names "your turn" and "### Why your turn matters" does not."""
    return _folded(_HEADING_NAME.sub("", heading.strip()).rstrip(" :!.?*"))


async def hold_lesson(state: FinalizeState, copy: LessonCopy) -> str:
    """The pass's lesson step: the missing title and card, both or neither."""
    text = state.text
    titled = has_lesson_title(text)
    quizzed = any(fence.lang == "quiz" for fence in iter_fences(text))
    if titled and quizzed:
        return text
    practice = None if quizzed else await lesson_practice(state)
    if not quizzed and practice is None:
        return text
    if not titled:
        topic = lesson_topic(state.ctx.user_message_content) or (practice and practice.topic)
        if not topic:
            return text
        backup = state.ctx.regenerate_backup
        number = next_lesson_number(
            state.ctx.recent_messages, redoing=backup.message_id if backup else None
        )
        text = with_title(text, f"### {copy.lesson} {number}: {topic}")
    return with_practice(text, practice.quiz, copy) if practice is not None else text


async def hold_lesson_shape(state: FinalizeState) -> str:
    """Pass entry: the reply to a lesson or teach-me turn in the shape the app reads."""
    text = state.text
    if (
        not state.settings.lesson_shape_enabled
        or state.server_text
        or state.was_cancelled
        or not text.strip()
    ):
        return text
    layout = prompt_lesson_layout(state.ctx.prompt_messages)
    if layout is None:
        return text
    user = state.ctx.user
    copy = lesson_copy(state.ctx.user_message_content or "", user.locale if user else None)
    if layout == "teaching" and not teaches(text):
        return await hold_outline(state, copy)
    return text if layout == "walkthrough" and asks_back(text) else await hold_lesson(state, copy)
