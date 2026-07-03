"""Parse in-chat vocab/trivia quiz blocks and validate user answers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

VOCAB_QUIZ_FENCE_RE = re.compile(r"```vocab_quiz\s*\n([\s\S]*?)```", re.IGNORECASE)
QUIZ_ANSWER_RE = re.compile(r"^([A-D])\.?$", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedVocabQuiz:
    word: str
    part_of_speech: str | None
    question: str | None
    correct: str | None
    quiz_type: str | None


def quiz_answer_letter(text: str) -> str | None:
    match = QUIZ_ANSWER_RE.match(text.strip())
    return match.group(1).upper() if match else None


def _clean_word(raw: str) -> str:
    return raw.replace("**", "").strip()


def parse_vocab_quiz(content: str) -> ParsedVocabQuiz | None:
    """Extract the machine-readable vocab_quiz JSON fence from assistant content."""
    if "```vocab_quiz" not in content:
        return None
    match = VOCAB_QUIZ_FENCE_RE.search(content)
    if not match:
        return None
    try:
        data = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    quiz_type_raw = str(data.get("quiz_type") or data.get("quizType") or "").lower()
    quiz_type = quiz_type_raw if quiz_type_raw in ("vocab", "trivia") else None

    word = _clean_word(str(data.get("word") or ""))
    question = str(data.get("question") or "").strip() or None
    if quiz_type == "trivia":
        if not question and not word:
            return None
    elif not word:
        return None

    choices = data.get("choices")
    if not isinstance(choices, list) or len(choices) < 2:
        return None

    correct_raw = str(data.get("correct") or "").upper()
    correct = correct_raw if re.fullmatch(r"[A-D]", correct_raw) else None

    pos = str(data.get("part_of_speech") or "").strip() or None
    if quiz_type == "trivia":
        pos = None

    return ParsedVocabQuiz(
        word=word or (question or "")[:80],
        part_of_speech=pos,
        question=question,
        correct=correct,
        quiz_type=quiz_type,
    )
