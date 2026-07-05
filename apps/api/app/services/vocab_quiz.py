"""Parse in-chat vocab/trivia quiz blocks and validate user answers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

VOCAB_QUIZ_FENCE_RE = re.compile(r"```vocab_quiz\s*\n([\s\S]*?)```", re.IGNORECASE)
VOCAB_SESSION_JSON_FENCE_RE = re.compile(r"```json\s*\n([\s\S]*?)```", re.IGNORECASE)
VOCAB_SESSION_JSON_PARTIAL_RE = re.compile(r"```json[\s\S]*$", re.IGNORECASE)
QUIZ_ANSWER_RE = re.compile(r"^([A-D])\.?$", re.IGNORECASE)

_SESSION_METADATA_KEYS = frozenset(
    {
        "session_complete",
        "sessionComplete",
        "words_learned",
        "wordsLearned",
        "daily_goal_met",
        "dailyGoalMet",
    }
)


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


def _is_vocab_session_metadata(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    return any(key in data for key in _SESSION_METADATA_KEYS)


def strip_vocab_session_metadata(content: str) -> str:
    """Remove ```json fences the model sometimes emits when a daily vocab session ends."""

    def _strip_fence(match: re.Match[str]) -> str:
        try:
            data = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return match.group(0)
        return "" if _is_vocab_session_metadata(data) else match.group(0)

    stripped = VOCAB_SESSION_JSON_FENCE_RE.sub(_strip_fence, content)
    partial = VOCAB_SESSION_JSON_PARTIAL_RE.search(stripped)
    if partial and re.search(
        r"session_complete|sessionComplete|words_learned|wordsLearned|daily_goal_met|dailyGoalMet",
        partial.group(0),
        re.IGNORECASE,
    ):
        stripped = stripped[: partial.start()].rstrip()
    return stripped.strip()


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
    if not re.fullmatch(r"[A-D]", correct_raw):
        return None
    correct = correct_raw

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
