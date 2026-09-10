"""Which memories go into a prompt, in what order, and how they're rendered.

Pure ranking and formatting — no Redis, no DB, no awaits. The stateful core
(`app/services/memory/__init__.py`) imports these into its own namespace and
calls them there, so tests patching `app.services.memory.format_memory_block`
and friends still intercept the internal calls.
"""

from app.core.config import Settings
from app.models.orm import Memory
from app.services.memory.facts import (
    SECTION_LABELS as SECTION_LABELS,
)
from app.services.memory.facts import (
    TYPE_PRIORITY as TYPE_PRIORITY,
)
from app.services.memory.facts import (
    fallback_score,
    identity_core,
    is_active_memory,
    pack_memories,
    render_memory_block,
    semantic_score,
)
from app.services.memory.text import is_food_or_diet_memory_text, is_food_or_diet_query

# Always useful identity/style context — a tiny core, not every profile/preference row.
_ALWAYS_INJECT_TYPES = frozenset({"profile", "preference"})
# Topic-sensitive sections — only inject when cosine similarity clears the bar.
_SIMILARITY_GATED_TYPES = frozenset({"project", "fact", "focus"})


def _confidence_value(memory: Memory) -> float:
    if memory.confidence is None:
        return 1.0
    return float(memory.confidence)


def _eligible_memory(memory: Memory, settings: Settings) -> bool:
    if not is_active_memory(memory):
        return False
    return _confidence_value(memory) >= settings.memory_min_confidence and bool(memory.text.strip())


def select_memories_for_prompt(
    memories: list[Memory],
    settings: Settings,
    *,
    omit_project_memory: bool = False,
) -> list[Memory]:
    """Non-semantic fallback: identity core + scored remaining facts."""
    filtered = [memory for memory in memories if _eligible_memory(memory, settings)]
    if omit_project_memory:
        filtered = [memory for memory in filtered if memory.type != "project"]
    core = identity_core(filtered)
    core_ids = {id(memory) for memory in core}
    rest = [memory for memory in filtered if id(memory) not in core_ids]
    rest.sort(key=fallback_score, reverse=True)
    return [*core, *rest][: settings.memory_inject_limit]


def format_memory_block(memories: list, *, max_chars: int = 0) -> str:
    packed = pack_memories(memories, max_chars=max_chars)
    return render_memory_block(packed)


def select_memories_semantic(
    memories: list[Memory],
    query_embedding: list[float],
    settings: Settings,
    *,
    omit_project_memory: bool = False,
    query_text: str | None = None,
) -> list[Memory]:
    """Identity core always; remaining facts only above similarity.

    Food/drink asks also keep diet facts whose embedding would otherwise miss.
    """
    from app.gateways.embedding_gateway import cosine_similarity, parse_embedding

    eligible = [memory for memory in memories if _eligible_memory(memory, settings)]
    if omit_project_memory:
        eligible = [memory for memory in eligible if memory.type != "project"]
    always = identity_core(eligible)
    always_ids = {id(memory) for memory in always}
    scored: list[tuple[float, Memory]] = []
    min_sim = settings.memory_min_similarity
    for memory in eligible:
        if id(memory) in always_ids:
            continue
        vec = parse_embedding(getattr(memory, "embedding_json", None))
        if vec is None:
            continue
        cosine = cosine_similarity(query_embedding, vec)
        if min_sim > 0 and cosine < min_sim:
            continue
        scored.append((semantic_score(memory, cosine), memory))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    gated = [memory for _, memory in scored]
    merged = always + gated
    if query_text and is_food_or_diet_query(query_text):
        have = {id(memory) for memory in merged}
        for memory in eligible:
            if id(memory) in have:
                continue
            if is_food_or_diet_memory_text(memory.text):
                merged.append(memory)
                have.add(id(memory))
    return merged[: settings.memory_inject_limit]
