"""Pure text helpers for memory sections — no IO, no state.

Used by the consolidation policy, the CRUD paths, home surfaces and the
background extractor. None of them touch Redis, the DB or settings, so callers
can depend on the text rules without pulling in the caching/locking machinery.
"""

import hashlib
import re

from app.modules.memory.ops import normalize_memory_text as normalize_memory_text
from app.services.prompt_safety import strip_untrusted_blocks, text_before_attachment_markers

_AS_OF_PREFIX_RE = re.compile(r"^As of \d{4}-\d{2}-\d{2}:\s*", re.IGNORECASE)


def contains_phrase(haystack: str, needle: str) -> bool:
    """True when ``needle`` appears with alphanumeric boundaries (CodeQL-safe)."""
    if not haystack or not needle:
        return False
    h = haystack.lower()
    n = needle.lower()
    start = 0
    while True:
        index = h.find(n, start)
        if index < 0:
            return False
        before_ok = index == 0 or not h[index - 1].isalnum()
        after = index + len(n)
        after_ok = after >= len(h) or not h[after].isalnum()
        if before_ok and after_ok:
            return True
        start = index + 1


_HEALTH_NEEDLES = (
    "allergy",
    "allergies",
    "allergic",
    "diagnosis",
    "diagnosed",
    "cancer",
    "depression",
    "depressed",
    "anxiety",
    "anxious",
    "therapist",
    "psychiatrist",
    "psychiatric",
    "medication",
    "prescribe",
    "prescription",
    "pregnant",
    "hiv",
    "diabetes",
)
_LEGAL_NEEDLES = ("lawsuit", "attorney", "lawyer", "divorce", "divorcing")
_FINANCE_NEEDLES = (
    "salary",
    "mortgage",
    "credit card",
    "bank account",
    "debt",
)
_RELATIONSHIP_NEEDLES = (
    "boyfriend",
    "girlfriend",
    "husband",
    "wife",
    "spouse",
    "affair",
    # The user's own dating life, not a dating app they build or use for work.
    "is dating",
    "am dating",
    "are dating",
    "been dating",
    "started dating",
    "dating someone",
    "went on a date",
)
_HIGHLY_SENSITIVE_NEEDLES = (
    "ethnicity",
    "ethnic origin",
    "religion",
    "muslim",
    "jewish",
    "christianity",
    "christian",
    "catholic",
    "hindu",
    "buddhist",
    "political party",
    "sexual orientation",
    "homosexual",
    "gay",
    "lesbian",
    "bisexual",
    "transgender",
    "sex life",
)
_NON_MEMORY_SMALL_TALK = frozenset(
    {
        "hi",
        "hello",
        "hey",
        "hey there",
        "hello there",
        "hiya",
        "yo",
        "sup",
        "thanks",
        "thank you",
        "thx",
        "ty",
        "ok",
        "okay",
        "k",
        "cool",
        "nice",
        "great",
        "perfect",
        "awesome",
        "got it",
        "sounds good",
        "makes sense",
        "understood",
        "yes",
        "no",
        "yep",
        "nope",
        "sure",
        "bye",
        "goodbye",
        "cya",
        "see ya",
        "lol",
        "lmao",
        "haha",
        "hehe",
        "go",
        "do it",
        "please",
        "proceed",
    }
)


def memory_extract_user_text(content: str) -> str:
    """User prose only — drop attachment OCR/excerpts so they cannot become memories."""
    return text_before_attachment_markers(strip_untrusted_blocks(content or "")).strip()


# Explicit remember/forget — scanned as literals, not a regex (CodeQL ReDoS).
_MEMORY_COMMAND_MARKERS = (
    "remember this",
    "remember that",
    "remember i'm",
    "remember im ",
    "remember i ",
    "remember my ",
    "keep in mind",
    "please remember",
    "don't forget",
    "do not forget",
    "forget that",
    "forget this",
    "forget i ",
    "forget i'",
    "forget my ",
    "forget about",
    "stop remembering",
    "don't remember",
    "do not remember",
)

_FORGET_MARKERS = (
    "forget that",
    "forget this",
    "forget i ",
    "forget i'",
    "forget my ",
    "forget about",
    "stop remembering",
    "don't remember",
    "do not remember",
)


