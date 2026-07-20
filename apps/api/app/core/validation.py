"""Pure input validators shared by Pydantic schemas (no DB/IO/services)."""

from __future__ import annotations

import re

# Keep in sync with app.services.model_catalog.CATALOG ids (asserted in tests).
KNOWN_MODEL_ALIASES: frozenset[str] = frozenset(
    {
        "free-chat",
        "smart-chat",
        "minimax-m2",
        "glm-4-flash",
        "glm-5.2",
        "gpt-5.5",
        "qwen-plus",
        "gemini-flash",
        "mercury-2",
        "llama-70b",
        "max-chat",
        "title-model",
        "memory-model",
        "fallback-memory-model",
        "embedding-model",
        "vision-chat",
        "image-gen-model",
    }
)

# ISO 639-1 codes supported by the mobile app (see apps/mobile/lib/i18n/languages.ts).
LOCALE_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "tr": "Turkish",
    "am": "Amharic",
}

BORING_CHAT_TITLES = frozenset(
    {
        "new chat",
        "untitled",
        "chat",
        "conversation",
        "new conversation",
    }
)


def normalize_display_name(raw: str | None) -> str | None:
    """Trim, collapse whitespace, and enforce length for user-visible names."""
    if raw is None:
        return None
    name = " ".join(raw.strip().split())
    if not name or len(name) > 80:
        return None
    return name


def normalize_locale_code(locale: str | None) -> str:
    if not locale:
        return "en"
    return locale.split("-")[0].lower()


# Straight + curly quotes models often wrap titles with.
_TITLE_QUOTES = "\"'" + "\u201c\u201d\u2018\u2019"
# Trailing sentence punctuation that can sit outside the closing quote.
_TITLE_TRAIL_PUNCT = ".!?,;:"
# One-shot unwrap: leading quotes, or trailing quotes + optional punct.
_TITLE_WRAP_RE = re.compile(
    rf"^[{re.escape(_TITLE_QUOTES)}]+|[{re.escape(_TITLE_QUOTES)}]+[{re.escape(_TITLE_TRAIL_PUNCT)}]*$"
)


def unwrap_chat_title(raw: str) -> str:
    """Strip wrapping quotes/punct until stable (fixes '"My Trip Plan".')."""
    title = raw.strip()
    while True:
        prev = title
        title = _TITLE_WRAP_RE.sub("", title).strip()
        title = title.rstrip(_TITLE_TRAIL_PUNCT).strip()
        title = title.strip(_TITLE_QUOTES).strip()
        if title == prev:
            return title


def normalize_chat_title(raw: str | None) -> str | None:
    if not raw:
        return None
    title = unwrap_chat_title(raw)
    if not title:
        return None
    if title.lower() in BORING_CHAT_TITLES:
        return None
    if len(title) < 3 or len(title) > 80:
        return None
    return title


def validate_user_alias(alias: str, *, allow_auto: bool = False) -> None:
    if allow_auto and alias == "auto":
        return
    if alias in KNOWN_MODEL_ALIASES:
        return
    raise ValueError(f"Unknown model alias: {alias}")
