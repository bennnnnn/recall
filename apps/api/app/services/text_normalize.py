"""Shared text normalization helpers."""

from __future__ import annotations


def collapse_ws(text: str) -> str:
    """Collapse runs of whitespace so matchers need no ``\\s+`` (avoids ReDoS)."""
    return " ".join(text.split())
