"""Which memories go into a prompt, in what order, and how they're rendered.

Pure ranking and formatting — no Redis, no DB, no awaits. The stateful core
(`app/services/memory/__init__.py`) imports these into its own namespace and
calls them there, so tests patching `app.services.memory.format_memory_block`
and friends still intercept the internal calls.
"""

from app.core.config import Settings
from app.models.orm import Memory

TYPE_PRIORITY = {"profile": 0, "preference": 1, "project": 2, "fact": 3, "focus": 4}
SECTION_LABELS = {
    "profile": "Profile",
    "preference": "Preferences",
    "project": "Projects",
    "fact": "Facts",
    "focus": "Focus",
}
# Always useful identity/style context — never gated by query similarity.
_ALWAYS_INJECT_TYPES = frozenset({"profile", "preference"})
# Topic-sensitive sections — only inject when cosine similarity clears the bar.
_SIMILARITY_GATED_TYPES = frozenset({"project", "fact", "focus"})

# Surfaces (home chips / suggestion prompts) must never echo these topics.


def _confidence_value(memory: Memory) -> float:
    if memory.confidence is None:
        return 1.0
    return float(memory.confidence)


def _eligible_memory(memory: Memory, settings: Settings) -> bool:
    return _confidence_value(memory) >= settings.memory_min_confidence and bool(memory.text.strip())


def select_memories_for_prompt(
    memories: list[Memory],
    settings: Settings,
    *,
    omit_project_memory: bool = False,
) -> list[Memory]:
    """Non-semantic fallback: profile/preference only (no off-topic dump)."""
    filtered = [
        memory
        for memory in memories
        if _eligible_memory(memory, settings) and memory.type in _ALWAYS_INJECT_TYPES
    ]
    if omit_project_memory:
        filtered = [memory for memory in filtered if memory.type != "project"]
    filtered.sort(key=lambda m: (TYPE_PRIORITY.get(m.type, 99), -_confidence_value(m)))
    type_cap = min(settings.memory_inject_limit, len(TYPE_PRIORITY))
    return filtered[:type_cap]


def format_memory_block(memories: list, *, max_chars: int = 0) -> str:
    if not memories:
        return ""
    ordered = sorted(memories, key=lambda m: TYPE_PRIORITY.get(m.type, 99))
    lines = ["Known facts about the user:"]
    for memory in ordered:
        label = SECTION_LABELS.get(memory.type, memory.type.title())
        lines.append(f"\n## {label}\n{memory.text.strip()}")
    block = "\n".join(lines)
    if max_chars > 0 and len(block) > max_chars:
        cut = max(1, max_chars - 1)
        return f"{block[:cut].rstrip()}…"
    return block


def select_memories_semantic(
    memories: list[Memory],
    query_embedding: list[float],
    settings: Settings,
    *,
    omit_project_memory: bool = False,
) -> list[Memory]:
    """profile/preference always; fact/focus/project only above similarity."""
    from app.gateways.embedding_gateway import cosine_similarity, parse_embedding

    always: list[Memory] = []
    scored: list[tuple[float, Memory]] = []
    for memory in memories:
        if not _eligible_memory(memory, settings):
            continue
        if omit_project_memory and memory.type == "project":
            continue
        if memory.type in _ALWAYS_INJECT_TYPES:
            always.append(memory)
            continue
        if memory.type not in _SIMILARITY_GATED_TYPES:
            continue
        vec = parse_embedding(getattr(memory, "embedding_json", None))
        if vec is None:
            continue
        score = cosine_similarity(query_embedding, vec)
        min_sim = settings.memory_min_similarity
        if min_sim > 0 and score < min_sim:
            continue
        scored.append((score, memory))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    always.sort(key=lambda m: (TYPE_PRIORITY.get(m.type, 99), -_confidence_value(m)))
    gated = [memory for _, memory in scored]
    merged = always + gated
    type_cap = min(settings.memory_inject_limit, len(TYPE_PRIORITY))
    return merged[:type_cap]
