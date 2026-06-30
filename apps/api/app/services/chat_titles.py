"""Shared helpers for chat title validation and display."""

BORING_CHAT_TITLES = frozenset(
    {
        "new chat",
        "untitled",
        "chat",
        "conversation",
        "new conversation",
    }
)


def normalize_chat_title(raw: str | None) -> str | None:
    if not raw:
        return None
    title = raw.strip().strip('"').strip("'")
    if not title:
        return None
    if title.lower() in BORING_CHAT_TITLES:
        return None
    if len(title) < 3 or len(title) > 80:
        return None
    return title


def sanitize_manual_chat_title(raw: str) -> str | None:
    """User-chosen title — allow boring labels; trim quotes and enforce length."""
    title = raw.strip().strip('"').strip("'").strip()
    if not title or len(title) > 80:
        return None
    return title
