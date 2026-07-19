"""Detect composer image-generation intent (mirrors mobile imageGenIntent.ts)."""

from __future__ import annotations

import re

_IMAGE_NOUN = re.compile(
    r"\b(?:images?|pictures?|pics?|photos?|illustrations?|artworks?|drawings?|portraits?)\b",
    re.I,
)

_VERB_THEN_IMAGE = re.compile(
    r"^(?:please\s+)?(?:can you\s+)?"
    r"(?:create|generate|make|design|render|produce)\s+"
    r"(?:me\s+)?(?:an?\s+)?"
    r"(?:image|picture|pic|photo|illustration|artwork|drawing|portrait)\s+"
    r"(?:of\s+)?(.+)$",
    re.I,
)

_VERB_SUBJECT_IMAGE = re.compile(
    r"^(?:please\s+)?(?:can you\s+)?"
    r"(?:create|generate|make|design|render|produce)\s+"
    r"(?:me\s+)?(?:an?\s+)?(.+?)\s+"
    r"(?:image|picture|pic|photo|illustration|artwork|drawing|portrait)$",
    re.I,
)

_DRAW_ME = re.compile(
    r"^(?:please\s+)?(?:can you\s+)?(?:draw|paint|illustrate)\s+me\s+(?:an?\s+)?(.+)$",
    re.I,
)

_CREATE_OR_DRAW_SUBJECT = re.compile(
    r"^(?:please\s+)?(?:can you\s+)?"
    r"(?:create|generate|make|draw|paint|illustrate)\s+"
    r"(?:me\s+)?(?:an?\s+)?(.+)$",
    re.I,
)

_NON_IMAGE_DRAW = re.compile(
    r"\b(?:conclusion|inference|boundary|line|diagram|chart|graph|plot|"
    r"sketch\s+of\s+the\s+idea)\b",
    re.I,
)

_NON_IMAGE_SUBJECT = re.compile(
    r"\b(?:"
    r"todos?|tasks?|lists?|reminders?|projects?|accounts?|scripts?|code|"
    r"functions?|classes?|files?|folders?|chats?|notes?|summar(?:y|ies)|"
    r"plans?|schedules?|events?|meetings?|quizzes?|flashcards?|emails?|"
    r"messages?|replies?|drafts?|reports?|endpoints?|apis?|databases?|"
    r"tables?|components?|hooks?|pages?|screens?|modals?|buttons?|forms?|"
    r"users?|passwords?|logins?|prs?|pull\s+requests?|commits?|branches?|"
    r"issues?|bugs?|tests?|arrays?|objects?|strings?|comparisons?"
    r")\b",
    re.I,
)

_CODEISH = re.compile(r"\b(?:compression|script|code|algorithm|function|api)\b", re.I)

_USER_MESSAGE_PREFIX = "Generate image: "


def _clean_prompt(raw: str) -> str | None:
    prompt = raw.strip().rstrip(".!?").strip()
    if not prompt or len(prompt) < 2:
        return None
    if _CODEISH.search(prompt):
        return None
    return prompt


def _short_create_subject(trimmed: str) -> str | None:
    if len(trimmed) > 80:
        return None
    match = _CREATE_OR_DRAW_SUBJECT.match(trimmed)
    if not match:
        return None
    subject = match.group(1).strip()
    if len(subject.split()) > 8:
        return None
    if _NON_IMAGE_SUBJECT.search(subject) or _NON_IMAGE_DRAW.search(subject):
        return None
    return _clean_prompt(subject)


def extract_image_gen_prompt(text: str) -> str | None:
    """Return the image subject if ``text`` is a clear image-gen ask, else None."""
    trimmed = text.strip()
    if not trimmed or len(trimmed) > 500:
        return None

    if trimmed.lower().startswith(_USER_MESSAGE_PREFIX.lower()):
        return _clean_prompt(trimmed[len(_USER_MESSAGE_PREFIX) :])

    match = _VERB_THEN_IMAGE.match(trimmed)
    if match:
        return _clean_prompt(match.group(1))

    match = _VERB_SUBJECT_IMAGE.match(trimmed)
    if match:
        return _clean_prompt(match.group(1))

    match = _DRAW_ME.match(trimmed)
    if match:
        subject = match.group(1)
        if _NON_IMAGE_DRAW.search(subject):
            return None
        return _clean_prompt(subject)

    short = _short_create_subject(trimmed)
    if short:
        return short

    if len(trimmed) <= 80 and _IMAGE_NOUN.search(trimmed):
        stripped = _IMAGE_NOUN.sub("", trimmed)
        stripped = re.sub(r"^(?:an?\s+)", "", stripped, flags=re.I).strip()
        if len(stripped) >= 2 and not re.search(
            r"\b(?:script|code|compression|format|file)\b", stripped, re.I
        ):
            return _clean_prompt(stripped)

    return None
