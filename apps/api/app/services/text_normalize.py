"""Shared text normalization helpers."""

from __future__ import annotations

_HEAD_TAIL_SEP = "\n…\n"


def collapse_ws(text: str) -> str:
    """Collapse runs of whitespace so matchers need no ``\\s+`` (avoids ReDoS)."""
    return " ".join(text.split())


def cap_text_head_tail(text: str, max_chars: int = 4000) -> str:
    """Keep the start and end of long text; drop the middle with an ellipsis marker."""
    if max_chars < 1 or len(text) <= max_chars:
        return text
    if max_chars <= len(_HEAD_TAIL_SEP):
        return text[:max_chars]
    budget = max_chars - len(_HEAD_TAIL_SEP)
    head = budget // 2
    tail = budget - head
    return f"{text[:head]}{_HEAD_TAIL_SEP}{text[-tail:]}"
