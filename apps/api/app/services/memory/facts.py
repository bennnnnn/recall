"""Atomic memory scoring and prompt packing — no IO."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models.memory_ops import (
    ACTIVE_STATUS as ACTIVE_STATUS,
)
from app.models.memory_ops import (
    MUTED_STATUS as MUTED_STATUS,
)
from app.models.memory_ops import (
    SUPERSEDED_STATUS as SUPERSEDED_STATUS,
)
from app.models.memory_ops import (
    evict_for_cap as evict_for_cap,
)
from app.models.memory_ops import (
    importance_value,
    normalize_memory_text,
    recency_score,
)
from app.models.memory_ops import (
    is_active_memory as is_active_memory,
)
from app.models.memory_ops import (
    match_fact as match_fact,
)
from app.models.memory_ops import (
    memory_status as memory_status,
)
from app.models.orm import Memory
from app.services.memory.text import (
    classify_memory_sensitivity,
    contains_phrase,
    is_sensitive_memory_text,
)

TYPE_PRIORITY = {"profile": 0, "preference": 1, "project": 2, "fact": 3, "focus": 4}
SECTION_LABELS = {
    "profile": "Profile",
    "preference": "Preferences",
    "project": "Projects",
    "fact": "Facts",
    "focus": "Focus",
}

_COMM_PREF_CUES = (
    "concise",
    "short answer",
    "brief",
    "example",
    "alternatives",
    "tone",
    "detailed",
    "direct",
    "english",
)
_IDENTITY_PROFILE_LIMIT = 3
_IDENTITY_PREF_LIMIT = 2


def fallback_score(memory: Any) -> float:
    type_prior = 1.0 - (TYPE_PRIORITY.get(getattr(memory, "type", ""), 9) * 0.05)
    return (importance_value(memory) * 0.55) + (recency_score(memory) * 0.3) + (type_prior * 0.15)


def semantic_score(memory: Any, cosine: float) -> float:
    type_prior = 1.0 - (TYPE_PRIORITY.get(getattr(memory, "type", ""), 9) * 0.05)
    return (
        (cosine * 0.55)
        + (importance_value(memory) * 0.25)
        + (recency_score(memory) * 0.15)
        + (type_prior * 0.05)
    )


def is_communication_preference(memory: Any) -> bool:
    if getattr(memory, "type", "") != "preference":
        return False
    text = normalize_memory_text(getattr(memory, "text", "")).lower()
    return any(contains_phrase(text, cue) for cue in _COMM_PREF_CUES)


def identity_core(memories: list[Memory]) -> list[Memory]:
    profiles = [m for m in memories if m.type == "profile"]
    profiles.sort(key=lambda m: (importance_value(m), recency_score(m)), reverse=True)
    prefs = [m for m in memories if is_communication_preference(m)]
    if not prefs:
        prefs = [m for m in memories if m.type == "preference"]
    prefs.sort(key=lambda m: (importance_value(m), recency_score(m)), reverse=True)
    core: list[Memory] = []
    seen: set[int] = set()
    for memory in (*profiles[:_IDENTITY_PROFILE_LIMIT], *prefs[:_IDENTITY_PREF_LIMIT]):
        key = id(memory)
        if key in seen:
            continue
        core.append(memory)
        seen.add(key)
    return core


def should_skip_sensitive_persist(
    *,
    sensitivity: str,
    text: str,
    explicit_remember: bool,
    include_sensitive: bool,
) -> bool:
    classified = sensitivity or classify_memory_sensitivity(text)
    if include_sensitive or explicit_remember:
        return False
    if classified != "normal":
        return True
    return is_sensitive_memory_text(text)


def render_memory_block(memories: list[Any]) -> str:
    if not memories:
        return ""
    ordered = sorted(memories, key=lambda m: TYPE_PRIORITY.get(m.type, 99))
    lines = ["Known facts about the user:"]
    current_type: str | None = None
    for memory in ordered:
        if memory.type != current_type:
            label = SECTION_LABELS.get(memory.type, str(memory.type).title())
            lines.append(f"\n## {label}")
            current_type = memory.type
        lines.append(f"- {str(memory.text).strip()}")
    return "\n".join(lines)


def pack_memories(memories: list[Any], *, max_chars: int) -> list[Any]:
    if max_chars <= 0:
        return list(memories)
    packed: list[Any] = []
    for memory in memories:
        trial = [*packed, memory]
        if len(render_memory_block(trial)) > max_chars:
            continue
        packed.append(memory)
    return packed


def expected_facts_from_rows(facts: list[Memory]) -> dict[UUID, str]:
    return {fact.id: fact.text for fact in facts}
