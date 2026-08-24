"""Extract allowlisted settings changes from a chat line.

Linear token / phrase scans only — no ``\\s+`` / ``.+`` regex on user text
(CodeQL ``py/polynomial-redos``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.validation import LOCALE_NAMES
from app.services.response_tone import TONE_IDS

SettingsField = Literal["appearance", "default_model", "response_tone", "locale"]

# Product aliases the composer / Settings use — not provider names.
_MODEL_NICKNAMES: dict[str, str] = {
    "auto": "auto",
    "automatic": "auto",
    "flash": "free-chat",
    "free": "free-chat",
    "fast": "free-chat",
    "pro": "smart-chat",
    "smart": "smart-chat",
    "plus": "smart-chat",
    "gpt": "gpt-5.5",
    "chatgpt": "gpt-5.5",
}

_MODEL_IDS = frozenset({"auto", "free-chat", "smart-chat", "gpt-5.5"})

_TONE_NICKNAMES: dict[str, str] = {
    "funny": "funny",
    "funnier": "funny",
    "funniest": "funny",
    "humor": "funny",
    "humour": "funny",
    "humorous": "funny",
    "playful": "funny",
    "witty": "funny",
    "professional": "professional",
    "formal": "professional",
    "serious": "professional",
    "casual": "casual",
    "relaxed": "casual",
    "chill": "casual",
    "soft": "soft",
    "softer": "soft",
    "gentle": "soft",
    "gentler": "soft",
    "kind": "soft",
    "kinder": "soft",
    "warm": "soft",
    "warmer": "soft",
}

_APPEARANCE_NICKNAMES: dict[str, str] = {
    "dark": "dark",
    "night": "dark",
    "light": "light",
    "day": "light",
    "system": "system",
    # "default" = follow the system theme, the product default. Without
    # this the heuristic misses "switch to default theme" and the user has no
    # way to undo an explicit light/dark choice via chat. ("auto" is NOT
    # aliased here — it collides with the "auto" model alias.)
    "default": "system",
}

_LANGUAGE_NICKNAMES: dict[str, str] = {
    "english": "en",
    "spanish": "es",
    "espanol": "es",
    "español": "es",
    "french": "fr",
    "francais": "fr",
    "français": "fr",
    "german": "de",
    "deutsch": "de",
    "italian": "it",
    "italiano": "it",
    "portuguese": "pt",
    "portugues": "pt",
    "português": "pt",
    "russian": "ru",
    "turkish": "tr",
    "amharic": "am",
}

_CHANGE_CUES = frozenset(
    {
        "switch",
        "change",
        "set",
        "use",
        "enable",
        "turn",
        "go",
        "put",
        "make",
        "be",
    }
)

_CONTENT_VERBS = frozenset(
    {
        "write",
        "draft",
        "explain",
        "summarize",
        "translate",
        "tell",
        "show",
        "list",
        "create",
        "generate",
        "draw",
    }
)

_SETTINGS_NOUNS = frozenset(
    {
        "theme",
        "appearance",
        "mode",
        "model",
        "models",
        "tone",
        "humour",
        "humor",
        "language",
        "locale",
        "setting",
        "settings",
    }
)

_PUNCT = frozenset("?!.,;:\"'`")

_MAX_COMMAND_TOKENS = 12


@dataclass(frozen=True, slots=True)
class SettingsChange:
    field: SettingsField
    value: str


def _strip_punct(token: str) -> str:
    start = 0
    end = len(token)
    while start < end and token[start] in _PUNCT:
        start += 1
    while end > start and token[end - 1] in _PUNCT:
        end -= 1
    return token[start:end]


def _tokens(content: str) -> list[str]:
    return [_strip_punct(part).lower() for part in content.split() if _strip_punct(part)]


def _has_content_request(tokens: list[str]) -> bool:
    return any(token in _CONTENT_VERBS for token in tokens)


def _has_change_cue(tokens: list[str]) -> bool:
    return any(token in _CHANGE_CUES for token in tokens)


def _has_settings_noun(tokens: list[str]) -> bool:
    return any(token in _SETTINGS_NOUNS for token in tokens)


def _looks_like_command(tokens: list[str]) -> bool:
    if not tokens or len(tokens) > _MAX_COMMAND_TOKENS:
        return False
    if _has_content_request(tokens):
        return False
    return _has_change_cue(tokens) or _has_settings_noun(tokens) or len(tokens) <= 4


def _window_has(tokens: list[str], left: str, right: str) -> bool:
    for index, token in enumerate(tokens[:-1]):
        if token == left and tokens[index + 1] == right:
            return True
    return False


def _extract_appearance(tokens: list[str]) -> str | None:
    if _window_has(tokens, "match", "system"):
        return "system"
    for index, word in enumerate(tokens):
        value = _APPEARANCE_NICKNAMES.get(word)
        if value is None:
            continue
        nxt = tokens[index + 1] if index + 1 < len(tokens) else ""
        prev = tokens[index - 1] if index > 0 else ""
        if nxt in {"mode", "theme", "appearance"} or prev in {"theme", "appearance", "to"}:
            return value
        if word in {"dark", "light"} and (nxt == "" or nxt in _CHANGE_CUES or nxt == "please"):
            if _has_change_cue(tokens) or _has_settings_noun(tokens) or len(tokens) <= 3:
                return value
        if word == "system" and nxt in {"theme", "appearance", "mode"}:
            return "system"
    return None


def _extract_model(tokens: list[str]) -> str | None:
    for index, token in enumerate(tokens):
        if token in _MODEL_IDS:
            return token
        nick = _MODEL_NICKNAMES.get(token)
        if nick is None:
            continue
        nxt = tokens[index + 1] if index + 1 < len(tokens) else ""
        prev = tokens[index - 1] if index > 0 else ""
        if nxt in {"model", "mode", "chat"} or prev in {"model", "to", "use", "on"}:
            return nick
        if token in _MODEL_NICKNAMES and (
            _has_change_cue(tokens) or _has_settings_noun(tokens) or len(tokens) <= 3
        ):
            return nick
    return None


def _extract_tone(tokens: list[str]) -> str | None:
    for index, token in enumerate(tokens):
        nick = _TONE_NICKNAMES.get(token)
        if nick is None:
            continue
        prev = tokens[index - 1] if index > 0 else ""
        nxt = tokens[index + 1] if index + 1 < len(tokens) else ""
        if prev in {"be", "more", "less", "sound", "tone"} or nxt == "tone":
            return nick
        if token in TONE_IDS and (_has_change_cue(tokens) or nxt == "tone" or len(tokens) <= 3):
            return nick
        if token in {"funnier", "softer", "gentler", "kinder", "warmer"}:
            return nick
    return None


def _extract_locale(tokens: list[str]) -> str | None:
    for index, token in enumerate(tokens):
        if token in LOCALE_NAMES:
            prev = tokens[index - 1] if index > 0 else ""
            # Bare ISO codes collide with English ("it", "am"). Need a language cue.
            if prev in {"language", "locale"}:
                return token
            if prev == "to" and ("language" in tokens or "locale" in tokens):
                return token
        nick = _LANGUAGE_NICKNAMES.get(token)
        if nick is None:
            continue
        prev = tokens[index - 1] if index > 0 else ""
        nxt = tokens[index + 1] if index + 1 < len(tokens) else ""
        if (
            prev in {"to", "in", "language", "locale", "speak"}
            or nxt in {"language", "please"}
            or _has_change_cue(tokens)
        ):
            return nick
    return None


def extract_settings_changes(content: str) -> list[SettingsChange]:
    """Return allowlisted changes, or empty if this is not a settings command."""
    tokens = _tokens(content)
    if not _looks_like_command(tokens):
        return []

    found: list[SettingsChange] = []
    seen: set[SettingsField] = set()

    appearance = _extract_appearance(tokens)
    if appearance is not None:
        found.append(SettingsChange("appearance", appearance))
        seen.add("appearance")

    model = _extract_model(tokens)
    if model is not None:
        found.append(SettingsChange("default_model", model))
        seen.add("default_model")

    tone = _extract_tone(tokens)
    if tone is not None:
        found.append(SettingsChange("response_tone", tone))
        seen.add("response_tone")

    locale = _extract_locale(tokens)
    if locale is not None:
        found.append(SettingsChange("locale", locale))
        seen.add("locale")

    if not found:
        return []
    # A lone language word in a long-ish line without a cue is too easy to misfire.
    if seen == {"locale"} and not _has_change_cue(tokens) and "language" not in tokens:
        return []
    return found
