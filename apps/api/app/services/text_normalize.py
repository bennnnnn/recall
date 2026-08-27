"""Shared text normalization helpers."""

from __future__ import annotations

_HEAD_TAIL_SEP = "\n…\n"
# Zero-width / BOM — iOS sometimes leaves these on a two-letter greeting.
_FORMAT_CHARS = frozenset("\u200b\u200c\u200d\ufeff\u2060")


def collapse_ws(text: str) -> str:
    """Collapse runs of whitespace so matchers need no ``\\s+`` (avoids ReDoS)."""
    if any(ch in _FORMAT_CHARS for ch in text):
        text = "".join(ch for ch in text if ch not in _FORMAT_CHARS)
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
