"""When a memory section needs rewriting, and whether a rewrite is acceptable.

Policy only — the LLM call and the DB write live in
background/memory_consolidation.py. Kept apart from the caching and locking
machinery so the rules can be read and tested on their own.
"""

import logging
import re

from app.services.memory.text import _split_sentences, normalize_memory_text

logger = logging.getLogger(__name__)

_CONSOLIDATION_ANCHOR_STOP = frozenset(
    {
        "user",
        "the",
        "and",
        "for",
        "with",
        "who",
        "that",
        "this",
        "their",
        "they",
        "prefers",
        "likes",
        "works",
        "name",
        "is",
        "are",
        "was",
        "has",
        "have",
    }
)


def section_needs_consolidation(text: str) -> bool:
    """True only for migration-style glue (duplicates), not normal long summaries."""
    clean = text.strip()
    if not clean:
        return False
    sentences = _split_sentences(clean)
    normalized = [normalize_memory_text(sentence).lower() for sentence in sentences]
    if len(normalized) != len(set(normalized)):
        return True
    prefixes = [" ".join(sentence.split()[:3]) for sentence in normalized if sentence]
    if len(prefixes) >= 2 and len(prefixes) != len(set(prefixes)):
        return True
    return len(clean) > 900 and len(sentences) >= 6


def sections_need_consolidation(sections: dict[str, str]) -> bool:
    return any(section_needs_consolidation(text) for text in sections.values())


def extract_consolidation_anchors(text: str) -> frozenset[str]:
    """Salient tokens from prior memory text that a rewrite should preserve."""
    anchors: set[str] = set()
    for match in re.finditer(r"[\w.+-]+@[\w-]+\.[\w.-]+", text):
        anchors.add(match.group(0).lower())
    for match in re.finditer(r"\b\d{2,}\b", text):
        anchors.add(match.group(0))
    for match in re.finditer(r'"([^"]{2,80})"', text):
        quoted = match.group(1).strip().lower()
        if quoted:
            anchors.add(quoted)
    for match in re.finditer(r"\b[A-Z][a-zA-Z0-9-]{2,}\b", text):
        token = match.group(0).lower()
        if token not in _CONSOLIDATION_ANCHOR_STOP:
            anchors.add(token)
    return frozenset(anchors)


def consolidation_rewrite_preserves_facts(
    prior: str,
    summary: str,
    *,
    min_preserved_ratio: float = 0.8,
) -> bool:
    """True when enough prior anchors appear in the rewritten summary.

    BUG FIX (off-by-one): the safety gate is meant to reject a merge that
    drops >= 20% of anchors (the default `min_preserved_ratio=0.8`). A `>=`
    comparison here accepted a merge that preserved exactly 80% — i.e.
    dropped exactly 20% — when the spec says that boundary should be
    rejected too. Strict `>` closes it.
    """
    anchors = extract_consolidation_anchors(prior)
    if len(anchors) < 2:
        return True
    haystack = summary.lower()
    preserved = sum(1 for anchor in anchors if anchor in haystack)
    return preserved / len(anchors) > min_preserved_ratio


def accept_memory_section_rewrite(
    *,
    section_type: str,
    prior: str,
    summary: str,
    confidence: float,
    min_confidence: float,
    enforce_length_floor: bool = True,
    allow_clear: bool = False,
) -> str | None:
    """Validate a whole-section rewrite before upsert (extraction + consolidation).

    Rejects low confidence, empty text, catastrophic shortening, and rewrites
    that drop too many prior fact anchors — so a flaky LLM pass cannot silently
    erase stable facts (name, employer, allergy, …). Explicit forget commands
    pass ``allow_clear`` so a requested wipe is not blocked by those guards.
    """
    if confidence < min_confidence:
        return None
    clean = normalize_memory_text(summary)
    if not clean:
        return "" if allow_clear else None
    if allow_clear:
        return clean
    # Exact-sentence dedupe can shrink well below 50%; only LLM merges use the floor.
    if enforce_length_floor and prior and len(clean) < len(prior) * 0.5:
        logger.warning(
            "Skipping memory rewrite for %s: new text much shorter than existing",
            section_type,
        )
        return None
    if prior and not consolidation_rewrite_preserves_facts(prior, clean):
        logger.warning(
            "Skipping memory rewrite for %s: rewrite dropped prior fact anchors",
            section_type,
        )
        return None
    # Identical text is still "accepted" so extraction can re-embed stale rows;
    # callers that only want real changes should compare against prior.
    return clean
