"""A chemistry message that asks several things, each answered by a verified part of its own.

"a) molar mass of NH3 b) moles in 34 g of NH3" verified neither part, and "What is the molar
mass of H2O? How many moles are in 36 g of H2O?" was answered with the molar mass alone, the
moles never mentioned (audit 2026-11-13): read whole, the message holds two asks no one law
answers, or one law answers the first and the instant reply drops the second.

Its questions are read by ``questions``: labelled parts or question sentences, a later one
taking the substance an earlier one named. When every question verifies to an answer of its
own, the reply is the question in parts, a card under each part
(``services.worked_parts``), as physics answers its parts (``physics.split_parts``); otherwise
the message is read whole, as before, and an instant reply that would answer fewer questions
than it asks is the model's instead (``direct``).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from app.core.sympy_executor import run_sympy
from app.modules.chemistry.block import VerifiedChemistry, build_verified_chemistry
from app.modules.chemistry.direct import maybe_direct_chemistry_reply
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.questions import Question, asks_several, chemistry_questions
from app.modules.chemistry.reply_policy import attach_chemistry_fence_hint
from app.services.solving import SubjectAugmentation
from app.services.worked_parts import answers_in_parts

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)

# More questions than this is a worksheet pasted whole, not one question in parts.
_MAX_QUESTIONS = 6


def _solve_each(
    questions: tuple[Question, ...],
) -> tuple[tuple[VerifiedChemistry, ...], tuple[str, ...]] | None:
    blocks: list[VerifiedChemistry] = []
    replies: list[str] = []
    for question in questions:
        intent = extract_chemistry_intent(question.read)
        verified = None if intent is None else build_verified_chemistry(intent)
        # Two questions read as one answer is one question misread, not two answered.
        if verified is None or any(
            block.result.answer == verified.result.answer for block in blocks
        ):
            return None
        reply = maybe_direct_chemistry_reply(
            verified, has_image_attachment=False, user_text=question.read
        )
        if reply is None:
            return None
        blocks.append(verified)
        replies.append(reply)
    return tuple(blocks), tuple(replies)


def _read_parts(
    text: str,
) -> tuple[tuple[Question, ...], tuple[tuple[VerifiedChemistry, ...], tuple[str, ...]] | None]:
    """The message's questions, and each one's verified block and reply when all verify. Runs
    in the SymPy pool: every reading and solve here parses with it."""
    questions = chemistry_questions(text)
    if not 2 <= len(questions) <= _MAX_QUESTIONS:
        return questions, None
    return questions, _solve_each(questions)


async def solve_chemistry_parts(text: str, settings: Settings) -> SubjectAugmentation | None:
    """The message answered in parts when it asks several questions and each verifies; None
    otherwise, and the message is read whole."""
    if not asks_several(text):
        return None
    try:
        questions, solved = await run_sympy(
            _read_parts, text, timeout=settings.stem_solve_timeout_seconds
        )
    except Exception:
        logger.warning("chemistry parts read failed", exc_info=True)
        return None
    if solved is None:
        return None
    blocks, replies = solved
    first = blocks[0]
    return SubjectAugmentation(
        "chemistry",
        attach_chemistry_fence_hint(first.prompt_text),
        replace(first, question_parts=blocks),
        direct_text=answers_in_parts([question.asked for question in questions], replies),
    )
