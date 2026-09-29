"""Subject formatting for a short continuation of the prior exchange.

"Another" is not physics. When the current line is only a continuation, the
subject comes from the nearest earlier exchange that is not itself a
continuation. A new topic does not inherit that subject.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.services.chat.prompt_constants.routing import (
    is_lightweight_chat_turn,
    is_writing_deliverable_request,
)
from app.services.text_normalize import collapse_ws

_MAX_CHARS = 80
_POLITE_PREFIXES = ("please ", "can you ", "could you ", "would you ", "will you ")
_PHRASES = frozenset(
    {
        "another",
        "another one",
        "another problem",
        "another harder",
        "another trickier",
        "give me another",
        "give me a harder one",
        "give me a trickier one",
        "one more",
        "one more problem",
        "next",
        "next one",
        "again",
        "do it again",
        "once more",
        "same again",
        "harder",
        "trickier",
        "easier",
        "harder one",
        "trickier one",
        "same but harder",
        "same but easier",
        "a harder one",
        "a trickier one",
        "make it harder",
        "make it trickier",
        "show me",
        "show me how",
        "show the steps",
        "show me the steps",
        "how",
        "how so",
        "why",
        "why not",
        "explain",
        "explain how",
        "explain it",
        "explain this",
        "go on",
        "continue",
        "keep going",
    }
)
_STATISTICS_CUES = (
    "standard deviation",
    "z-score",
    "z score",
    "p-value",
    "p value",
    "confidence interval",
    "normal distribution",
    "null hypothesis",
    "sample mean",
    "variance",
)
_BIOLOGY_CUES = (
    "dilution",
    "punnett",
    "hardy-weinberg",
    "hardy weinberg",
    "allele",
    "enzyme kinetics",
    "michaelis",
    "population growth",
)


def is_pure_continuation(text: str | None) -> bool:
    """True only for an exact continuation phrase, not a new question."""
    if not text:
        return False
    collapsed = collapse_ws(text)
    if not collapsed or len(collapsed) > _MAX_CHARS:
        return False
    if is_writing_deliverable_request(collapsed):
        return False
    if is_lightweight_chat_turn(collapsed):
        return False
    return _phrase(collapsed) in _PHRASES


def classify_presentation_subject(text: str | None) -> str | None:
    """Subject of this text, or None when it does not name one."""
    if not text or not text.strip():
        return None
    from app.modules.chemistry.request import is_chemistry_question
    from app.modules.math.tools.prompt import needs_symbolic_math
    from app.modules.physics.extract import needs_physics

    if needs_physics(text):
        return "physics"
    if is_chemistry_question(text):
        return "chemistry"
    if _has_phrase(text, _STATISTICS_CUES):
        return "statistics"
    if _has_digit(text) and _has_phrase(text, _BIOLOGY_CUES):
        return "biology"
    if needs_symbolic_math(text):
        return "math"
    return None


def blocks_math_followup(text: str) -> bool:
    """A physics problem is not replayed through the math solver."""
    from app.modules.physics.extract import needs_physics

    return needs_physics(text)


def effective_presentation_subject(
    query: str | None,
    prior_messages: Sequence[tuple[str, str]] | None = None,
) -> str | None:
    """Subject hints for this turn, including a pure continuation."""
    if not query or not query.strip():
        return None
    own = classify_presentation_subject(query)
    if own:
        return own
    if not is_pure_continuation(query):
        return None
    return _continuation_subject(prior_messages or ())


def _phrase(text: str) -> str:
    cleaned = collapse_ws(text).lower().strip(" \"'`")
    cleaned = cleaned.strip(".,!?:;")
    changed = True
    while changed:
        changed = False
        for prefix in _POLITE_PREFIXES:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix) :].strip()
                changed = True
    if cleaned.endswith(" please"):
        cleaned = cleaned[: -len(" please")].strip()
    return cleaned.strip(".,!?:;")


def _continuation_subject(messages: Sequence[tuple[str, str]]) -> str | None:
    index = len(messages) - 1
    while index >= 0:
        role, content = messages[index]
        if role != "user":
            index -= 1
            continue
        if is_pure_continuation(content):
            index -= 1
            continue
        subject = classify_presentation_subject(content)
        if subject:
            return subject
        for later_role, later in messages[index + 1 :]:
            if later_role == "user":
                break
            if later_role == "assistant":
                subject = classify_presentation_subject(later)
                if subject:
                    return subject
        return None
    return None


def _has_digit(text: str) -> bool:
    return any(char.isdigit() for char in text)


def _has_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(_contains_phrase(text, phrase) for phrase in phrases)


def _contains_phrase(haystack: str, phrase: str) -> bool:
    lower = haystack.lower()
    start = 0
    size = len(phrase)
    while True:
        index = lower.find(phrase, start)
        if index < 0:
            return False
        before = lower[index - 1] if index else " "
        after = lower[index + size] if index + size < len(lower) else " "
        if not before.isalnum() and not after.isalnum():
            return True
        start = index + 1
