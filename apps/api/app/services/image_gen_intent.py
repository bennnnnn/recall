"""Detect composer image-generation intent (mirrors mobile imageGenIntent.ts).

Matching is linear token scans — no ``\\s+`` / ``.+`` regex on user chat text
(CodeQL ``py/polynomial-redos``).
"""

from __future__ import annotations

_USER_MESSAGE_PREFIX = "Generate image: "

_VERBS_IMAGE = frozenset(
    {"create", "generate", "make", "design", "render", "produce"},
)
_VERBS_DRAW = frozenset({"draw", "paint", "illustrate"})
_VERBS_CREATE_OR_DRAW = frozenset(
    {"create", "generate", "make", "draw", "paint", "illustrate"},
)
_IMAGE_NOUNS = frozenset(
    {
        "image",
        "images",
        "picture",
        "pictures",
        "pic",
        "pics",
        "photo",
        "photos",
        "illustration",
        "illustrations",
        "artwork",
        "artworks",
        "drawing",
        "drawings",
        "portrait",
        "portraits",
    },
)
_ARTICLES = frozenset({"a", "an"})
_REVISION_PRONOUNS = frozenset({"it", "them", "this", "that"})

_NON_IMAGE_WORDS = frozenset(
    {
        "todo",
        "todos",
        "task",
        "tasks",
        "list",
        "lists",
        "reminder",
        "reminders",
        "project",
        "projects",
        "account",
        "accounts",
        "script",
        "scripts",
        "code",
        "function",
        "functions",
        "class",
        "classes",
        "file",
        "files",
        "folder",
        "folders",
        "chat",
        "chats",
        "note",
        "notes",
        "summary",
        "summaries",
        "plan",
        "plans",
        "schedule",
        "schedules",
        "event",
        "events",
        "meeting",
        "meetings",
        "quiz",
        "quizzes",
        "flashcard",
        "flashcards",
        "email",
        "emails",
        "message",
        "messages",
        "reply",
        "replies",
        "draft",
        "drafts",
        "report",
        "reports",
        "endpoint",
        "endpoints",
        "api",
        "apis",
        "database",
        "databases",
        "table",
        "tables",
        "component",
        "components",
        "hook",
        "hooks",
        "page",
        "pages",
        "screen",
        "screens",
        "modal",
        "modals",
        "button",
        "buttons",
        "form",
        "forms",
        "user",
        "users",
        "password",
        "passwords",
        "login",
        "logins",
        "pr",
        "prs",
        "commit",
        "commits",
        "branch",
        "branches",
        "issue",
        "issues",
        "bug",
        "bugs",
        "test",
        "tests",
        "array",
        "arrays",
        "object",
        "objects",
        "string",
        "strings",
        "comparison",
        "comparisons",
    },
)

_NON_IMAGE_DRAW_WORDS = frozenset(
    {
        "conclusion",
        "inference",
        "boundary",
        "line",
        "diagram",
        "chart",
        "graph",
        "plot",
    },
)

_CODEISH_WORDS = frozenset(
    {"compression", "script", "code", "algorithm", "function", "api"},
)


def _tokens(text: str) -> list[str]:
    """Whitespace-split only — linear in ``len(text)``."""
    return text.split()


def _strip_polite(tokens: list[str]) -> list[str]:
    i = 0
    n = len(tokens)
    if i < n and tokens[i].lower() == "please":
        i += 1
    if i + 1 < n and tokens[i].lower() == "can" and tokens[i + 1].lower() == "you":
        i += 2
    return tokens[i:]


def _join_subject(parts: list[str]) -> str:
    return " ".join(parts).strip()


def _clean_prompt(raw: str) -> str | None:
    prompt = raw.strip().rstrip(".!?").strip()
    if not prompt or len(prompt) < 2:
        return None
    words = prompt.lower().split()
    if any(w in _CODEISH_WORDS for w in words):
        return None
    return prompt


def _has_non_image_subject(subject: str) -> bool:
    words = subject.lower().split()
    for i, word in enumerate(words):
        if word in _NON_IMAGE_WORDS:
            return True
        if word == "pull" and i + 1 < len(words) and words[i + 1] in {"request", "requests"}:
            return True
    return False


def _has_non_image_draw(subject: str) -> bool:
    lower = subject.lower()
    if "sketch of the idea" in lower:
        return True
    return any(word in _NON_IMAGE_DRAW_WORDS for word in lower.split())


