"""Personal memory: extraction cadence, injection limits, semantic recall, caches."""

from pydantic import BaseModel


class MemorySettings(BaseModel):
    semantic_memory_enabled: bool = True
    memory_min_confidence: float = 0.4
    memory_inject_limit: int = 15
    # A store of this many facts or fewer (that fits memory_inject_max_chars) is read whole
    # on every turn that reads memory, so a question needs no word or vector in common with
    # the fact it needs (``selection.select_whole_store``). 0 turns it off.
    memory_whole_store_max_facts: int = 15
    memory_active_fact_cap: int = 150
    # A new fact this close (cosine) to an active one says the same thing in other words
    # and replaces it. Measured 2026-11-20: true paraphrases scored 0.89-0.91, distinct
    # look-alikes ("plays guitar" / "plays piano", "lives in Paris" / "in Lyon") 0.52-0.86.
    memory_near_duplicate_similarity: float = 0.88
    # Untouched stale vectors embedded per apply pass. Touched rows always
    # embed; leftover NULLs wait for a later pass instead of bursting 150
    # HTTP calls on the first write after migration.
    memory_embed_backfill_per_pass: int = 16
    # Hard cap on formatted memory block chars injected into the system prompt.
    memory_inject_max_chars: int = 1500
    memory_cache_ttl: int = 300
    memory_query_cache_ttl: int = 120
    # Run memory extraction every N completed assistant turns (always on turn 1,
    # and always on an explicit remember/forget). Default 1 so a fact stated on
    # turn 2 is not dropped if the chat ends there. Ops can raise this to skip
    # intermediate LLM cost; skipped lines still land on the next pass via the
    # extract cursor.
    memory_extract_every_n_turns: int = 1
    # A turn's recalls share one query vector; the next message is rarely the same
    # text, so a long TTL mostly holds dead vectors (8 KB each, packed float32).
    memory_query_embed_cache_ttl: int = 300
    # Chat-path live embed budget, for memory and chat-history recall: a slow
    # embedding provider falls back to the type-priority memory block (and no
    # earlier-chat snippets) instead of holding the first token. The embed runs
    # on and fills the cache for the next turn. Document search waits longer
    # (attachments/rag.py): a question about a file needs its excerpts. Background
    # jobs use background_llm_timeout_seconds.
    memory_query_embed_timeout_seconds: float = 0.75
    # Minimum cosine similarity for a fact to join a question's block (0 = disabled), in a
    # store too large to read whole. Short facts score low with the embedding model: "what
    # job do i do again" is 0.33 from "User works as a nurse", "where do i live again?" 0.34
    # from "User lives in Denver", while an unrelated fact tops out near 0.25
    # (memory_recall_eval --large, 2026-11-22). 0.35 kept the right fact out.
    memory_min_similarity: float = 0.28
