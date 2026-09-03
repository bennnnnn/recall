"""Which memories go into a prompt, in what order, and how they're rendered.

Pure ranking and formatting — no Redis, no DB, no awaits. The stateful core
(`app/services/memory/__init__.py`) imports these into its own namespace and
calls them there, so tests patching `app.services.memory.format_memory_block`
and friends still intercept the internal calls.
"""

from types import SimpleNamespace

from app.core.config import Settings
from app.models.orm import Memory
from app.services.memory.text import (
    is_diet_health_memory_text,
    is_food_or_diet_query,
    is_sensitive_memory_text,
    join_memory_facts,
    memory_fact_matches_query,
    split_memory_facts,
    strip_memory_as_of,
)

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


# Identity is useful on most turns; cap it so a long profile cannot eat the
# whole inject budget before a matching project/fact appears.
_PROFILE_PROMPT_MAX_CHARS = 600


def select_facts_for_prompt(
    memory: Memory,
    *,
    query_text: str | None,
    exclude_sensitive: bool,
) -> list[str]:
    """Pick individual sentences from a section — never the whole blob blindly.

    Profile stays available as identity. Preferences need a query match so
    cooking notes do not ride along with the weather. Gated types (already
    cosine-selected) keep matching sentences, or the whole allowed set when
    the ask is semantically related but lexically different (hiking / outdoor).
    """
    facts = split_memory_facts(strip_memory_as_of(memory.text))
    query = (query_text or "").strip()
    keep_diet = bool(query) and is_food_or_diet_query(query)
    allowed: list[str] = []
    for fact in facts:
        sensitive = is_sensitive_memory_text(fact)
        if exclude_sensitive and sensitive:
            if keep_diet and is_diet_health_memory_text(fact):
                allowed.append(fact)
            continue
        allowed.append(fact)
    if not query:
        return allowed
    if memory.type == "profile":
        return allowed
    matched = [fact for fact in allowed if memory_fact_matches_query(fact, query)]
    if matched:
        return matched
    if memory.type in _SIMILARITY_GATED_TYPES:
        return allowed
    return []


def prompt_memories_from_facts(
    memories: list[Memory],
    *,
    query_text: str | None,
    exclude_sensitive: bool,
) -> list[SimpleNamespace]:
    """Copy sections with only the facts that should reach the prompt."""
    out: list[SimpleNamespace] = []
    for memory in memories:
        facts = select_facts_for_prompt(
            memory,
            query_text=query_text,
            exclude_sensitive=exclude_sensitive,
        )
        if not facts:
            continue
        out.append(
            SimpleNamespace(
                type=memory.type,
                text=join_memory_facts(facts),
                confidence=getattr(memory, "confidence", None),
            )
        )
    return out


def format_memory_block(memories: list, *, max_chars: int = 0) -> str:
    if not memories:
        return ""
    ordered = sorted(memories, key=lambda m: TYPE_PRIORITY.get(m.type, 99))
    lines = ["Known facts about the user:"]
    used = len(lines[0])
    for memory in ordered:
        label = SECTION_LABELS.get(memory.type, memory.type.title())
        facts = split_memory_facts(strip_memory_as_of(getattr(memory, "text", "") or ""))
        if not facts:
            continue
        section_header = f"\n## {label}\n"
        profile_cap = (
            used + _PROFILE_PROMPT_MAX_CHARS if memory.type == "profile" and max_chars > 0 else 0
        )
        kept: list[str] = []
        truncated = False
        for fact in facts:
            body = join_memory_facts([*kept, fact])
            piece = section_header + body
            next_used = used + len(piece)
            over_budget = max_chars > 0 and next_used > max_chars
            over_profile = profile_cap > 0 and next_used > profile_cap
            if over_budget or over_profile:
                if not kept and max_chars > 0:
                    room = max_chars - used - len(section_header) - 1
                    if room > 20:
                        lines.append(section_header + fact[:room].rstrip() + "…")
                        used = max_chars
                        truncated = True
                break
            kept.append(fact)
        if truncated:
            break
        if kept:
            block = section_header + join_memory_facts(kept)
            lines.append(block)
            used += len(block)
            if max_chars > 0 and used >= max_chars:
                break
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
