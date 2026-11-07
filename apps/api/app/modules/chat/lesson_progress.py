"""What a lesson chat has taught so far, as one memory line.

Read from the chat itself: the subject from its first "teach me", the topics
from each ``### Lesson N: <topic>`` heading. Built by the ``lesson_progress``
job after a lesson reply; memory owns the write
(``modules/memory/learning_progress.py``).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Chat
from app.modules.conversation import history as conversation_history
from app.modules.turn_reading.lesson_flow import lesson_step, lesson_titles, teach_subject
from app.modules.turn_reading.teaching import is_teaching_request

# A long course still finds its first "teach me" and every lesson heading.
LESSON_HISTORY_LIMIT = 300
_COVERED_MAX = 8
_TOPIC_MAX_CHARS = 60
# The line ``lesson_progress`` writes, as the prompt's memory shows it.
PROGRESS_LINE = re.compile(r"\bLearning (?P<subject>[^\n:]{1,120}): reached Lesson \d")


def resumes_course(query: str, memory: str) -> bool:
    """Memory says they are already learning what this asks for ("Learning Python lists:
    reached Lesson 3" and "teach me python"): the reply asks where to pick up, so no new
    lesson's code and quiz are demanded. The asked subject is the saved one or its start;
    a narrower ask ("teach me python dictionaries") gets its lesson."""
    asked = (teach_subject(query) or "").lower().split()
    if not asked:
        return False
    for line in PROGRESS_LINE.finditer(memory or ""):
        if line.group("subject").lower().split()[: len(asked)] == asked:
            return True
    return False


@dataclass(frozen=True)
class LessonProgress:
    text: str
    started_at: datetime | None


@dataclass
class _Course:
    """The course a chat is on, read message by message."""

    subject: str | None = None
    topics: list[str] = field(default_factory=list)
    latest: tuple[int, str] | None = None
    started_at: datetime | None = None
    # The subject of the last "teach me" since the last lesson, if any.
    pending: str | None = None

    def asked(self, subject: str | None) -> None:
        if subject:
            self.pending = subject

    def taught(self, reply: str, sent: datetime | None) -> None:
        titles = lesson_titles(reply)
        if not titles:
            return
        switched = (
            self.pending is not None
            and titles[0][0] == 1
            and self.pending.casefold() != (self.subject or "").casefold()
        )
        if self.latest is None or switched:
            # With no "teach me" before it, a course has no subject to name.
            self._start(self.pending, sent)
        # "Teach me more about loops" between lessons 4 and 5 goes on with the course.
        self.pending = None
        for number, raw_topic in titles:
            topic = raw_topic[:_TOPIC_MAX_CHARS].strip()
            self.latest = (number, topic)
            if topic not in self.topics:
                self.topics.append(topic)

    def _start(self, subject: str | None, sent: datetime | None) -> None:
        self.subject, self.topics, self.latest, self.started_at = subject, [], None, sent


def lesson_progress(messages: Sequence[Any], *, title: str | None) -> LessonProgress | None:
    """The learning line for an oldest-first chat, or None when it taught no lesson.

    The subject is what the user asked to learn, never a guess: a chat whose lessons
    answered no "teach me" (a "help me understand two sum" the model laid out as Lesson
    1) keeps no line, and the chat's title ("Greeting", "Understanding Two Sum In
    Python") never stands in for it. A new "teach me" followed by a Lesson 1 starts a
    new course in the same chat ("teach me maths", lessons, then "now teach me
    chemistry"): the line is the latest course's, with only its own lessons.
    """
    course = _Course()
    for message in messages:
        content = getattr(message, "content", None)
        if not isinstance(content, str):
            continue
        role = getattr(message, "role", None)
        if role == "user" and is_teaching_request(content):
            course.asked(teach_subject(content))
        elif role == "assistant" and lesson_step(content) is not None:
            course.taught(content, getattr(message, "created_at", None))
    if course.latest is None or course.subject is None:
        return None
    number, topic = course.latest
    where = f' (chat "{title.strip()}")' if title and title.strip() else ""
    covered = "; ".join(course.topics[-_COVERED_MAX:])
    return LessonProgress(
        text=(
            f"Learning {course.subject}: reached Lesson {number}, {topic}{where}. "
            f"Covered: {covered}"
        ),
        started_at=course.started_at,
    )


async def load_lesson_progress(
    session: AsyncSession, *, user_id: UUID, chat_id: UUID
) -> LessonProgress | None:
    chat = await session.get(Chat, chat_id)
    if chat is None or chat.user_id != user_id:
        return None
    messages = await conversation_history.recent_messages(
        session, chat_id, limit=LESSON_HISTORY_LIMIT
    )
    return lesson_progress(messages, title=chat.title)
