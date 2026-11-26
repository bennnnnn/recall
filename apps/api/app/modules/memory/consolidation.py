"""When a memory section needs rewriting, and whether a rewrite is acceptable.

Policy only — the LLM call and the DB write live in
consolidation_workflow.py. Kept apart from the caching and locking
machinery so the rules can be read and tested on their own.
"""

import logging
import re
from collections.abc import Callable, Iterable
from typing import Any, TypeVar

from app.modules.memory.fact_quality import FactView, is_learning_line, texts_to_drop
from app.modules.memory.ops import normalize_memory_text
from app.modules.memory.text import merge_diet_facts

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


# Two facts of one type whose words overlap this much say one thing.
NEAR_DUP_JACCARD = 0.8

_Fact = TypeVar("_Fact")


def fact_tokens(text: str) -> frozenset[str]:
    """The words two facts are compared by (``tokens_jaccard``)."""
    return frozenset(part for part in normalize_memory_text(text).lower().split() if part)


def tokens_jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    shared = len(a & b)
    return shared / (len(a) + len(b) - shared)


def _active(memory: Any) -> bool:
    return str(getattr(memory, "status", None) or "active") == "active"


def _mergeable(memory: Any) -> bool:
    """An active fact with words; a lesson chat's progress line is the lesson job's, never
    merged: two courses are never one line."""
    text = getattr(memory, "text", "")
    return _active(memory) and bool(normalize_memory_text(text)) and not is_learning_line(text)


def duplicate_pairs(
    facts: Iterable[_Fact], *, newest: Callable[[_Fact], Any] | None = None
) -> list[tuple[_Fact, _Fact]]:
    """Each (kept, dropped) pair of duplicate facts: the same type and text, then a type's
    facts whose words are ``NEAR_DUP_JACCARD`` alike. ``newest`` orders each choice, the
    newest kept; without it the facts' own order does.

    The one rule: the job merges these pairs and the check that queues the job asks whether
    there are any. Written twice, the check counted lesson lines the job leaves alone, so a
    user with two courses queued a job every 300 s that merged nothing (audit, 2026-11-25).
    """
    active = [fact for fact in facts if _mergeable(fact)]
    by_key: dict[tuple[str, str], list[_Fact]] = {}
    for fact in active:
        text = normalize_memory_text(getattr(fact, "text", "")).lower()
        by_key.setdefault((str(getattr(fact, "type", "")), text), []).append(fact)
    pairs: list[tuple[_Fact, _Fact]] = []
    used: set[int] = set()
    for group in by_key.values():
        if len(group) < 2:
            continue
        if newest is not None:
            group.sort(key=newest, reverse=True)
        used.update(id(fact) for fact in group)
        pairs += [(group[0], extra) for extra in group[1:]]
    remaining = [fact for fact in active if id(fact) not in used]
    if newest is not None:
        remaining.sort(key=newest, reverse=True)
    claimed: set[int] = set()
    # Each fact's words once, not again for every pair (CX-5).
    tokens = [fact_tokens(getattr(fact, "text", "")) for fact in remaining]
    for index, left in enumerate(remaining):
        if id(left) in claimed:
            continue
        for offset, right in enumerate(remaining[index + 1 :], index + 1):
            if id(right) in claimed or getattr(right, "type", "") != getattr(left, "type", ""):
                continue
            if tokens_jaccard(tokens[index], tokens[offset]) < NEAR_DUP_JACCARD:
                continue
            claimed.add(id(right))
            pairs.append((left, right))
    return pairs


def facts_need_consolidation(memories: Iterable[Any]) -> bool:
    """True when two active facts are duplicates (``duplicate_pairs``), or one should be
    dropped."""
    memory_list = list(memories)
    active_views = [
        FactView(text=normalize_memory_text(getattr(memory, "text", "")))
        for memory in memory_list
        if _active(memory) and normalize_memory_text(getattr(memory, "text", ""))
    ]
    return bool(texts_to_drop(active_views)) or bool(duplicate_pairs(memory_list))


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

    The gate rejects a merge that drops 20% of the anchors or more (the default
    ``min_preserved_ratio=0.8``): keeping exactly 80% is a rejection too, hence the
    strict ``>``.
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
    pass ``allow_clear`` only so an empty summary can wipe that section; nonempty
    rewrites still go through the shortening and anchor checks.
    """
    if confidence < min_confidence:
        return None
    clean = normalize_memory_text(summary)
    if not clean:
        return "" if allow_clear else None
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
    if prior and not allow_clear:
        clean = merge_diet_facts(prior, clean)
    return clean
