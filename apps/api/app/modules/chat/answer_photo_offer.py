"""Whether a turn's reply may open with a reference photo, and the hints that ask for it.

A reply about one thing worth seeing ("what is a capybara") opens with a photo the app
looks up (``modules/images/answer_photo``). A worked problem, a school exercise, a
lesson or code never does.

The word rules below only offer the photo; the turn's read decides it (``decider_read``'s
``seen``). "What is ur name" read "ur name" as the thing asked about, its own hint said to
open the reply with a photo of it, and "My name is Recall" came under one (the owner's chat,
2026-11-22). A read that calls the answer unseen takes the hints back out
(``without_answer_photo_hints``) and no photo is looked up; with no read the rules stand.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, get_args

from app.modules.chat.continuation_subject import works_on_last_reply
from app.modules.chat.prompt_constants import is_bare_writing_line
from app.modules.chat.prompt_constants.answer_subject import subject_photo_hint
from app.modules.chat.prompt_constants.visuals import ANSWER_PHOTO_HINT, WHERE_IS_PHOTO_HINT
from app.modules.turn_reading.answer_subject import asked_about_subject
from app.modules.turn_reading.coding import is_programming_turn
from app.modules.turn_reading.conversation import is_social_opener
from app.modules.turn_reading.routing import is_lightweight_chat_turn
from app.modules.turn_reading.school_question import is_school_exercise
from app.modules.turn_reading.visuals import where_is_place
from app.services.solving import SubjectName

if TYPE_CHECKING:
    from app.modules.chat.prompt_format import StyleTurn

# Subjects whose answers are worked problems, never one thing to look at.
NO_PHOTO_SUBJECTS: frozenset[str] = frozenset({*get_args(SubjectName), "statistics"})


def offers_answer_photo(turn: StyleTurn) -> bool:
    """Whether this turn could be about one thing worth seeing ("what is a capybara").

    Code, a subject problem, a school exercise, a lesson, a draft, a chart or day plan,
    a pasted fragment, small talk and "continue" / "fix that" never are. Offering the photo
    there only confused the reply ("I can't see the image you're referring to").
    """
    # A multi-part message's photo, if it asks for one, is in its contract.
    if turn.multi or not turn.image_search_enabled or not turn.query.strip():
        return False
    if turn.writing or turn.writing_kind or turn.viz_intent or turn.is_day_plan:
        return False
    if turn.teaching or turn.walkthrough or turn.learning_plan or turn.lesson_hint:
        return False
    if turn.subject in NO_PHOTO_SUBJECTS:
        return False
    if is_lightweight_chat_turn(turn.query) or is_social_opener(turn.query):
        return False
    if is_bare_writing_line(turn.query) or works_on_last_reply(turn.query):
        return False
    # A school exercise is answered in the textbook's words: a photo above "Verify the law
    # of conservation of mass" or the nitrogen cycle was one nobody asked for (2026-10-30).
    if is_school_exercise(turn.query):
        return False
    return not is_programming_turn(turn.query)


def answer_photo_hints(turn: StyleTurn) -> list[str]:
    if turn.query and where_is_place(turn.query):
        return [ANSWER_PHOTO_HINT, WHERE_IS_PHOTO_HINT]
    subject = asked_about_subject(turn.query)
    if subject:
        return [ANSWER_PHOTO_HINT, subject_photo_hint(subject)]
    return [ANSWER_PHOTO_HINT]


def without_answer_photo_hints(
    messages: list[dict[str, Any]], query: str | None
) -> list[dict[str, Any]]:
    """The prompt without the photo hints ``answer_photo_hints`` gave ``query``'s turn."""
    hints = [ANSWER_PHOTO_HINT, WHERE_IS_PHOTO_HINT]
    subject = asked_about_subject(query or "")
    if subject:
        hints.append(subject_photo_hint(subject))
    out: list[dict[str, Any]] = []
    for message in messages:
        content = message.get("content")
        if message.get("role") == "system" and isinstance(content, str):
            changed = content
            for hint in hints:
                changed = changed.replace(hint, "")
            if changed != content:
                message = {**message, "content": re.sub(r"\n{3,}", "\n\n", changed).strip()}
        out.append(message)
    return out


def offers_photo_in(messages: list[dict[str, Any]]) -> bool:
    """Whether the prompt asks the reply to open with a photo."""
    return any(
        message.get("role") == "system"
        and isinstance(message.get("content"), str)
        and ANSWER_PHOTO_HINT in message["content"]
        for message in messages
    )
