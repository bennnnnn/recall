"""Shared helpers for chat title validation and display."""

from app.core.validation import BORING_CHAT_TITLES as BORING_CHAT_TITLES
from app.core.validation import normalize_chat_title as normalize_chat_title


def sanitize_manual_chat_title(raw: str) -> str | None:
    """User-chosen title — allow boring labels; trim quotes and enforce length."""
    title = raw.strip().strip('"').strip("'").strip()
    if not title or len(title) > 80:
        return None
    return title
