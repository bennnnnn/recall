"""Token estimation + token-budget windowing for prompt context.

Pure helpers (no app imports) so both the chat service and the background
compaction job can share them without import cycles.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```")
_SUMMARY_MAX_CHARS = 6000
_SUMMARY_MESSAGE_MAX_CHARS = 1200

SUMMARY_SYSTEM_PROMPT = (
    "You compress a conversation into a concise running summary so an assistant can "
    "continue it later. Merge the existing summary with the new messages.\n\n"
    "Format (plain text, no markdown headings):\n"
    "Facts: durable preferences, names, numbers, decisions\n"
    "Topics: what was discussed and outcomes\n"
    "Open: unresolved questions or next steps\n\n"
    "Keep durable facts and decisions; drop greetings and filler. Reply with the "
    "summary only."
)


# Flat estimate for a vision ``image_url`` part when provider usage is missing.
_VISION_IMAGE_PART_TOKENS = 85


def estimate_tokens(text: str | list[Any]) -> int:
    """Rough token count — blends word/char heuristics; code blocks count denser.

    Accepts OpenAI-style multimodal ``content`` lists (vision turns) so finalize
    fallbacks do not crash when provider usage is absent.
    """
    if isinstance(text, list):
        total = 0
        for part in text:
            if isinstance(part, str):
                total += estimate_tokens(part)
            elif isinstance(part, dict):
                part_type = part.get("type")
                if part_type == "text" and isinstance(part.get("text"), str):
                    total += estimate_tokens(part["text"])
                elif part_type == "image_url":
                    total += _VISION_IMAGE_PART_TOKENS
        return max(1, total)

    stripped = text.strip()
    if not stripped:
        return 1

    dense_chars = sum(len(block) for block in _CODE_FENCE_RE.findall(stripped))
    plain_len = max(0, len(stripped) - dense_chars)
    words = len(stripped.split())
    char_est = plain_len / 3.6 + dense_chars / 2.5
    word_est = words * 1.35
    return max(1, int(max(char_est, word_est)))


def select_recent_window(
    messages: list[Any],
    budget: int,
    max_count: int,
    min_count: int = 2,
) -> int:
    """How many of the most recent messages to keep verbatim.

    Walks newest → oldest, accumulating estimated tokens. Keeps messages until
    the token budget or `max_count` is hit, but always keeps at least
    `min_count` (so the latest exchange is never dropped, even if it alone
    exceeds the budget). Returns the count of trailing messages to keep.
    """
    kept = 0
    tokens = 0
    for msg in reversed(messages):
        if kept >= max_count:
            break
        cost = estimate_tokens(msg.content)
        if kept >= min_count and tokens + cost > budget:
            break
        tokens += cost
        kept += 1
    return kept


@dataclass(frozen=True)
class HistorySplit:
    keep_count: int
    summarized_count: int
    window_tokens: int
    token_pressure: bool


def compute_history_split(
    total_message_count: int,
    recent_messages: list[Any],
    budget: int,
    max_count: int,
    min_count: int = 2,
) -> HistorySplit:
    """Split a chat into verbatim tail vs messages eligible for summarization."""
    keep = select_recent_window(recent_messages, budget, max_count, min_count)
    tail = recent_messages[-keep:] if keep else []
    window_tokens = sum(estimate_tokens(m.content) for m in tail)
    summarized = max(0, total_message_count - keep)
    token_pressure = keep < min(max_count, len(recent_messages))
    return HistorySplit(
        keep_count=keep,
        summarized_count=summarized,
        window_tokens=window_tokens,
        token_pressure=token_pressure,
    )


def should_run_compression(
    split: HistorySplit,
    already_summarized: int,
    batch: int,
    *,
    urgent_min_pending: int = 3,
) -> bool:
    """Whether the background job should fold more messages into the summary."""
    pending = split.summarized_count - already_summarized
    if pending <= 0:
        return False
    if pending >= batch:
        return True
    if split.token_pressure and pending >= urgent_min_pending:
        return True
    return False


def trim_message_for_summary(content: str, max_chars: int = _SUMMARY_MESSAGE_MAX_CHARS) -> str:
    text = content.strip()
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 20].rstrip()}… [truncated]"


def cap_summary(text: str, max_chars: int = _SUMMARY_MAX_CHARS) -> str:
    trimmed = text.strip()
    if len(trimmed) <= max_chars:
        return trimmed
    return f"{trimmed[: max_chars - 3].rstrip()}..."
