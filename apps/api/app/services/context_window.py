"""Token estimation + token-budget windowing for prompt context.

Pure helpers (no app imports) so both the chat service and the background
compaction job can share them without import cycles.
"""

from typing import Any


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


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