_REMEMBER_MARKERS = frozenset(
    {
        "remember this",
        "remember that",
        "remember i'm",
        "remember im ",
        "remember i ",
        "remember my ",
    }
)
# Words that may come before an instruction in the same clause: "oh and",
# "please", "can you". Anything else makes it a statement or a question about
# remembering: "I always forget my keys", "do you remember that song?".
_CONNECTIVES = frozenset(
    {"and", "but", "also", "so", "now", "ok", "okay", "oh", "hey", "actually", "wait"}
)
_POLITE_LEADS: tuple[tuple[str, ...], ...] = (
    ("please",),
    ("pls",),
    ("can", "you"),
    ("could", "you"),
    ("would", "you"),
    ("will", "you"),
    ("i", "want", "you", "to"),
    ("i", "need", "you", "to"),
    ("i'd", "like", "you", "to"),
    ("make", "sure", "to"),
    ("make", "sure", "you"),
    ("go", "ahead", "and"),
    ("for", "future", "chats"),
    ("for", "future", "reference"),
    ("going", "forward"),
    ("from", "now", "on"),
)
_CLAUSE_BREAKS = ".!?;:,\n\u2014\u2013"
# "Forget about the previous question" drops a turn, not a saved fact.
_CHAT_PARTS = frozenset(
    {
        "question",
        "questions",
        "request",
        "prompt",
        "problem",
        "answer",
        "reply",
        "message",
        "part",
        "chat",
        "conversation",
        "topic",
    }
)
_CHAT_PART_LEADS = frozenset(
    {
        "the",
        "my",
        "your",
        "that",
        "this",
        "previous",
        "last",
        "earlier",
        "above",
        "first",
        "other",
        "whole",
    }
)


def is_explicit_memory_command(text: str) -> bool:
    """True when the user asked to remember or forget a fact in this turn."""
    lowered = _fold_quotes(text)
    if not lowered:
        return False
    return any(
        _is_command_at(lowered, marker, index)
        for marker in _MEMORY_COMMAND_MARKERS
        for index in _marker_positions(lowered, marker)
    )


def _fold_quotes(text: str | None) -> str:
    return (text or "").lower().replace("\u2019", "'").replace("\u2018", "'")


def _marker_positions(lowered: str, marker: str) -> list[int]:
    positions: list[int] = []
    start = 0
    while (index := lowered.find(marker, start)) >= 0:
        if index == 0 or not lowered[index - 1].isalnum():
            positions.append(index)
        start = index + 1
    return positions


def _is_command_at(lowered: str, marker: str, index: int) -> bool:
    """The marker starts its clause, after nothing but "please", "can you" or "and"."""
    before = lowered[:index]
    cut = max(before.rfind(mark) for mark in _CLAUSE_BREAKS)
    clause = before[cut + 1 :].split()
    led = False
    while clause:
        if clause[0] in _CONNECTIVES:
            clause = clause[1:]
            continue
        lead = next((lead for lead in _POLITE_LEADS if tuple(clause[: len(lead)]) == lead), None)
        if lead is None:
            break
        clause = clause[len(lead) :]
        led = True
    if clause:
        return False
    after = lowered[index + len(marker) :].split()
    if marker.startswith("forget") and _names_a_chat_part(after):
        return False
    # "Remember that song from Titanic?" asks; "can you remember that …?" tells.
    return not (marker in _REMEMBER_MARKERS and not led and lowered.rstrip().endswith("?"))


def _names_a_chat_part(words: list[str]) -> bool:
    head = [word.strip(".,!?;:") for word in words[:3]]
    while head and head[0] in _CHAT_PART_LEADS:
        head = head[1:]
    return bool(head) and head[0] in _CHAT_PARTS


_FORGET_WORD_MIN_CHARS = 5
_FORGET_WORD_SKIP = frozenset({"please", "about", "really"})


def forget_content_words(text: str) -> list[str]:
    """Words the user named in a forget command, not the command itself.

    Words shorter than five letters are dropped so "forget that" cannot match
    every stored fact.
    """
    lowered = (text or "").lower().replace("\u2019", "'").replace("\u2018", "'")
    for marker in sorted(_FORGET_MARKERS, key=len, reverse=True):
        lowered = lowered.replace(marker, " ")
    seen: list[str] = []
    for word in re.findall(r"[a-z0-9]+", lowered.replace("'", "")):
        if len(word) < _FORGET_WORD_MIN_CHARS or word in _FORGET_WORD_SKIP or word in seen:
            continue
        seen.append(word)
    return seen


def is_explicit_forget_command(text: str) -> bool:
    """True when the user asked to drop a stored fact, not to remember one."""
    lowered = _fold_quotes(text)
    if not lowered:
        return False
    return any(
        not _forget_marker_is_negated(lowered, index) and _is_command_at(lowered, marker, index)
        for marker in _FORGET_MARKERS
        for index in _marker_positions(lowered, marker)
    )


def classify_memory_sensitivity(text: str) -> str:
    haystack = strip_memory_as_of(text).lower()
    if any(contains_phrase(haystack, needle) for needle in _HIGHLY_SENSITIVE_NEEDLES):
        return "highly_sensitive"
    if any(contains_phrase(haystack, needle) for needle in _HEALTH_NEEDLES):
        return "health"
    if any(contains_phrase(haystack, needle) for needle in _LEGAL_NEEDLES):
        return "legal"
    if any(contains_phrase(haystack, needle) for needle in _FINANCE_NEEDLES):
        return "finance"
    if any(contains_phrase(haystack, needle) for needle in _RELATIONSHIP_NEEDLES):
        return "relationship"
    return "normal"


