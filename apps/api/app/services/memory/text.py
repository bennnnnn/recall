"""Pure text helpers for memory sections — no IO, no state.

Used by the consolidation policy, the CRUD paths, home surfaces and the
background extractor. None of them touch Redis, the DB or settings, so callers
can depend on the text rules without pulling in the caching/locking machinery.
"""

import hashlib
import re
from datetime import UTC, date, datetime

from app.models.memory_ops import normalize_memory_text as normalize_memory_text
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
    "dating",
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
_CANDIDATE_CUES = (
    "i am",
    "i'm",
    "i've",
    "i work",
    "i live",
    "i prefer",
    "i like",
    "i hate",
    "i love",
    "i moved",
    "i use",
    "i drink",
    "i own",
    "i study",
    "i recently",
    "my name",
    "my dog",
    "my cat",
    "my favorite",
    "my favourite",
    "i'm trying",
    "i'm learning",
    "i have a",
    "we moved",
    "we live",
    "we are",
    "call me",
    "moved to",
    "go by",
)


def memory_extract_user_text(content: str) -> str:
    """User prose only — drop attachment OCR/excerpts so they cannot become memories."""
    return text_before_attachment_markers(strip_untrusted_blocks(content or "")).strip()


# Explicit remember/forget — scanned as literals, not a regex (CodeQL ReDoS).
_MEMORY_COMMAND_MARKERS = (
    "remember this",
    "remember that",
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


def is_explicit_memory_command(text: str) -> bool:
    """True when the user asked to remember or forget a fact in this turn."""
    lowered = (text or "").lower()
    if not lowered:
        return False
    return any(marker in lowered for marker in _MEMORY_COMMAND_MARKERS)


def is_explicit_forget_command(text: str) -> bool:
    """True when the user asked to drop a stored fact, not to remember one."""
    lowered = (text or "").lower().replace("\u2019", "'").replace("\u2018", "'")
    if not lowered:
        return False
    for marker in _FORGET_MARKERS:
        start = 0
        while True:
            index = lowered.find(marker, start)
            if index < 0:
                break
            if not _forget_marker_is_negated(lowered, index):
                return True
            start = index + 1
    return False


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


def is_highly_sensitive_text(text: str) -> bool:
    return classify_memory_sensitivity(text) == "highly_sensitive"


def is_memory_candidate(text: str) -> bool:
    """Cheap gate: skip the memory model when the user line has no self-claim."""
    if is_explicit_memory_command(text):
        return True
    lowered = (text or "").lower().replace("\u2019", "'").replace("\u2018", "'")
    if not lowered:
        return False
    return any(contains_phrase(lowered, cue) for cue in _CANDIDATE_CUES)


def merge_explicit_remember_fact(prior: str, incoming: str) -> str:
    """Keep prior section text and add an explicit-remember fact the LLM omitted.

    Whole-section rewrites of a long preference/profile often shrink below the
    50% length floor (or drop unrelated anchors). Explicit "remember that …"
    still has to land, so merge instead of dropping the new fact.
    """
    return join_memory_facts([strip_memory_as_of(prior), incoming])


def _forget_marker_is_negated(lowered: str, index: int) -> bool:
    before = lowered[:index]
    return before.endswith("don't ") or before.endswith("do not ") or before.endswith("dont ")


def strip_memory_as_of(text: str) -> str:
    """Remove a leading ``As of YYYY-MM-DD:`` stamp if present."""
    return _AS_OF_PREFIX_RE.sub("", text.strip()).strip()


def stamp_memory_as_of(text: str, *, as_of: date | None = None) -> str:
    """Prefix section text with today's (or provided) as-of date for freshness."""
    body = strip_memory_as_of(text)
    if not body:
        return body
    day = as_of or datetime.now(UTC).date()
    return f"As of {day.isoformat()}: {body}"


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
