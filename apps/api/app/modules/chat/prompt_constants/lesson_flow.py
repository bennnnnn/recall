# ruff: noqa: RUF001
"""Where a lesson stands: the lesson the last reply taught, or the outline it asked from.

A teach-me reply is either Lesson N (title, sections, a practice quiz) or, for a
whole subject, an outline that ends asking where to start. The next turn goes
on from either one.
"""

from __future__ import annotations

import re
from typing import Any

from app.modules.chat.prompt_constants.teaching import (
    _LESSON_OPENING,
    _LESSON_SHAPE,
    is_teaching_request,
)

# "### Lesson 2: Dictionaries": a heading with the word Lesson in an app
# language and the lesson's number. "Day 1", "Part 2" and "Step 3" are plans,
# parts and how-tos, not lessons.
_LESSON_WORDS = r"lesson|lecci[oó]n|le[cç]on|lektion|lezione|li[cç][aã]o|aula|урок|ders|ትምህርት"
_LESSON_TITLE = re.compile(
    r"^\s*(?:#{1,4}\s+|\*\*)\s*(?:" + _LESSON_WORDS + r")\s+(\d{1,2})\s*[:.\-—–]",
    re.MULTILINE | re.IGNORECASE,
)
_QUIZ_FENCE = re.compile(r"^\s*```quiz\b", re.MULTILINE | re.IGNORECASE)
_QUESTION_MARKS = ("?", "？", "፧")


def lesson_step(text: str | None) -> int | None:
    """The number of the lesson an assistant reply taught, or None.

    A lesson ends on practice: a ```quiz card or a question after its title. A
    reply that only mentions "Lesson 2" in passing is not one.
    """
    if not text:
        return None
    found: int | None = None
    end = 0
    for match in _LESSON_TITLE.finditer(text):
        found, end = int(match.group(1)), match.end()
    if found is None or found < 1:
        return None
    rest = text[end:]
    if _QUIZ_FENCE.search(rest) or any(mark in rest for mark in _QUESTION_MARKS):
        return found
    return None


def active_lesson_step(messages: list[Any] | None) -> int | None:
    """The lesson the most recent assistant reply taught, in an oldest-first window."""
    for message in reversed(messages or []):
        if getattr(message, "role", None) != "assistant":
            continue
        content = getattr(message, "content", None)
        return lesson_step(content if isinstance(content, str) else None)
    return None


def lesson_continue_hint(number: int) -> str:
    """The turn after a lesson: grade the practice if answered, then the next lesson."""
    nxt = number + 1
    return (
        f"A lesson is in progress. The learner has ALREADY SEEN Lesson {number}, which ended "
        "with a practice ```quiz (they can check it in the app) and a preview of the next "
        f"lesson. Do not repeat Lesson {number}. Read the latest message first:\n"
        '- An answer to the practice question: if right, start with "Correct! 🎉" and say why '
        'in one sentence; if wrong or partial, start with "Not quite", fix that one '
        "misunderstanding in 1-3 sentences with a fresh tiny example, and do not ask them to "
        f"try again. Then teach Lesson {nxt}.\n"
        f"- 'next', 'ok', 'got it', 'continue' or similar: teach Lesson {nxt}.\n"
        "- Confusion ('I don't get it', 'why?', 'another example'): stay on the same idea, "
        f"explain it a different way with a new analogy and example under the same "
        f"`### Lesson {number}: ...` title, and end with a fresh ```quiz.\n"
        "- A question about the lesson: answer it first, then continue.\n"
        "- Accidental or unclear input: do not grade it; give the practice answer in one "
        f"sentence and teach Lesson {nxt}.\n"
        "- A request to skip, stop, change topic, get everything at once, a summary or a "
        "cheat sheet: do that instead of the next lesson.\n"
        f"Lesson {nxt} covers what the preview promised, without a greeting or an outline, "
        "in the same shape (the app's ```quiz, ```array and ```steps cards included):\n"
        + _LESSON_SHAPE
    )


def outline_awaits_pick(messages: list[Any] | None) -> bool:
    """True when the last reply answered a "teach me" with a subject outline, not a lesson.

    It ends on a question (where to start) and has no lesson title, so the
    next message picks a topic, gives a level or says "start".
    """
    rows = [
        m
        for m in messages or []
        if getattr(m, "role", None) in {"user", "assistant"}
        and isinstance(getattr(m, "content", None), str)
    ]
    if len(rows) < 2 or rows[-1].role != "assistant" or rows[-2].role != "user":
        return False
    reply: str = rows[-1].content
    if lesson_step(reply) is not None or _LESSON_TITLE.search(reply):
        return False
    return is_teaching_request(rows[-2].content) and any(m in reply for m in _QUESTION_MARKS)


OUTLINE_PICK_HINT = (
    "Your previous reply outlined a subject the user wants to learn and asked where to "
    "start. Read the latest message:\n"
    "- A number, a topic, 'start', their level or their goal: teach Lesson 1 on the topic it "
    "picks (the first topic for 'start' or a beginner, the first one they don't know for a "
    "level, the one that leads to their goal) without repeating the outline, in this "
    "shape:\n" + _LESSON_OPENING + _LESSON_SHAPE + "\n"
    "- Anything else (another question, a change of mind): answer that instead."
)


def lesson_turn_hint(lesson: int | None, *, outline_pick: bool) -> str | None:
    """How this turn goes on: the next lesson, Lesson 1 from the outline, or neither."""
    if lesson:
        return lesson_continue_hint(lesson)
    return OUTLINE_PICK_HINT if outline_pick else None
