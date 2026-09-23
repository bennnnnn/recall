"""Strip leftover Learning fences the model still sometimes emits into chat."""

from __future__ import annotations

import json

from app.services.md_fence_scan import find_lang_opener, iter_closed_fences, strip_closed_fences

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


def _is_vocab_session_metadata(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    return any(key in data for key in _SESSION_METADATA_KEYS)


def _drop_open_fence(content: str, lang: str) -> str:
    opener = find_lang_opener(content, lang)
    if opener is None:
        return content
    return content[:opener].rstrip()


def strip_vocab_quiz_fences(content: str) -> str:
    """Drop leftover ```vocab_quiz / ```vocab_card — chat no longer grades them."""
    stripped = strip_closed_fences(content, "vocab_quiz")
    stripped = strip_closed_fences(stripped, "vocab_card")
    stripped = _drop_open_fence(stripped, "vocab_quiz")
    return _drop_open_fence(stripped, "vocab_card")


def strip_vocab_session_metadata(content: str) -> str:
    """Remove ```json fences the model sometimes emits when a daily vocab session ends."""
    pieces: list[str] = []
    cursor = 0
    for start, end, body in iter_closed_fences(content, "json"):
        try:
            data = json.loads(body.strip())
        except json.JSONDecodeError:
            continue
        if _is_vocab_session_metadata(data):
            pieces.append(content[cursor:start])
            cursor = end
    leftover = content[cursor:]
    opener = find_lang_opener(leftover, "json")
    if opener is not None:
        tail = leftover[opener:].lower()
        if any(key.lower() in tail for key in _SESSION_METADATA_KEYS):
            leftover = leftover[:opener]
    pieces.append(leftover)
    return "".join(pieces).strip()


def strip_learning_chat_fences(content: str) -> str:
    """Drop dead in-chat Learning protocol before persist."""
    return strip_vocab_session_metadata(strip_vocab_quiz_fences(content))
