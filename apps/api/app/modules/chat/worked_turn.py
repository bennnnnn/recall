"""Which turns ask the model for a ```worked block: a calculation no solver checked.

A turn qualifies when nothing verified answers it (no solve, no instant reply, no money
card), it is no small talk, lesson or message of several requests, its message holds a
number, and the readers say it is a question to work: its subject is maths, physics or
chemistry (the subject order, ``services/subjects/order.py``; not when only a word named
it, "remind me to study chemistry at 7pm"), or it is a school exercise or a science question
that states a quantity (``turn_reading.school_question``, ``question_kinds``). The model
still answers a question that asks no calculation in prose; the contract says so.

Physics lays the block out as its verified replies are laid out (``WorkedLayout``).

A message that only states the student's own results and asks whether they are right ("My
answers: 1) 1 mol 2) 110 g. Did I get them right?") asks for no new value: it gets no block,
and the reply compares each result with the right one (``RESULT_CHECK_CONTRACT``). A new
question beside a claim ("How many grams in 0.5 mol NaCl? I got 29.2 g, am I right?") keeps
its block, for the question.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.config import Settings
from app.modules.chat.prompt_constants.worked import RESULT_CHECK_CONTRACT, WORKED_BLOCK_CONTRACT
from app.modules.chat.prompt_inject import inject_before_last_user
from app.modules.chat.turn_trace import note_prompt_rule
from app.modules.chat.worked_render import WorkedLayout
from app.modules.turn_reading.question_kinds import is_science_question
from app.modules.turn_reading.school_question import is_school_exercise
from app.modules.turn_reading.turn import current_turn_reading, teaching_of
from app.services.student_claim import only_checks_stated_results

_STEM_SUBJECTS = frozenset({"math", "physics", "chemistry"})
# Subject-order steps that read a subject from a word, not from a problem's shape.
_WORD_CUE_REASONS = frozenset({"chemistry_question"})
# A number with a unit after it ("100 meters", "4 g"); a digit inside a formula (CO2) or a
# time (10am) is none.
_QUANTITY = re.compile(r"(?<![A-Za-z\d.])\d+(?:[.,]\d+)?\s?(?!am\b|pm\b)(?:[a-zA-Zµ°Ω%]{1,12})\b")


def worked_layout(
    content: str,
    subject: str | None,
    settings: Settings,
    *,
    answered: bool,
    lightweight: bool,
    several_requests: bool,
) -> WorkedLayout | None:
    """The layout of this turn's ```worked block, or None when the turn gets none.

    ``answered``: a verified solve, an instant reply or a money card answers the turn.
    """
    if not settings.worked_layout_enabled or answered or lightweight or several_requests:
        return None
    if not _calculation(content, subject) or only_checks_stated_results(content):
        return None
    return WorkedLayout(law_heading=subject == "physics")


def checks_stated_results(
    content: str, subject: str | None, *, answered: bool, lightweight: bool
) -> bool:
    """A calculation turn nothing verified whose message only states the student's results
    to check: the reply compares each with the right one, and works nothing again. A
    verified check ("check my answer: x = 6") is the solver's, laid out as its replies are."""
    return (
        not answered
        and not lightweight
        and only_checks_stated_results(content)
        and _calculation(content, subject)
    )


def _calculation(content: str, subject: str | None) -> bool:
    """The readers say the message is a question to work, with a number in it."""
    if not any(char.isdigit() for char in content) or teaching_of(content):
        return False
    return (
        (subject in _STEM_SUBJECTS and not _word_cue_only(content))
        or is_school_exercise(content)
        or (is_science_question(content) and _QUANTITY.search(content) is not None)
    )


def _word_cue_only(content: str) -> bool:
    """The subject order named the subject from a word alone ("study chemistry"): the
    message is about the subject, not a calculation in it (``chemistry_question``)."""
    reading = current_turn_reading()
    return (
        reading is not None
        and reading.text == content
        and reading.subject_reason in (_WORD_CUE_REASONS)
    )


def states_a_quantity(content: str) -> bool:
    """A number with a unit after it ("36 cm", "10 ohm", "4X"): a value to work with, where a
    digit inside a formula (CH3CH2CH2OH) or a grade ("grade 11") is none."""
    return _QUANTITY.search(content) is not None


def with_worked_contract(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """The prompt with the block's contract beside the user's message."""
    note_prompt_rule("subject.worked")
    return inject_before_last_user(messages, WORKED_BLOCK_CONTRACT)


def with_result_check_contract(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """The prompt with the check's contract beside the user's message."""
    note_prompt_rule("subject.result_check")
    return inject_before_last_user(messages, RESULT_CHECK_CONTRACT)


def without_worked_contract(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The prompt without it: a tool verified the turn after it was built."""
    return [message for message in messages if message.get("content") != WORKED_BLOCK_CONTRACT]
