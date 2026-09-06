"""Detect composer reference-photo *lookup* intent (mirrors mobile imageLookupIntent.ts).

Separate from ``image_gen_intent`` (creative generation). "Show me an ear" /
"what does a golden retriever look like" want a real photo, not AI art —
this module recognizes that distinct phrasing so the router can send it to
``image_search`` instead of ``generate_image``.

Checked *before* generation intent in the caller: none of the trigger verbs
here ("show", "let … see", "what does … look like") overlap with
generation's verb set (create/generate/make/design/render/produce/draw/
paint/illustrate), so this only changes behavior for phrasing generation
did not already own on purpose (see the "show me a picture of X" bug this
fixes — generation's bare colloquial fallback used to mis-parse it).

Matching is linear token scans — no ``\\s+`` / ``.+`` regex on user chat text
(CodeQL ``py/polynomial-redos``), same discipline as ``image_gen_intent``.
"""

from __future__ import annotations

_ARTICLES = frozenset({"a", "an", "the"})
_POSSESSIVES = frozenset({"my", "your", "our", "his", "her", "their", "its"})
_REFERENCE_NOUNS = frozenset(
    {"picture", "pictures", "photo", "photos", "image", "images", "pic", "pics"}
)

# "show me my todos", "show me the code", "show me how to solve this" — this
# extremely common product phrase must NOT be hijacked into an image search.
# Extends image_gen_intent's non-image denylist with app/chat content nouns
# and explanation cues that "show me" / "what does X look like" commonly ask
# for outside of visual object identification.
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
        "deck",
        "decks",
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
        "settings",
        "profile",
        "subscription",
        "password",
        "passwords",
        "history",
        "progress",
        "streak",
        "streaks",
        "score",
        "scores",
        "result",
        "results",
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
        "answer",
        "answers",
        "proof",
        "proofs",
        "worksheet",
        "worksheets",
        "assignment",
        "assignments",
        "step",
        "steps",
        "graph",
        "graphs",
        "chart",
        "charts",
        "diagram",
        "diagrams",
        "table",
        "tables",
        "formula",
        "formulas",
        "calculation",
        "calculations",
        "translation",
        "definition",
        "meaning",
        "transcript",
        "attachment",
        "attachments",
        "document",
        "documents",
        "pdf",
        "explanation",
        "breakdown",
        "method",
        "methods",
        "working",
        "workings",
        "derivation",
    },
)

# "show me how to solve this" / "what does X mean" — explanation cues embedded
# in the subject, not an object to photograph.
_EXPLANATION_CUES = frozenset(
    {
        "how",
        "why",
        "when",
        "where",
        "what",
        "solve",
        "explain",
        "prove",
        "calculate",
        "compute",
        "work",
        "works",
        "mean",
        "means",
    }
)

_MAX_SUBJECT_WORDS = 8


def _tokens(text: str) -> list[str]:
    return text.split()


def _clean_subject(raw: str) -> str | None:
    subject = raw.strip().rstrip(".!?").strip()
    if not subject or len(subject) < 2:
        return None
    words = subject.lower().split()
    if not words or len(words) > _MAX_SUBJECT_WORDS:
        return None
    if words[0] in _POSSESSIVES:
        return None
    if any(w in _NON_IMAGE_WORDS or w in _EXPLANATION_CUES for w in words):
        return None
    return subject


def _strip_reference_noun_prefix(tokens: list[str]) -> list[str]:
    """ "[a/an/the]? picture/photo/image of SUBJECT" -> SUBJECT tokens."""
    i = 0
    if i < len(tokens) and tokens[i].lower() in _ARTICLES:
        i += 1
    if i < len(tokens) and tokens[i].lower() in _REFERENCE_NOUNS:
        i += 1
        if i < len(tokens) and tokens[i].lower() == "of":
            i += 1
        return tokens[i:]
    return tokens


def _strip_leading_article(tokens: list[str]) -> list[str]:
    if tokens and tokens[0].lower() in _ARTICLES:
        return tokens[1:]
    return tokens


def _match_show_me(tokens: list[str]) -> str | None:
    """ "show me [a/an/the]? [picture/photo/image of]? SUBJECT" """
    if len(tokens) < 2 or tokens[0].lower() != "show":
        return None
    i = 1
    if i < len(tokens) and tokens[i].lower() == "me":
        i += 1
    remaining = _strip_leading_article(tokens[i:])
    remaining = _strip_reference_noun_prefix(remaining)
    remaining = _strip_leading_article(remaining)
    if not remaining:
        return None
    return _clean_subject(" ".join(remaining))


def _match_let_me_see(tokens: list[str]) -> str | None:
    """ "let me see [a/an/the]? SUBJECT" """
    if len(tokens) < 4:
        return None
    if tokens[0].lower() != "let" or tokens[1].lower() != "me" or tokens[2].lower() != "see":
        return None
    remaining = _strip_leading_article(tokens[3:])
    remaining = _strip_reference_noun_prefix(remaining)
    remaining = _strip_leading_article(remaining)
    if not remaining:
        return None
    return _clean_subject(" ".join(remaining))


def _match_look_like(tokens: list[str]) -> str | None:
    """ "what does/do [a/an/the]? SUBJECT look like" """
    if len(tokens) < 5 or tokens[0].lower() != "what":
        return None
    if tokens[1].lower() not in {"does", "do"}:
        return None
    if tokens[-1].lower().rstrip("?.!") != "like" or tokens[-2].lower() != "look":
        return None
    subject_tokens = _strip_leading_article(tokens[2:-2])
    if not subject_tokens:
        return None
    return _clean_subject(" ".join(subject_tokens))


def extract_image_lookup_query(text: str) -> str | None:
    """Return the reference-photo subject if ``text`` clearly wants a real photo, else None."""
    trimmed = text.strip()
    if not trimmed or len(trimmed) > 200:
        return None

    tokens = _tokens(trimmed)
    if not tokens:
        return None

    matched = _match_show_me(tokens)
    if matched:
        return matched

    matched = _match_let_me_see(tokens)
    if matched:
        return matched

    matched = _match_look_like(tokens)
    if matched:
        return matched

    return None
