"""Asking for the lesson the last reply just taught: point to it, never teach it again.

"Teach me American sayings" opened with Lesson 1 and its practice question; "Very
interesting. Lets start with 1" then got Lesson 1 word for word (live, 2026-10-25), and
on the free model it read the 1 as the quiz answer and went on to Lesson 2. The turn
hint (``lesson_again_hint``) asks for one short pointer; the finalize pass holds it: a
reply that writes a lesson or a quiz anyway becomes that pointer.

The ask is read by a positive grammar on the message's last sentence: "start with 1",
"let's begin with lesson 1", "go back to lesson 2", "show me lesson 2", "from the
beginning" (Lesson 1). A bare "1" is an answer to the quiz, never this. The grammar is
English, so a message it reads is English, and so is the pointer.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from app.modules.chat.prompt_constants.lesson_flow import active_lesson_step, lesson_titles
from app.services.md_fence_scan import iter_fences

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

_FIRST = {"1": 1, "one": 1, "first": 1, "the first": 1, "the first one": 1}
_NUMBER = r"(\d{1,2}|one|(?:the\s+)?first(?:\s+one)?)"
_LEAD = r"(?:(?:ok(?:ay)?|so|great|cool|nice|alright|sure|yes|yeah)\W+)*"
_ASK = re.compile(
    rf"^\W*{_LEAD}(?:(?:let'?s|lets|can\s+we|could\s+we|i\s+want\s+to|i'?d\s+like\s+to|please)\s+)?"
    rf"(?:(?:start|begin)\s+(?:with|from|at)\s+(?:lesson\s+|number\s+|no\.?\s*|#)?(?P<n1>{_NUMBER})"
    rf"|(?:go\s+(?:back\s+)?to|show\s+me|do|teach\s+me|give\s+me)\s+lesson\s+(?P<n2>{_NUMBER})"
    r"|(?:start|begin)\s+(?:from\s+)?(?:the\s+)?(?P<top>beginning|start))"
    r"(?:\s+please)?\W*$",
    re.IGNORECASE,
)
_SENTENCES = re.compile(r"(?<=[.!?])\s+")


def asked_lesson(text: str | None) -> int | None:
    """The lesson number the message's last sentence asks to start or go to, or None."""
    sentences = _SENTENCES.split((text or "").strip())
    found = _ASK.match(sentences[-1]) if sentences and sentences[-1] else None
    if found is None:
        return None
    if found.group("top"):
        return 1
    number = found.group("n1") or found.group("n2") or ""
    words = " ".join(number.lower().split())
    return _FIRST.get(words) or (int(words) if words.isdigit() else None)


def lesson_again(text: str | None, recent: list[Any] | None) -> int | None:
    """The lesson the user asks for when it is the one the last reply taught, or None."""
    current = active_lesson_step(recent)
    asked = asked_lesson(text)
    return current if current is not None and asked == current else None


def lesson_again_hint(number: int) -> str:
    """The turn hint when the user asks for the lesson they are on."""
    return (
        f"The learner asked for Lesson {number}, which your previous reply already taught; "
        "it ends with its practice question. Reply in one or two short sentences: they are "
        f"on Lesson {number}, it is just above, try its practice question, and 'next' brings "
        f"Lesson {number + 1}. Do not grade anything. Write no lesson, no heading and no quiz."
    )


def pointer(number: int) -> str:
    return (
        f"You're on Lesson {number} now: it's just above. Try its practice question, or say "
        f'"next" for Lesson {number + 1}.'
    )


def keep_to_lesson_again_pass(state: FinalizeState) -> str:
    """The finalize pass: a reply that teaches or quizzes again becomes the pointer."""
    number = lesson_again(state.ctx.user_message_content, state.ctx.recent_messages)
    if number is None or state.server_text:
        return state.text
    teaches = bool(lesson_titles(state.text)) or any(
        fence.lang == "quiz" for fence in iter_fences(state.text)
    )
    return pointer(number) if teaches else state.text
