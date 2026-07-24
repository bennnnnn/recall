"""Detect composer image-generation intent (mirrors mobile imageGenIntent.ts).

Matching is linear token scans — no ``\\s+`` / ``.+`` regex on user chat text
(CodeQL ``py/polynomial-redos``).
"""

from __future__ import annotations

from typing import Any

_USER_MESSAGE_PREFIX = "Generate image: "

_VERBS_IMAGE = frozenset(
    {"create", "generate", "make", "design", "render", "produce"},
)
_VERBS_DRAW = frozenset({"draw", "paint", "illustrate"})
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
        # Learning / chat asks — "make your own example" is not a picture.
        "example",
        "examples",
        "problem",
        "problems",
        "equation",
        "equations",
        "question",
        "questions",
        "exercise",
        "exercises",
        "homework",
        "solution",
        "solutions",
        "proof",
        "proofs",
        "worksheet",
        "worksheets",
        "assignment",
        "assignments",
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
    if _has_non_image_subject(subject) or _has_non_image_draw(subject):
        return None
    return _clean_prompt(subject)


def _match_short_create(tokens: list[str]) -> str | None:
    """draw/paint/illustrate [me] [a/an] SUBJECT — short subjects only.

    ``make`` / ``create`` / ``generate`` (etc.) are *not* matched here — they
    need an explicit image noun via the other matchers, so chat asks like
    ``make your own example`` stay in the normal LLM turn.
    """
    if len(tokens) < 2:
        return None
    verb = tokens[0].lower()
    # Ambiguous verbs need "… pic/image/photo" (see _match_verb_*).
    if verb in _VERBS_IMAGE:
        return None
    if verb not in _VERBS_DRAW:
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


_NON_REVISION = frozenset(
    {
        "ok",
        "okay",
        "thanks",
        "thank you",
        "yes",
        "no",
        "sure",
        "cool",
        "nice",
        "lol",
        "great",
        "got it",
        "perfect",
    }
)


def subject_from_image_gen_user_message(content: str) -> str | None:
    """Subject from a prior ``Generate image: …`` user bubble, if any."""
    trimmed = content.strip()
    if not trimmed.lower().startswith(_USER_MESSAGE_PREFIX.lower()):
        return None
    return _clean_prompt(trimmed[len(_USER_MESSAGE_PREFIX) :])


def is_image_only_assistant_content(content: str) -> bool:
    """True when the assistant bubble is only an ``[Image: …]`` marker."""
    has_image = False
    for line in content.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("[Image:") and s.endswith("]") and len(s) > len("[Image:]"):
            has_image = True
            continue
        return False
    return has_image


def _strip_revision_lead_in(tokens: list[str]) -> list[str]:
    """Drop ``make it`` / ``change them to`` / ``now`` style lead-ins (linear)."""
    i = 0
    n = len(tokens)
    if i < n and tokens[i].lower() == "please":
        i += 1
    if (
        i + 1 < n
        and tokens[i].lower() == "make"
        and tokens[i + 1].lower()
        in {
            "it",
            "them",
        }
    ):
        return tokens[i + 2 :]
    if (
        i + 1 < n
        and tokens[i].lower() == "change"
        and tokens[i + 1].lower()
        in {
            "it",
            "them",
        }
    ):
        j = i + 2
        if j < n and tokens[j].lower() == "to":
            j += 1
        return tokens[j:]
    if i < n and tokens[i].lower() in {"now", "again", "instead", "try"}:
        return tokens[i + 1 :]
    return tokens[i:]


def extract_image_revision_prompt(
    text: str,
    *,
    last_assistant_is_image_only: bool,
    previous_subject: str | None,
) -> str | None:
    """Short follow-up after an image-only reply → new generate prompt."""
    if not last_assistant_is_image_only or not previous_subject:
        return None
    trimmed = text.strip()
    if not trimmed or len(trimmed) > 120:
        return None

    tokens = _strip_revision_lead_in(_tokens(trimmed))
    if not tokens or len(tokens) > 8:
        return None
    revision = _join_subject(tokens)
    if not revision:
        return None
    if revision.lower() in _NON_REVISION:
        return None
    if _has_non_image_subject(revision):
        return None
    cleaned = _clean_prompt(revision)
    if not cleaned:
        return None
    return f"{previous_subject}, {cleaned}"


def image_gen_revision_context(
    messages: list[Any],
) -> tuple[bool, str | None]:
    """Walk newest→oldest for image-gen context used by revision intercept."""
    last_assistant_is_image_only = False
    previous_subject: str | None = None
    for row in reversed(messages):
        role = getattr(row, "role", None)
        content = getattr(row, "content", None)
        if role is None and isinstance(row, dict):
            role = row.get("role")
            content = row.get("content")
        if not isinstance(content, str):
            content = ""
        if not last_assistant_is_image_only and role == "assistant":
            last_assistant_is_image_only = is_image_only_assistant_content(content)
            if not last_assistant_is_image_only:
                break
            continue
        if last_assistant_is_image_only and role == "user":
            previous_subject = subject_from_image_gen_user_message(content)
            break
    return last_assistant_is_image_only, previous_subject
