"""Parse in-chat vocab/trivia quiz blocks and validate user answers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

VOCAB_QUIZ_FENCE_RE = re.compile(r"```vocab_quiz\s*\n([\s\S]*?)```", re.IGNORECASE)
VOCAB_SESSION_JSON_FENCE_RE = re.compile(r"```json\s*\n([\s\S]*?)```", re.IGNORECASE)
VOCAB_SESSION_JSON_PARTIAL_RE = re.compile(r"```json[\s\S]*$", re.IGNORECASE)
QUIZ_ANSWER_RE = re.compile(r"^([A-D])\.?$", re.IGNORECASE)
PLAIN_MC_CHOICE_RE = re.compile(
    r"^\s*(?:[-*•]\s*)?([A-D])\)\s*(.+?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
WORD_MEANING_QUESTION_RE = re.compile(
    r"What does\s+\*{0,2}([\w'-]+)\*{0,2}\s+mean",
    re.IGNORECASE,
)
WORD_LABEL_RE = re.compile(r"\*\*Word:\*\*\s*([\w'-]+)", re.IGNORECASE)

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
    choices: dict[str, str] | None = None


def _normalize_match_text(text: str) -> str:
    cleaned = re.sub(r"[*_`]", "", text)
    return re.sub(r"\s+", " ", cleaned.strip().lower())


def _definition_match_score(choice: str, definition: str, example: str | None = None) -> float:
    choice_norm = _normalize_match_text(choice)
    definition_norm = _normalize_match_text(definition)
    if not choice_norm or not definition_norm:
        return 0.0
    if (
        choice_norm == definition_norm
        or definition_norm in choice_norm
        or choice_norm in definition_norm
    ):
        return 1.0
    choice_tokens = set(choice_norm.split())
    definition_tokens = set(definition_norm.split())
    if not definition_tokens:
        return 0.0
    overlap = len(choice_tokens & definition_tokens) / len(definition_tokens)
    if example:
        example_norm = _normalize_match_text(example)
        example_tokens = set(example_norm.split())
        if example_tokens:
            overlap = max(overlap, len(choice_tokens & example_tokens) / len(example_tokens))
    return overlap


def extract_plain_markdown_choices(content: str) -> dict[str, str]:
    choices: dict[str, str] = {}
    for match in PLAIN_MC_CHOICE_RE.finditer(content):
        letter = match.group(1).upper()
        text = match.group(2).strip()
        if letter in {"A", "B", "C", "D"} and text:
            choices[letter] = text
    return choices


def parse_plain_markdown_vocab_quiz(content: str) -> ParsedVocabQuiz | None:
    """Parse chat-mode plain-markdown multiple choice (no ```vocab_quiz fence)."""
    if "```vocab_quiz" in content:
        return None
    choices = extract_plain_markdown_choices(content)
    if len(choices) < 2:
        return None

    word = ""
    meaning_match = WORD_MEANING_QUESTION_RE.search(content)
    if meaning_match:
        word = meaning_match.group(1)
    else:
        label_match = WORD_LABEL_RE.search(content)
        if label_match:
            word = label_match.group(1)

    question = None
    for line in content.splitlines():
        stripped = line.strip()
        if "?" in stripped:
            question = re.sub(r"[*_`]", "", stripped).strip()
            break

    return ParsedVocabQuiz(
        word=word,
        part_of_speech=None,
        question=question,
        correct=None,
        quiz_type="vocab",
        choices=choices,
    )


def infer_correct_letter_from_definition(
    choices: dict[str, str],
    definition: str | None,
    *,
    example: str | None = None,
) -> str | None:
    if not choices or not definition:
        return None
    best_letter: str | None = None
    best_score = 0.0
    for letter, text in choices.items():
        score = _definition_match_score(text, definition, example)
        if score > best_score:
            best_score = score
            best_letter = letter
    if best_score < 0.45:
        return None
    return best_letter


def parse_assistant_quiz(content: str) -> ParsedVocabQuiz | None:
    """Return a gradable quiz from either a vocab_quiz fence or plain markdown MC."""
    fenced = parse_vocab_quiz(content)
    if fenced is not None:
        return fenced
    return parse_plain_markdown_vocab_quiz(content)


def grade_quiz_answer(quiz: ParsedVocabQuiz, user_answer: str) -> tuple[str, str, bool] | None:
    user_letter = quiz_answer_letter(user_answer)
    if user_letter is None or not quiz.correct:
        return None
    correct_letter = quiz.correct.upper()
    return user_letter, correct_letter, user_letter == correct_letter


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
        choices={
            str(choice.get("letter", "")).upper(): str(choice.get("text", "")).strip()
            for choice in choices
            if isinstance(choice, dict)
            and str(choice.get("letter", "")).upper() in {"A", "B", "C", "D"}
            and str(choice.get("text", "")).strip()
        }
        or None,
    )
