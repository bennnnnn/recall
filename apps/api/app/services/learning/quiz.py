"""Service compatibility API for vocabulary quiz policy and verification."""

import re

from app.core.config import get_settings
from app.gateways import litellm_gateway
from app.models.vocab_quiz import (
    MAX_QUIZ_TRIES_PER_QUESTION,
    ParsedVocabQuiz,
    QuizAnswerGrade,
    is_vocab_quiz_answer,
    match_choice_letter,
    parse_vocab_quiz,
    quiz_answer_letter,
    strip_vocab_session_metadata,
)

__all__ = [
    "MAX_QUIZ_TRIES_PER_QUESTION",
    "ParsedVocabQuiz",
    "QuizAnswerGrade",
    "is_vocab_quiz_answer",
    "match_choice_letter",
    "parse_vocab_quiz",
    "quiz_answer_letter",
    "strip_vocab_session_metadata",
    "verified_correct_letter",
]


async def verified_correct_letter(quiz: ParsedVocabQuiz) -> str | None:
    """Use a cheap second model pass to check a quiz answer key."""
    if not quiz.choices:
        return None
    stem = (quiz.question or quiz.word or "").strip()
    if not stem:
        return None
    choice_lines = "\n".join(f"{letter}. {text}" for letter, text in quiz.choices)
    prompt = (
        "Which choice letter is the correct answer? "
        "Reply with only one letter: A, B, C, or D.\n\n"
        f"Question: {stem}\n{choice_lines}"
    )
    try:
        raw = await litellm_gateway.complete_text(
            settings=get_settings(),
            model_alias="title-model",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4,
        )
    except Exception:
        return None
    if not raw:
        return None
    match = re.search(r"[A-D]", raw.upper())
    if match is None:
        return None
    letter = match.group(0)
    present = {choice_letter.upper() for choice_letter, _ in quiz.choices}
    return letter if letter in present else None
