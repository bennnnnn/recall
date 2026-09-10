# Memory V2 (atomic facts)

Long-term memory is **one retrievable fact per row**, not one growing paragraph per
`profile|preference|project|fact|focus` type. `type` is only a UI grouping.

## Storage

- Dropped `uq_memories_user_type`. Added `status` (`active|superseded|muted`),
  `sensitivity`, `importance`, `last_confirmed_at`, `superseded_*`, `source_message_id`.
- Cap: 150 **active** facts. Evict lowest-importance / fastest-decay first; protect
  high-importance identity profile facts.
- Existing blobs were sentence-split on migration `0087_memory_facts`.

## Extract / retrieve

Extraction returns ops (`add|update|supersede|delete`). Writes are optimistic per fact
(skip if the matched row changed under the lock). Embeddings update only for touched rows.

Retrieval scores active facts (cosine + importance + recency), always injects a tiny
identity core, then packs **whole facts** into `memory_inject_max_chars`. No mid-fact `…` cut.

Highly sensitive facts are not auto-stored unless the user said “remember” or
`memory_include_sensitive` is on. Extraction stays post-turn (never on TTFT).

## Out of scope

- **Temporary Chat** (a no-memory thread) — deferred in FEATURES.md.
- Recalled-memory chips, chat “Sources” rows, extracting from assistant text.
