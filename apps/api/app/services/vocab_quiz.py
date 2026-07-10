"""Parse in-chat vocab/trivia quiz blocks and validate user answers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

VOCAB_QUIZ_FENCE_RE = re.compile(r"```vocab_quiz[^\n]*\n([\s\S]*?)```", re.IGNORECASE)
VOCAB_SESSION_JSON_FENCE_RE = re.compile(r"```json\s*\n([\s\S]*?)```", re.IGNORECASE)
VOCAB_SESSION_JSON_PARTIAL_RE = re.compile(r"```json[\s\S]*$", re.IGNORECASE)
QUIZ_ANSWER_RE = re.compile(r"^([A-D])\.?$", re.IGNORECASE)
# Short confirmations only — avoid matching prose like "A bit more help".
QUIZ_ANSWER_LOOSE_RE = re.compile(
    r"^(?:is\s+it\s+|option\s+|answer\s*(?:is\s+)?|i\s+(?:think|say|choose|pick)\s+)?"
    r"([A-D])\.?[?!.]*$",
    re.IGNORECASE,
)
MAX_LOOSE_QUIZ_ANSWER_LEN = 24
# Wrong answers on the same open question before we mark it missed and move on.
MAX_QUIZ_TRIES_PER_QUESTION = 3

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
    question: str | None
    correct: str | None
    quiz_type: str | None
    correct_text: str | None = None
    # (letter, choice text) pairs for free-text answer matching.
    choices: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class QuizAnswerGrade:
    is_correct: bool
    user_letter: str
    correct_letter: str
    word: str
    quiz_type: str | None = None
    question: str | None = None
    # 1-based try count for this open question (letter answers since the quiz fence).
    attempt: int = 1
    # True when wrong and attempt >= MAX_QUIZ_TRIES_PER_QUESTION — mark missed, move on.
    tries_exhausted: bool = False


def _normalize_choice_text(text: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", text.strip().lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def match_choice_letter(user_text: str, choices: tuple[tuple[str, str], ...]) -> str | None:
    """Map free-text like 'a typical example' to its A-D letter when unique."""
    needle = _normalize_choice_text(user_text)
    if not needle or len(needle) > 80:
        return None
    hits: list[str] = []
    for letter, text in choices:
        choice = _normalize_choice_text(text)
        if not choice:
            continue
        if needle == choice or needle in choice or choice in needle:
            hits.append(letter)
    # Prefer exact / unique matches only — ambiguous substrings are ignored.
    unique = list(dict.fromkeys(hits))
    if len(unique) == 1:
        return unique[0]
    return None


def quiz_answer_letter(
    text: str,
    *,
    choices: tuple[tuple[str, str], ...] | None = None,
) -> str | None:
    stripped = text.strip()
    strict = QUIZ_ANSWER_RE.match(stripped)
    if strict:
        return strict.group(1).upper()
    if len(stripped) <= MAX_LOOSE_QUIZ_ANSWER_LEN:
        loose = QUIZ_ANSWER_LOOSE_RE.match(stripped)
        if loose:
            return loose.group(1).upper()
    if choices:
        return match_choice_letter(stripped, choices)
    return None


def is_vocab_quiz_answer(
    text: str,
    *,
    choices: tuple[tuple[str, str], ...] | None = None,
) -> bool:
    return quiz_answer_letter(text, choices=choices) is not None


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

    correct_text: str | None = None
    choice_pairs: list[tuple[str, str]] = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        letter = str(choice.get("letter") or "").upper()
        if not re.fullmatch(r"[A-D]", letter):
            continue
        text = str(choice.get("text") or "").strip()
        if not text:
            continue
        choice_pairs.append((letter, text))
        if letter == correct:
            correct_text = text

    return ParsedVocabQuiz(
        word=word or (question or "")[:80],
        question=question,
        correct=correct,
        quiz_type=quiz_type,
        correct_text=correct_text,
        choices=tuple(choice_pairs),
    )