def _match_verb_then_image(tokens: list[str]) -> str | None:
    """create/generate … image/pic … of? SUBJECT"""
    if len(tokens) < 3:
        return None
    if tokens[0].lower() not in _VERBS_IMAGE:
        return None
    i = 1
    if i < len(tokens) and tokens[i].lower() == "me":
        i += 1
    if i < len(tokens) and tokens[i].lower() in _ARTICLES:
        i += 1
    if i >= len(tokens) or tokens[i].lower() not in _IMAGE_NOUNS:
        return None
    i += 1
    if i < len(tokens) and tokens[i].lower() == "of":
        i += 1
    if i >= len(tokens):
        return None
    return _clean_prompt(_join_subject(tokens[i:]))


def _match_verb_subject_image(tokens: list[str]) -> str | None:
    """create/generate … SUBJECT image/pic/photo"""
    if len(tokens) < 3:
        return None
    if tokens[0].lower() not in _VERBS_IMAGE:
        return None
    if tokens[-1].lower() not in _IMAGE_NOUNS:
        return None
    i = 1
    if i < len(tokens) - 1 and tokens[i].lower() == "me":
        i += 1
    if i < len(tokens) - 1 and tokens[i].lower() in _ARTICLES:
        i += 1
    subject_parts = tokens[i:-1]
    if not subject_parts:
        return None
    return _clean_prompt(_join_subject(subject_parts))


def _match_draw_me(tokens: list[str]) -> str | None:
    """draw/paint/illustrate me [a/an] SUBJECT"""
    if len(tokens) < 3:
        return None
    if tokens[0].lower() not in _VERBS_DRAW:
        return None
    if tokens[1].lower() != "me":
        return None
    i = 2
    if i < len(tokens) and tokens[i].lower() in _ARTICLES:
        i += 1
    if i >= len(tokens):
        return None
    subject = _join_subject(tokens[i:])
    if _has_non_image_draw(subject):
        return None
    return _clean_prompt(subject)


def _match_short_create(tokens: list[str]) -> str | None:
    """create/draw [me] [a/an] SUBJECT — short subjects only."""
    if len(tokens) < 2:
        return None
    if tokens[0].lower() not in _VERBS_CREATE_OR_DRAW:
        return None
    i = 1
    if i < len(tokens) and tokens[i].lower() == "me":
        i += 1
    if i < len(tokens) and tokens[i].lower() in _ARTICLES:
        i += 1
    subject_parts = tokens[i:]
    if not subject_parts or len(subject_parts) > 8:
        return None
    if subject_parts[0].lower() in _REVISION_PRONOUNS:
        return None
    subject = _join_subject(subject_parts)
    if _has_non_image_subject(subject) or _has_non_image_draw(subject):
        return None
    return _clean_prompt(subject)


def _match_image_noun_message(tokens: list[str]) -> str | None:
    """Short colloquial: 'cat pic' / 'sunset photo' as the full message."""
    if not tokens or len(tokens) > 16:
        return None
    if not any(tok.lower() in _IMAGE_NOUNS for tok in tokens):
        return None
    kept = [tok for tok in tokens if tok.lower() not in _IMAGE_NOUNS]
    i = 0
    if i < len(kept) and kept[i].lower() in _ARTICLES:
        i += 1
    subject = _join_subject(kept[i:])
    if len(subject) < 2:
        return None
    words = subject.lower().split()
    if any(w in {"script", "code", "compression", "format", "file"} for w in words):
        return None
    return _clean_prompt(subject)


def extract_image_gen_prompt(text: str) -> str | None:
    """Return the image subject if ``text`` is a clear image-gen ask, else None."""
    trimmed = text.strip()
    if not trimmed or len(trimmed) > 500:
        return None

    if trimmed.lower().startswith(_USER_MESSAGE_PREFIX.lower()):
        return _clean_prompt(trimmed[len(_USER_MESSAGE_PREFIX) :])

    tokens = _strip_polite(_tokens(trimmed))
    if not tokens:
        return None

    matched = _match_verb_then_image(tokens)
    if matched:
        return matched

    matched = _match_verb_subject_image(tokens)
    if matched:
        return matched

    matched = _match_draw_me(tokens)
    if matched:
        return matched

    # Short create/draw only when the whole message is short (same as before).
    if len(trimmed) <= 80:
        matched = _match_short_create(tokens)
        if matched:
            return matched
        matched = _match_image_noun_message(tokens)
        if matched:
            return matched

    return None
