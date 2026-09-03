"""Pure text helpers for memory sections — no IO, no state.

Used by the consolidation policy, the CRUD paths, home surfaces and the
background extractor. None of them touch Redis, the DB or settings, so callers
can depend on the text rules without pulling in the caching/locking machinery.
"""

import hashlib
import re
from datetime import UTC, date, datetime

from app.services.prompt_safety import strip_untrusted_blocks, text_before_attachment_markers

_AS_OF_PREFIX_RE = re.compile(r"^As of \d{4}-\d{2}-\d{2}:\s*", re.IGNORECASE)


_SENSITIVE_MEMORY_RE = re.compile(
    r"\b("
    r"allerg(?:y|ies|ic)|diagnos(?:is|ed)|cancer|depress(?:ion|ed)|anxi(?:ety|ous)|"
    r"therapist|psychiatr|medication|prescri(?:be|ption)|pregnant|hiv\b|diabetes|"
    r"lawsuit|attorney|\blawyer\b|divorc(?:e|ing)|"
    r"salary|mortgage|credit\s*card|bank\s*account|\bdebt\b|"
    r"boyfriend|girlfriend|husband|wife|spouse|affair|\bdating\b"
    r")\b",
    re.IGNORECASE,
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
    "stop remembering",
    "don't remember",
    "do not remember",
    "i changed jobs",
    "i changed my job",
    "i switched jobs",
    "i switched my job",
    "i got a new job",
    "i moved to",
    "i no longer work",
    "i don't work at",
    "i do not work at",
)


def is_explicit_memory_command(text: str) -> bool:
    """True when the user asked to remember or forget a fact in this turn."""
    lowered = (text or "").lower()
    if not lowered:
        return False
    return any(marker in lowered for marker in _MEMORY_COMMAND_MARKERS)


def normalize_memory_text(text: str) -> str:
    clean = re.sub(r"\s+", " ", text.strip()).rstrip(".")
    return clean


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
    """True when text looks like health/legal/finance/relationship content."""
    return bool(_SENSITIVE_MEMORY_RE.search(strip_memory_as_of(text)))


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
    r"allerg(?:y|ies|ic)|peanut|gluten|vegan|vegetarian"
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


# Tiny words that should not make two unrelated facts look related.
_FACT_TOKEN_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "you",
        "your",
        "that",
        "this",
        "with",
        "what",
        "should",
        "about",
        "have",
        "from",
        "are",
        "was",
        "can",
        "how",
        "does",
        "did",
        "not",
        "but",
        "they",
        "them",
        "his",
        "her",
        "its",
        "our",
        "who",
        "why",
        "when",
        "will",
        "just",
        "been",
        "had",
        "user",
        "likes",
        "like",
        "also",
        "very",
        "into",
        "onto",
    }
)


def memory_fact_tokens(text: str) -> set[str]:
    """Lowercase tokens of length ≥3, scanned linearly (no regex)."""
    tokens: set[str] = set()
    buf: list[str] = []
    for ch in (text or "").lower():
        if ch.isalnum():
            buf.append(ch)
            continue
        if len(buf) >= 3:
            word = "".join(buf)
            if word not in _FACT_TOKEN_STOP:
                tokens.add(word)
        buf = []
    if len(buf) >= 3:
        word = "".join(buf)
        if word not in _FACT_TOKEN_STOP:
            tokens.add(word)
    return tokens


def fact_query_overlap(fact: str, query: str) -> int:
    """Count of shared content tokens between a stored fact and the user ask."""
    if not fact or not query:
        return 0
    return len(memory_fact_tokens(fact) & memory_fact_tokens(query))


def memory_fact_matches_query(fact: str, query: str) -> bool:
    """True when this fact is about the current ask (tokens or food/diet)."""
    cleaned = (query or "").strip()
    if not cleaned:
        return True
    if fact_query_overlap(fact, cleaned) > 0:
        return True
    return is_food_or_diet_query(cleaned) and (
        is_diet_health_memory_text(fact) or is_food_or_diet_query(fact)
    )


def drop_sensitive_memory_facts(text: str) -> str:
    """Keep only non-sensitive sentences. Empty if nothing remains."""
    body = strip_memory_as_of(text)
    if not body:
        return ""
    kept = [fact for fact in split_memory_facts(body) if not is_sensitive_memory_text(fact)]
    return join_memory_facts(kept)


_NAME_FACT_MARKERS = ("name is", "named ", "user's name")
_AGE_FACT_MARKERS = (" years old", "age is")
_JOB_FACT_MARKERS = ("works at", "works as", "job is", "employed at")
_PLACE_FACT_MARKERS = ("lives in", "based in", "located in", "country is")


def _fact_has_marker(fact: str, markers: tuple[str, ...]) -> bool:
    lowered = fact.lower()
    return any(marker in lowered for marker in markers)


def drop_duplicate_account_profile_facts(
    text: str,
    *,
    name: str | None,
    age: int | None,
    country: str | None,
    job: str | None,
    location: str | None,
) -> str:
    """Drop identity sentences the structured account profile already owns.

    Account name/age/job/country/location are injected separately. Leaving the
    same claims in the memory profile lets a stale job survive a Settings edit.
    """
    body = strip_memory_as_of(text)
    if not body:
        return ""
    drop_name = bool((name or "").strip())
    drop_age = age is not None
    drop_job = bool((job or "").strip())
    drop_place = bool((country or "").strip()) or bool((location or "").strip())
    kept: list[str] = []
    for fact in split_memory_facts(body):
        if drop_name and _fact_has_marker(fact, _NAME_FACT_MARKERS):
            continue
        if drop_age and _fact_has_marker(fact, _AGE_FACT_MARKERS):
            continue
        if drop_job and _fact_has_marker(fact, _JOB_FACT_MARKERS):
            continue
        if drop_place and _fact_has_marker(fact, _PLACE_FACT_MARKERS):
            continue
        kept.append(fact)
    return join_memory_facts(kept)
