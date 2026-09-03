"""Pure text helpers for memory sections — no IO, no state.

Used by the consolidation policy, the CRUD paths, home surfaces and the
background extractor. None of them touch Redis, the DB or settings, so callers
can depend on the text rules without pulling in the caching/locking machinery.
"""

import hashlib
import re
from datetime import UTC, date, datetime

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
