"""Shared prompt-message injection helpers."""

from __future__ import annotations


def inject_before_last_user(messages: list[dict[str, str]], block: str) -> list[dict[str, str]]:
    """Insert a system block immediately before the last user message."""
    augmented = list(messages)
    insert_at = len(augmented)
    for index in range(len(augmented) - 1, -1, -1):
        if augmented[index].get("role") == "user":
            insert_at = index
            break
    augmented.insert(insert_at, {"role": "system", "content": block})
    return augmented