def is_memory_candidate(text: str) -> bool:
    """Run extraction for every substantive user line.

    The memory model is the authority on whether a line contains a durable
    fact.  A narrow English phrase allowlist used here previously discarded
    ordinary statements such as "As a software engineer at Uber..." and
    "Please keep replies concise" before the model ever saw them.  This gate
    now rejects only unmistakable acknowledgements and small talk.

    Role-prefixed transcripts may contain assistant lines in legacy tests or
    callers.  Those lines are never evidence about the user and are ignored.
    """
    if is_explicit_memory_command(text):
        return True
    saw_user_role = False
    candidates: list[str] = []
    for raw_line in (text or "").splitlines() or [text or ""]:
        line = raw_line.strip()
        lowered = line.lower()
        if lowered.startswith("assistant:"):
            continue
        if lowered.startswith("user:"):
            saw_user_role = True
            line = line.split(":", 1)[1].strip()
        elif saw_user_role and not line:
            continue
        if line:
            candidates.append(line)

    for line in candidates:
        normalized = re.sub(r"[^\w'\s]+", " ", line.casefold())
        normalized = " ".join(normalized.split())
        if not normalized:
            continue
        if normalized in _NON_MEMORY_SMALL_TALK:
            continue
        if len(normalized) <= 2 and normalized.isalpha():
            continue
        return True
    return False


def _forget_marker_is_negated(lowered: str, index: int) -> bool:
    before = lowered[:index]
    return before.endswith("don't ") or before.endswith("do not ") or before.endswith("dont ")


def strip_memory_as_of(text: str) -> str:
    """Remove a leading ``As of YYYY-MM-DD:`` stamp if present."""
    return _AS_OF_PREFIX_RE.sub("", text.strip()).strip()


def is_sensitive_memory_text(text: str) -> bool:
    """True when text looks like health/legal/finance/relationship/highly-sensitive content."""
    return classify_memory_sensitivity(text) != "normal"


_DIET_HEALTH_MEMORY_RE = re.compile(
    r"\b("
    r"allerg(?:y|ies|ic)|peanut|gluten|vegan|vegetarian|kosher|halal|"
    r"lactose|shellfish|nut-free|diabetes|intoleran"
    r")\b",
    re.IGNORECASE,
)
_FOOD_QUERY_RE = re.compile(
    r"\b("
    r"eat|eating|eaten|ate|cook|cooking|dinner|lunch|breakfast|brunch|"
    r"food|restaurant|recipe|meal|hungry|starving|snack|diet|"
    r"allerg(?:y|ies|ic)|peanut|gluten|vegan|vegetarian|"
    r"milk|drink|drinks|drank|coffee|tea|latte|oat|"
    r"consume|consumes|consumed"
    r")\b",
    re.IGNORECASE,
)


def is_diet_health_memory_text(text: str) -> bool:
    """Allergy / diet constraints that food advice should still see."""
    return bool(_DIET_HEALTH_MEMORY_RE.search(strip_memory_as_of(text)))


def is_food_or_diet_query(text: str) -> bool:
    """True when the ask is about eating, cooking, or diet."""
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    return bool(_FOOD_QUERY_RE.search(cleaned))


def is_food_or_diet_memory_text(text: str) -> bool:
    """True when stored memory mentions food, drink, or diet."""
    return bool(_FOOD_QUERY_RE.search(strip_memory_as_of(text)))


def exclude_sensitive_for_query(query_text: str | None) -> bool:
    """Omit health/legal/finance memories unless this ask is about those topics."""
    text = (query_text or "").strip()
    if not text:
        return True
    return not is_sensitive_memory_text(text)


def embedding_text_hash(text: str) -> str:
    """Hash of the exact text an embedding was computed from — stored
    alongside the vector so a later pass can tell "stale" from "current"
    without needing the specific prior-snapshot text that triggered this
    particular embed call. See migration 0057 and its BUG FIX docstring."""
    return hashlib.sha256(text.encode()).hexdigest()


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def split_memory_facts(text: str) -> list[str]:
    return _split_sentences(text)


def join_memory_facts(facts: list[str]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for raw in facts:
        clean = normalize_memory_text(raw)
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        parts.append(clean)
    merged = ". ".join(parts)
    if merged and not merged.endswith("."):
        merged += "."
    return merged


def merge_diet_facts(prior: str, incoming: str) -> str:
    """Keep diet/drink sentences a later section rewrite omitted."""
    incoming_body = strip_memory_as_of(incoming)
    haystack = incoming_body.lower()
    omitted: list[str] = []
    for fact in split_memory_facts(prior):
        if not is_food_or_diet_memory_text(fact):
            continue
        needle = normalize_memory_text(strip_memory_as_of(fact)).lower()
        if needle and needle not in haystack:
            omitted.append(strip_memory_as_of(fact))
    if not omitted:
        return incoming
    return join_memory_facts([incoming_body, *omitted])
