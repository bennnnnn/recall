# D. Network and I/O efficiency — backend (NET-)

Auditor: network/IO dimension. Code audited: `/home/user/recall-audit` at `d2ec42b0` (read-only).
Paths below are repo-relative. Nothing was run except small `ast`/text scripts in
`tmp/code-audit/raw/scratch-net/` (no tests, no DB, no Redis, no network).

## Cost model used in this file (read this first)

Production shape from `fly.toml`: one `app` machine in `iad`, Neon in AWS `us-east-2`, through the
Neon pooler; Upstash Redis. iad↔us-east-2 is roughly 11–13 ms per round trip (RTT). Production env
in `fly.toml`: `WEB_SEARCH_CLASSIFIER_ENABLED=false`, `MEMORY_QUERY_EMBED_TIMEOUT_SECONDS=0.75`,
`CHAT_STREAM_CONNECT_TIMEOUT_SECONDS=5`.

What one `async with SessionLocal() as s:` that runs one statement costs on the wire, with the
locked versions (SQLAlchemy 2.1.0, asyncpg 0.32.0, `pool_pre_ping=True` in `core/db.py:29`):

| Step | Round trips | Source |
|---|---|---|
| Pool checkout pre-ping: the asyncpg adapter opens a transaction around the ping "to support pgbouncer transaction mode" | 3 (`BEGIN`, `;`, `ROLLBACK`) | `.venv/.../sqlalchemy/dialects/postgresql/asyncpg.py:866-877`; pinged on every non-fresh checkout, `sqlalchemy/pool/base.py:1314-1326` |
| First statement starts the session's transaction | 1 (`BEGIN`) | `asyncpg.py:883-895` (`_start_transaction`) |
| The statement | 1 | — |
| Session close: reset-on-return | 1 (`ROLLBACK`, or `COMMIT` for writers) | `asyncpg.py:905-912`, pool `reset_on_return="rollback"` |

So a one-query read session is about 6 round trips (~70 ms at 12 ms), of which 5 are overhead.
Opening a session that never executes costs nothing (connection checkout is lazy). This is the
baseline behind several findings; NET-03 is the finding about it.

## 1. One ordinary chat turn, traced

Assumptions: WebSocket (`modules/chat/ws_api.py`, the phone's transport), plain text question,
memory on, no attachments, not a greeting, a chat that already has ≥ 20 messages (recent window
full), turn does not need maths/search, production flags. "Before 1st token" = on the path before
the first model byte reaches the phone; "before done" = after the last token but before the `done`
frame; "bg" = background task / worker.

| # | Step (file:line) | Call | Count per turn | Path | Cached? |
|---|---|---|---|---|---|
| 1 | Token re-check per chargeable frame (`ws_api.py:393`, `core/access_tokens.py:94-116`) | Redis `GET revoked:jti:*`, `GET revoked:sid:*`, `GET revoked_since:*` (sequential) | 3 | before 1st token | no (MGET already listed in SCALING.md) |
| 2 | Chat rate limit (`ws_api.py:405`, `core/rate_limit.py:18-21`) | Redis `MULTI INCR EXPIRE EXEC` (1 RTT) | 1 RTT / 2–4 cmds | before | — |
| 3 | Prepare lock (`turn_resources.py:118`, `core/redis_lock.py:38-41`) | Redis `SET chatprep:{chat} NX EX 30`; refresh `EVAL` every 10 s (`turn_resources.py:152-169`); release `EVAL` (`:140`) | 2 + 1 per 10 s | before / bg / after done | — |
| 4 | Wait for previous finalize (`turn_load.py:187`, `finalize_registry.py:166-172`) | Redis `EXISTS chatfinal:{chat}` (polls 50 ms while set) | 1 (+polls) | before | — |
| 5 | Load user (`turn_load.py:79-93`) — WS passes `user=None` | SQL `SELECT users WHERE id` (own session) | 1 session | before (parallel lane) | **no** — `core/user_cache.py` is used by REST/SSE but not by the WS turn (NET-04) |
| 6 | Load chat (`turn_load.py:106-126`) | SQL `SELECT chats` (own session) unless this machine created it (`repositories/chats.py:58-60`) | 0–1 session | before (parallel lane) | 120 s, only on the creating machine |
| 7 | Quota probe (`turn_load.py:129-142`, `services/quota/tokens.py:43-45`) | Redis `EXISTS usage:{user}:{day}` | 1 | before (parallel lane) | — |
| 8 | Recent window (`turn_load.py:189-198`) | SQL `SELECT messages … LIMIT 20` + `SELECT count(*) FROM messages WHERE chat_id` (window full) | 1 session, 2 stmts | before (parallel lane, the longest) | no |
| 9 | Model health (`turn_load.py:283-287`, `services/model_health.py:50-53,95`) | Redis `ZRANGE recall:model_health:samples:{alias} 0 -1` × 6 selectable models | 6 | before (parallel lane) | no (NET-05) |
| 10 | Turn mode (`turn_load.py:257-258`, `turn_prep/mode.py:185-202`) | SQL `get_last_assistant` (short replies), `list_recent(8)` (profile push-back), `list_recent(7)` (draft follow-ups) — rows step 8 already holds | 0–1 session, sequential after step 8 | before | no (NET-04) |
| 11 | Photo / image-gen intercepts (`turn_intercepts.py:267-305`) | none for plain text (pure functions) | 0 | — | — |
| 12 | Reserve quota (`turn_resources.py:299-317`, `core/spend_counter.py:63-78`, `tokens.py:37-40,133-151`) | Redis `GET spend_musd:{day}`, `GET spend_mcents:{day}` (legacy, dead since 2026-10-16), `GET usage`, `INCRBY usage` (+`EXPIRE` on first) | 4–5 sequential | before | no |
| 13 | Save user message beside prompt build (`prepare.py:199-222`, `turn_prep/persist.py:107-119`) | SQL `INSERT messages` + `COMMIT` (own session) | 1 session | concurrent with 14–17; awaited before the first token is sent (`stream_paths.py:270`) | — |
| 14 | Attachment-RAG probe for slim turns (`prompt_builder.py:227-232`; `prepare.py:173-185` turns it on whenever `prior_count ≥ 20`) | SQL `SELECT attachment_chunks.id … LIMIT 1` (own session) | 1 session | before (sequential) | no |
| 15 | Unsummarized gap (`prompt_window.py:75-83`, `prompt_context.py:304-349`) | SQL `SELECT count(*) FROM messages WHERE chat_id` (**second count this turn**) + `list_before … LIMIT ≤10` | 1 session, 2 stmts | before (sequential) | no (NET-04) |
| 16 | Memory note (`prompt_builder.py:379-381`, `prompt_memory.py:150-161`) | Redis spend GETs, only for an explicit "remember" | 0 (2 on a memory command) | before | — |
| 17 | Fallback health (`turn_prep/context.py:259-278`) | reuses step 9 on a new turn | 0 | — | — |
| 18 | Web/subject augmentation (`turn_prep/augment.py:90-101`) | skipped for a plain slim turn | 0 | — | — |
| 19 | Reserve top-up (`turn_resources.py:219-269`) | Redis `GET usage` + `INCRBY` when the prompt estimate grew | 0–2 | before | — |
| 20 | Tool-loop gate (`stream_paths.py:166`) | Redis spend `GET` × 2 again | 2 | before | no (NET-05) |
| 21 | Web-search classifier (`stream_paths.py:119-136`) | model call — off in production (`fly.toml` `WEB_SEARCH_CLASSIFIER_ENABLED=false`) | 0 | — | — |
| 22 | Reply stream (`stream_paths.py:248-258`, `gateways/litellm_gateway.py:286-319`) | OpenRouter `acompletion(stream=True)` on the routed alias; fallbacks only on failure | 1 model call | the critical path | — |
| 23 | Health sample (`stream_paths.py:311`, `model_health.py:41-45`) | Redis pipeline `ZADD`+`ZREMRANGEBYRANK`+`EXPIRE` (1 RTT) | 3 cmds | before done | — |
| 24 | Finalize passes (`finalize_passes.py:122-169`) | CPU only for a plain reply (photo / picture / SymPy / PubChem / reminder passes only when the reply has those fences) | 0 | before done | — |
| 25 | Finalize marker (`stream_pipeline.py:101`, `finalize_registry.py:113-118`) | Redis `SET chatfinal:{chat} EX 30` | 1 | before done | — |
| 26 | Save reply (`turn_settle.py:275-314`) | SQL `INSERT messages`, `UPDATE chats SET updated_at`, `INSERT … ON CONFLICT usage_daily`, **`SELECT usage_daily` (result unused)**, `COMMIT` (one session) | 1 session, 5 stmts | before `done` (`ws_turn.py:123-124`) | — (NET-08) |
| 27 | Settle quota and spend (`turn_settle.py:241-271`) | Redis `INCRBY usage` (or `GET` when delta is 0), `INCRBY spend_musd` | 2 | before done | — |
| 28 | Clear marker (`turn_settle.py:312`) | Redis `DEL chatfinal:{chat}` | 1 | before done | — |
| 29 | Follow-up questions (`stream_pipeline.py:86-100`, `related_prompts.py:184-195`) | Redis spend `GET` × 2; 1–2 model calls on `memory-model` (retry when < 3 kept, `:92-103`); Redis `SET related_prompts:{msg}` | 2 + 1–2 model + 1 | bg (sent after `done`) | per message id, 7 days |
| 30 | Post-turn jobs (`post_turn.py:239-262`, `core/jobs/queue.py:67-72,107-126`) | Redis spend `GET` × 2; per job `XADD` + `XPENDING` + `XTRIM`; jobs on a plain turn: `memory`, `compress`, `message_index` (+`topic` on turn 1) | 2 + 9 (12 on turn 1) | bg | trim known in SCALING.md |
| 31 | Worker side of those jobs (`core/jobs/worker.py:110-142`, `core/jobs/dedupe.py`) | per job: claim `SET NX`, (dup check `GET`/`TTL`), done `SET`, `XACK`; `memory` job = 1 model call + DB; `message_index` = 1 embed batch + DB writes of 2–6 chunk rows; `compress` = skipped as already done (SCALE-02) | ~4–5 Redis per job + work | worker | — |

**Totals for this turn (API process only):**

| Resource | Count | Before 1st token | Notes |
|---|---|---|---|
| DB sessions that touch the wire | 6–8 (steps 5, 6, 8, 10 (some messages), 13, 14, 15, 26) | 5–7, of which 3–4 are **sequential** (8 → 10 → 14 → 15) | each pays 4–5 overhead round trips (cost model above) |
| SQL statements (app) | 10–13 | 8–11 | 2 `count(*)` of the same chat; 1 unused `SELECT` |
| SQL round trips incl. ping/BEGIN/ROLLBACK | ≈ 48–54 | ≈ 39–45; sequential ≈ 21 (≈ 27 with step 10) ≈ 250–320 ms at 12 ms RTT, of which ≈ 15–20 are session overhead | estimated from the cost model; `before_cursor_execute` cannot see the overhead (NET-03 says how to count it) |
| Redis commands | ≈ 43 with the spend cap on (37 measured with it off) | ≈ 22 | ≈ 13 avoidable, ≈ 18 with the two SCALING.md items (NET-05) |
| Model calls | 1 (+1–2 follow-up questions, bg) | 1 | + worker: 1 memory extraction, 1 embedding batch |

**What changes for other turns:**

| Turn | Extra network work |
|---|---|
| Personal / advice / work turn (memory loaded, `prompt_builder.py:237-255`) | Redis `GET memgen` + `GET memquery` (`retrieval.py:298-313`), `GET memembed` + embedding HTTP call (`embedding_gateway.py:145-192`, 0.75 s budget) + `SET memembed` (34 KB JSON); SQL `SELECT * FROM memories WHERE user_id` returning every active+muted fact with both embedding copies (NET-01); todos section 1–2 SQL (`todos/prompt_context.py:257-279`); history RAG: SQL probe `has_chunks_for_user` + a **second embedding call for the same text** (NET-06) + SQL HNSW search returning 6 full chunk rows with both embedding copies (NET-02); `_load_prior_user_messages` SQL when the turn is "rich" (`augment.py:237,260-262`, NET-04). Up to 12 DB sessions in the turn. |
| Maths question | SymPy process pool (CPU, `core/sympy_executor.py`); `_load_prior_user_messages` SQL (NET-04); when the regex reader misses, one structured model call (2.5 s, one retry on a second provider: `core/settings/stem.py:30-37`); word problems one call (3 s + one retry). Tool loop only when the server did not verify (`tool_loop/selection.py:75-120`). |
| Web-search question (tool loop, `tool_loop/rounds.py:110-128`) | No selection model call for an obvious lookup; `search_queries_for_turn` may make one reference-resolver model call (`web_search/turn_query.py:94-100`); Tavily reserve (Redis counter), Redis cache `GET`/`SET` per query (per-user key, `search_cache.py:163-165`); Tavily HTTP (pooled client). `_load_prior_user_messages` SQL. |
| Regenerate (`stream_entry.py:211-333`, `turn_load.py:290-338`) | One session with 5–6 **sequential** statements (user, chat, last, last user, `count(*)`, mode) — user row uncached on both transports; `seed=True` → Redis `EXISTS usage` + `EXISTS heal-flag` (`turn_settle.py:55-57`); recent window read again inside prompt build (`prompt_context.py:131-140`) because `TurnRequest.recent_messages` is not passed; model health read again for the plan pool: `ZRANGE` × N (`context.py:269-275`); image-gen intercept may `list_recent(20)` again (`turn_intercepts.py:83-88`). |
| Message with attachments (`turn_prep/attachments.py`) | The attachment rows are read 3 times (`stream_entry.py:69-72` → `count_image_attachments`; `attachments.py:184`; `persist.py:172`); one **session per verified row inside a loop** (`attachments.py:251-254`); R2 copy for a reused Library file inside an open transaction (`attachments/reuse.py:43`; LEAK-01). |

**Measured cross-check.** The lead's scratch run (`tmp/code-audit/raw/io-counts.json`, from the
untracked `apps/api/app/tests/security/test_zz_audit_io_counts.py`, real Postgres + fakeredis,
SSE transport, spend cap off because tests set `daily_global_spend_usd=0`) agrees with the trace:
warm plain SSE turn = 9 SQL statements and 37 Redis commands (production adds 2 `GET`s per spend
check: 6–8 more); maths turn = `SELECT messages` ×2 (window + `recent_user_contents`); regenerate =
15 SQL incl. `SELECT messages` ×6 and `SELECT users` even though SSE had the cached user;
`SELECT usage_daily` once per warm turn after the upsert (NET-08). `before_cursor_execute`
does not see `BEGIN`/`ROLLBACK`/ping (asyncpg runs them directly), so that run undercounts
round trips; NET-03 says how to count them.

## 2. Findings

### NET-01 — Memory recall ships every fact's two embedding copies to the API and ranks them in Python
- Severity: High
- Confidence: High (mechanism), Medium (bytes per turn depend on each user's fact count)
- Overlap: SCALE-06 (agent-scale) covers the unused HNSW index from the index side; this is the bytes/CPU side of the same root cause. Merge.
- Locations:
  - `apps/api/app/modules/memory/repository.py:21-37` — `select(Memory)` (every column) for all active **and muted** facts (`include_muted=True` default, `:25`)
  - `apps/api/app/modules/memory/models.py:104-105` — `embedding_json: Text` and `embedding: Vector(1536)` on every row
  - `apps/api/app/modules/memory/retrieval.py:55-78` (`semantic_memories_from_vec`), `:111` (`load_relevant_memories`), `:318-338` (`_query_block`), `:406-416` (`_cached_block`, "self"/"work" scopes, which never use vectors)
  - `apps/api/app/modules/memory/selection.py:92-109` — `parse_embedding(memory.embedding_json)` + `cosine_similarity(...)` per fact
  - `apps/api/app/gateways/embedding_gateway.py:118-138` — pure-Python cosine (re-computes the query vector's norm for every fact) and `json.loads` + `float()` per element
  - pgvector result processing: no codec is registered for asyncpg (grep: no `register_vector`), so the `embedding` column arrives as text and `pgvector.sqlalchemy` parses it into 1,536 floats for every row (`.venv/.../pgvector/sqlalchemy/vector.py:33-36`, `pgvector/vector.py:86-88`) — a vector selection never reads
  - Other full-row readers that use only text/metadata: `apps/api/app/modules/chat/turn_prep/instant.py:129-143` (`_profile_reply`, instant replies; uses `row.text` only), `apps/api/app/modules/memory/documents.py:83` (`GET /memories/documents`), `apps/api/app/modules/memory/enqueue_policy.py:73,87` (`GET /memories`, consolidate), `apps/api/app/modules/memory/learning_progress.py:61`, worker: `extraction_workflow.py:90`, `consolidation_workflow.py:91`, `apply.py:63-73` (only checks presence)
- Evidence:
  ```python
  # modules/memory/selection.py:98-106
  for memory in eligible:
      ...
      vec = parse_embedding(getattr(memory, "embedding_json", None))
      ...
      cosine = cosine_similarity(query_embedding, vec)
  ```
  Sizes (arithmetic in `scratch-net/embed_sizes.py`): one 1536-dim vector as stored by `json.dumps` = **34,151 chars**; as pgvector float4 text ≈ 15–21 KB. So each fact row moves ≈ 50 KB; the cap is 150 active facts (`core/settings/memory.py:10`) plus muted ones. The query-scoped block cache is keyed by the exact question text with a 120 s TTL (`modules/memory/cache.py:12-33`, `core/settings/memory.py:18`) and any memory write bumps the generation key (`modules/memory/cache.py:57-63`; the memory job runs after every turn), so a new question always misses and reloads. Memory turns are common: the measured "What should I cook tonight…" turn loaded memory (`io-counts.json`, `SELECT memories`).
  History: migration `apps/api/alembic/versions/0033_pgvector_real.py:1-6` says it *"Replaces the prior app-side JSON-cosine approach … for DB-side cosine similarity ordering"*. Commit `c788f5d4e` (#640, 2026-08-13) moved ranking back in-process; its test docstring: *"Semantic recall ranks the ≤5 list_for_user rows in-process. pgvector search_semantic is not on this path (the column/index stay for later)."* Memory is now one fact per row with a cap of 150 (CLAUDE.md "memory"), so the ≤5-rows premise is gone; `e64a70326` (#1914, 2026-10-20) then deleted the unused `memories_repo.search_semantic` as dead code.
- Impact: per uncached memory turn, up to ~7.5 MB (150 × ~50 KB) is detoasted on Neon, sent iad←us-east-2, and parsed twice on the API's single event loop (~460k `float()` calls plus 150 × 1,536-element Python dot products and norms) before the first token; every other socket on that machine waits while it runs (SCALING.md: one event loop per machine; "Measure before moving any of it"). A user with 40 facts still moves ~2 MB per memory turn. The worker pays it too, on **every** turn with memory on: the `memory` job is queued after each turn (`memory_extract_every_n_turns=1`, `core/settings/memory.py:24`) and its snapshot loads every active fact with both embeddings to read `id`, `type`, `topic`, `text` and `last_confirmed_at` (`apps/api/app/modules/memory/extraction_workflow.py:90-117`), then reloads them after any write (`apply.py:63-73`, which needs only "has an embedding" and the text hash). Cost grows linearly with the fact count the product is designed to grow toward. The HNSW index `ix_memories_embedding` is written on every fact write and never read.
- Fix: rank in SQL and return narrow rows. One query in `modules/memory/repository.py`: `select(Memory.id, Memory.type, Memory.topic, Memory.text, Memory.confidence, Memory.importance, Memory.sensitivity, Memory.status, Memory.last_confirmed_at, (1 - Memory.embedding.cosine_distance(q)).label("similarity"))` over the user's active facts (150 rows: Postgres computes the distances in C; no index needed at this size), and make `selection.select_memories_semantic` take the similarity instead of parsing JSON (same `semantic_score`, same `memory_min_similarity`, same identity core and diet rules — behaviour-preserving). Every other reader selects named columns (or `load_only(...)` + `raiseload("*")`; plain `defer` would lazy-load and raise `MissingGreenlet` under async). Seam: `modules/memory/repository.py` + `selection.py`.
- Effort: M
- Verify: (1) scratch test on the `world` fixture: seed 150 facts with 1536-dim vectors for user A, count bytes with `before_cursor_execute` + `after_cursor_execute` (`len(repr(rows))`) or simply `SELECT sum(octet_length(embedding_json)) + sum(pg_column_size(embedding)) FROM memories WHERE user_id = :a`; before ≈ 7–8 MB per memory turn, after < 50 KB. (2) Same selection output for a fixed corpus (golden test over `select_memories_semantic`). (3) Production: `chat_stream_timing` `prompt_ready_ms` p95 on memory turns; event-loop lag.

### NET-02 — Every vector is also written as 34 KB of JSON text, and every chunk search reads both copies back
- Severity: High
- Confidence: High
- Overlap: SCALE-06 notes the chunk searches' index plan; the write volume and the dead JSON column are not covered there.
- Locations:
  - Writes: `apps/api/app/repositories/message_chunks.py:58-69` (`embedding_json=json.dumps(vec)` next to `embedding=vec`), `apps/api/app/modules/attachments/chunks_repository.py:94-105`, memory: `apps/api/app/modules/memory/writes_repository.py:229-249`, `apps/api/app/modules/memory/repository.py:236-248`
  - Columns: `apps/api/app/models/orm/attachments.py:52-53` (`message_chunks`), `apps/api/app/modules/attachments/models.py:107-108` (`attachment_chunks`), `apps/api/app/modules/memory/models.py:104-105`
  - Reads of full rows: `apps/api/app/repositories/message_chunks.py:99-106` and `apps/api/app/modules/attachments/chunks_repository.py:135-142` (`select(MessageChunk)` / `select(AttachmentChunk)`, LIMIT 6); callers use `row.text`, `row.created_at`, `row.attachment_id` only (`apps/api/app/modules/chat/history_rag.py:250-258`, `apps/api/app/modules/attachments/rag.py:355-365`)
  - The JSON is read only for non-1536 vectors: `history_rag.py:238-248`, `attachments/rag.py:343-353`, `message_chunks.py:90-94`, `chunks_repository.py:125-130`. Even mock mode pads to 1536 (`embedding_gateway.py:32-40`), so only tests with short vectors take that branch.
- Evidence:
  ```python
  # repositories/message_chunks.py:59-68
  MessageChunk(..., text=text,
               embedding_json=None if vec is None else json.dumps(vec),
               embedding=vec if vec is not None and len(vec) == EMBEDDING_DIM else None)
  ```
  `message_index` is queued after every turn with memory on (`apps/api/app/modules/chat/post_turn.py:197-218`) and indexes the user line and the reply (`history_rag.py:105-148`) in 900-char chunks, up to 6 per message (`apps/api/app/core/settings/chat.py:12-15`): typically 2–5 chunk rows per turn, each with ~34 KB of JSON beside a 6 KB vector.
- Impact: roughly half of each chunk row's bytes are a JSON copy production never reads. Per 1M turns: ~3M chunk rows → ~100 GB of JSON text through WAL (~45–55 GB stored after TOAST compression; `zlib` gets it to 15 KB, pglz less). That is storage billed by Neon every month thereafter, plus vacuum and backup volume, on the table that grows with every turn. Each personal turn's history-RAG and attachment-RAG searches also pull 6 × (~34 KB JSON + ~15–21 KB vector text) ≈ 300 KB each from Neon before the first token, only to read `text`.
- Fix: (1) stop writing `embedding_json` (`None`) in the three writers; (2) select named columns in both `search_semantic`s (`id, message_id, chat_id, role, text, created_at` / `attachment_id, chunk_index, text`); (3) after NET-01, nothing reads `memories.embedding_json`; drop the three columns in a later release (expand/contract, `docs/ENGINEERING_STANDARDS.md` "Schema changes"); tests that use 3-dim vectors switch to padded 1536-dim fakes. Seams: `repositories/message_chunks.py`, `modules/attachments/chunks_repository.py`, memory writes.
- Effort: M (S for steps 1–2)
- Verify: `SELECT avg(pg_column_size(embedding_json)), avg(pg_column_size(embedding)) FROM message_chunks` and `pg_total_relation_size('message_chunks')` growth per day, before/after; a unit test that `replace_chunks` writes `embedding_json IS NULL` for 1536-dim vectors; bytes returned by `search_semantic` (scratch test as in NET-01).

### NET-03 — Each DB session costs about five extra round trips (pre-ping inside a transaction, BEGIN, ROLLBACK), and a turn opens 6–12 sessions, 3–5 of them one after another before the first token
- Severity: High
- Confidence: High (mechanism, from the installed library code); Medium (milliseconds, which depend on the iad↔us-east-2 RTT)
- Locations:
  - `apps/api/app/core/db.py:25-37` — `pool_pre_ping=True`, default (transactional) isolation, one engine
  - `.venv/.../sqlalchemy/dialects/postgresql/asyncpg.py:866-877` (ping = `BEGIN` + `;` + `ROLLBACK` "to support pgbouncer transaction mode"), `:883-895` (`BEGIN` on first statement), `:905-912` (`ROLLBACK` on return); `.venv/.../sqlalchemy/pool/base.py:1314-1326` (ping on every non-fresh checkout); asyncpg `transaction.py:146,206` (each is a separate `execute`)
  - Sessions on the turn path (one checkout each): `apps/api/app/modules/chat/turn_load.py:87-88` (user), `:121-122` (chat), `:189-198` (window + count), `:257-258` (mode, 3 message shapes), `apps/api/app/modules/chat/turn_prep/persist.py:107` (user row), `apps/api/app/modules/chat/prompt_builder.py:229-230` (attachment probe), `apps/api/app/modules/chat/prompt_context.py:139,143,155,334` (window/memory/todos/gap), `apps/api/app/modules/chat/history_rag.py:178,225` (probe/search), `apps/api/app/modules/attachments/rag.py:293,326`, `apps/api/app/modules/chat/turn_prep/augment.py:261` (priors), `apps/api/app/modules/chat/turn_settle.py:294` (reply)
  - Design comments that assume a session is cheap: `turn_load.py:157-161` ("Each DB read gets its own AsyncSession"), `prompt_builder.py:302-306`, `prompt_context.py:89-96`
- Evidence: cost per one-query read session = ping 3 + `BEGIN` 1 + statement 1 + `ROLLBACK` 1 = 6 round trips, 5 of them overhead (table at the top). Sequential chain before the first token on a long chat's plain turn: window lane (`turn_load.py:189-198`) → attachment probe (`prompt_builder.py:227-232`, on because `prior_count ≥ 20`, `prepare.py:185`) → gap (`prompt_context.py:334-349`) = 3 sessions ≈ 15 overhead round trips ≈ 180 ms at 12 ms; `_classify_turn_mode` (short replies, edit follow-ups) and `_load_prior_user_messages` (maths, search, rich turns) add one session each. After the last token, the reply commit (`turn_settle.py:294-303`) is ping 3 + `BEGIN` + 4 statements + `COMMIT` before `done`. Docs understate this: `docs/PRODUCTION.md:528` says pre-ping "runs a statement on every checkout"; with this dialect it is three round trips, plus the `BEGIN`/`ROLLBACK` pair every session pays.
- Impact: a fixed latency tax of roughly 0.2–0.3 s before the first token on ordinary turns in long chats (estimate), paid again on every REST request that touches the DB; and 4–5 extra statements per session on Neon's compute and pooler (about 3× the app's own statement count), which is what fills `pg_stat_statements` and the pooler's queue first when traffic grows.
- Fix, in order: (1) fewer sessions: fold the turn's sequential reads into the lanes that already hold one (NET-04 removes 2–3); (2) ping only connections that sat idle: `pool_pre_ping=False`, a pool `checkin` listener that stamps `record.info["checked_in_at"]`, and a `checkout` listener that pings (`dbapi_connection.ping()`, still transaction-wrapped) only when the stamp is older than ~30 s and raises `sqlalchemy.exc.DisconnectionError` on failure, which makes the pool replace the connection (SQLAlchemy's pool-event contract) — a hot pool then skips the ping; (3) for read-only lanes, a small second engine created with `isolation_level="AUTOCOMMIT"` (its ping is a bare `;` and it sends no `BEGIN`/`ROLLBACK`, `asyncpg.py:876-877,884-885`), sized inside the SCALING.md pool budget — precondition: Neon's pooler must handle protocol-level prepared statements outside a transaction (the reason for the wrapped ping, SQLAlchemy #10226); note an `execution_options(isolation_level=…)` on the existing engine would not help, because the ping runs at checkout before the option is applied. Seams: `core/db.py`, `turn_deps.ChatTurnDeps.session_factory` (add a read factory).
- Effort: S (2), M (1, 3)
- Verify: scratch test on the `world` fixture (model on `test_zz_audit_io_counts.py`): count `engine.sync_engine.pool` `"checkout"` events and wrap `asyncpg.connection.Connection.execute` / `.fetchrow` at class level to count `BEGIN`, `ROLLBACK`, `COMMIT` and `;` during one warm plain turn. Expect today ≈ 7 checkouts, ≈ 7 pings, ≈ 14 `BEGIN`. Production: `pg_stat_statements` calls of `BEGIN`, `ROLLBACK`, `;` against the app's statements; `chat_stream_timing` `phases_ms.history_ready`, `prompt_assembled`, `first_token_ms` p50/p95.

### NET-04 — A turn re-reads rows and counts it already holds, in extra sessions, mostly before the first token
- Severity: Medium
- Confidence: High
- Locations (one pattern: the recent window, the count, the user and the attachment rows are loaded once and then fetched again):
  - Turn mode re-reads messages the window holds: `apps/api/app/modules/chat/turn_prep/mode.py:185-188` (`get_last_assistant` for "yes"/"ok"/"no"), `:191-193` → `:134-148` (`list_recent(8)` for "you should know that"), `:199-202` → `:155-168` (`list_recent(7)` for edit follow-ups: "make it shorter", "use python instead", "add error handling", any ≤30-word line matching `prompt_constants/writing.py:159-195`). Called from `apps/api/app/modules/chat/turn_load.py:257-258` *after* `turn.recent` (20 rows) is loaded at `:246-253`; same function at `turn_load.py:328`, `turn_prep/persist.py:139`, `turn_prep/context.py:245`.
  - Earlier user lines read again on every augmented turn (maths, chemistry, search, rich): `apps/api/app/modules/chat/turn_prep/augment.py:237` → `:260-262` → `apps/api/app/repositories/messages.py:248-260` (`recent_user_contents`, `ORDER BY created_at` with no id tie-break), while two functions down the same module derives them from the prompt (`augment.py:180,222`, `_prompt_prior_user_messages`). It also races the user-row insert started at `turn_prep/prepare.py:211`, so whether the current line is in "priors" depends on timing. Measured: maths turn = `SELECT messages` ×2 (`io-counts.json`).
  - `count(*)` of the chat twice per turn once the window is full: `apps/api/app/modules/chat/turn_load.py:64-76,192-198` (`prior_count`, exact) and again `apps/api/app/modules/chat/prompt_context.py:333-335` (`_load_unsummarized_gap`); the second also races the user-row insert (an off-by-one `window_start` in `services/context_window.py:155-178`). `count(*)` is O(messages in the chat) (index-only scan, agent-scale index table).
  - The WebSocket turn reads the user row from Postgres every turn: `apps/api/app/modules/chat/ws_api.py:193-208` passes no `user`, so `turn_load.py:79-93` queries; SSE passes the cached row (`apps/api/app/modules/chat/stream_api.py:289`, from `core/deps.py:50-62`). `core/user_cache.py:3-5` says *"Chat auth runs on every send, so the last loaded user stays here"* — not true for the WS transport the phone prefers. Regenerate reads it uncached on both transports (`turn_load.py:306-311`; measured `SELECT users` on the SSE regenerate).
  - Regenerate: one session with 5–6 sequential statements (`turn_load.py:306-328`: user, chat, `get_last`, `get_last_user`, `count`, mode), then `stream_entry.py:268-284` builds `TurnRequest` without `recent_messages` or `unhealthy_models`, so the window is read again (`prompt_context.py:131-140`) and model health again for the plan pool (`turn_prep/context.py:269-275`). Measured: 15 SQL statements, `SELECT messages` ×6, `ZRANGE` ×3 on top of the turn's 6.
  - Attachment turns read the attachment rows three times (`stream_entry.py:69-72` → `turn_prep/attachments.py:27`; `turn_prep/attachments.py:184`; `turn_prep/persist.py:172`) and open one session per verified row inside a loop (`turn_prep/attachments.py:251-254`).
  - Existence probes re-asked every turn for facts that change only when a job indexes something: `apps/api/app/modules/chat/prompt_builder.py:227-232` (`has_chunks_for_chat` on every slim turn of a chat with ≥ 20 messages, enabled by `turn_prep/prepare.py:173-185`), `apps/api/app/modules/attachments/rag.py:290-297` (rich turns), `apps/api/app/modules/chat/history_rag.py:177-183` (`has_chunks_for_user` on every personal turn; true for any user after their first indexed turn).
- Evidence:
  ```python
  # modules/chat/turn_load.py:246-258  (recent is in hand; the mode reads messages again)
  (loaded_user, daily_limit, loaded_chat), (recent, prior_count), unhealthy = await asyncio.gather(...)
  async with deps.session_factory() as session:
      turn_mode = await _classify_turn_mode(session, loaded_chat, content)
  ```
  ```python
  # modules/chat/turn_prep/augment.py:236-237
  # Earlier user lines name the web search subject; loaded only when augmenting.
  priors = await _load_prior_user_messages(identity.chat.id)
  ```
- Impact: each re-read is a full session (≈ 6 round trips ≈ 70 ms, NET-03) and most sit on the sequential path before the first token: short confirmations and edit follow-ups (very common in chat), every maths/search/rich turn, every turn in a long chat. On Neon it is 2–4 avoidable sessions per turn (≈ 10–20 statements with ping/BEGIN/ROLLBACK). The two races give the subject reader and the gap a result that depends on whether the user's own row committed first.
- Fix: one read per turn, passed down. `_classify_turn_mode(chat, content, recent)` derives the last assistant, prior user lines and draft history from the window (all three callers have it or can read it once); `augment._fetch_web_with_priors` uses `request.recent_messages` / the prompt (as `:180,222` already do); carry `prior_count` on `TurnRequest` into `load_prompt_window`/`_load_unsummarized_gap`; `ws_api` passes `user_cache.cached_user(user_id)` like `get_current_user` (the turn already re-reads the row before refusing on consent, `turn_load.py:82-86`); regenerate reads `list_recent(window)` once and derives last/last-user/omit from it, and passes `recent_messages` and `unhealthy_models` into `TurnRequest`; attachment rows are read once and passed, verified rows marked with one `UPDATE … WHERE id IN (…)`; cache the two "has chunks" answers (a Redis flag set by the index jobs, or a column on `chats`/`users`). Seams: `turn_prep/mode.py`, `turn_prep/request.TurnRequest`, `turn_load.py`, `ws_api.py`.
- Effort: M
- Verify: extend the `world` scratch test (`test_zz_audit_io_counts.py`): (i) "yes" after an assistant question, (ii) "make it shorter" after a drafted email, (iii) "solve 2x+5=17" in a chat seeded with 25 messages, (iv) a regenerate, (v) a WS turn. Count `SELECT … messages` and `count(*)`: today (i) 2, (ii) 2, (iii) 2 + 2 counts, (iv) 6, (v) `SELECT users` 1; after: 1 window read and ≤ 1 count per turn, no `SELECT users` on a warm WS turn.

### NET-05 — About 40–45 Redis commands per plain turn; nearly a third are repeated reads of slow-changing global state, one of them a key nothing writes any more
- Severity: Medium
- Confidence: High (counts measured with the spend cap off; production adds the spend reads)
- Locations:
  - Model health, read in full every turn: `apps/api/app/modules/chat/turn_load.py:283-287` → `apps/api/app/services/model_health.py:50-53` (`ZRANGE … 0 -1`, up to 40 members) × 6 selectable models via `asyncio.gather` (`:89-96`); again for the plan pool on regenerate (`turn_prep/context.py:269-275`); `GET /models` (`apps/api/app/routers/models.py:26`). The result is a best-effort hint (`model_health.py:99-109`).
  - Spend cap: `apps/api/app/core/spend_counter.py:63-66` reads two keys one after the other; the second, `spend_mcents:{today}` (`:37-38`), has not been written since `bac689f0e` (deployed 2026-10-15; the comment at `:28-29` says it *"can be dropped after"* its TTL), so since 2026-10-16 it is a guaranteed miss on every check. The check runs up to 4× in a plain turn: `apps/api/app/modules/chat/turn_resources.py:299`, `stream_paths.py:166`, `post_turn.py:239`, `related_prompts.py:184`; plus each model-calling job on the worker (`apps/api/app/background/handlers.py:101`) and 10 other call sites (`grep global_spend_exceeded(`: 15 in all).
  - Per-item commands in loops: `apps/api/app/modules/account/tokens.py:367-369` (`GET /auth/sessions`: one `GET` per refresh token; `MGET` fits); worker: `apps/api/app/modules/notifications/push.py:94-96` (one `DEL` per stale ticket) and `:115-117` (`ZREM` + `GET` + `DEL` per receipt, sequential, after an unbounded `ZRANGEBYSCORE` at `:99-101`) — one pipeline / multi-key `DEL` each.
  - Already recorded in `docs/SCALING.md:77-81` (not re-reported): three revocation `GET`s → `MGET` (`core/access_tokens.py:101-108`); `XPENDING`+`XTRIM` on every enqueue (`core/jobs/queue.py:107-126`).
- Evidence: measured warm plain SSE turn = 37 commands with the spend cap off (`io-counts.json`; the fake's `EVAL` fallback adds a `GET`+`DEL` production does not send), of which `ZRANGE recall:model_health:*` ×6. Production adds 2 `GET`s per spend check (6–8). Per plain turn: ≈ 6 health `ZRANGE`s, ≈ 4 legacy-key `GET`s and ≈ 3 repeated spend `GET`s are avoidable without the two SCALING.md items (≈ 13 of ≈ 43), ≈ 18 with them. The worker adds ≈ 15 per turn (claim, done, ack, spend checks per job). `docs/SCALING.md:61-64` ("Redis commands per request") counts a REST request and the enqueue only; a chat turn — the bulk of traffic — is about ten times that, so the doc understates the per-turn cost.
- Impact: per 1M turns ≈ 43M API-side Redis commands (+ ≈ 15M worker), ≈ 13M of them avoidable; Upstash bills per command (on pay-as-you-go, ~$0.2 per 100k: ~$26 per 1M turns avoidable). The 6-way `gather` opens up to 6 pooled connections per turn on an unbounded pool (SCALING.md item 2: "a burst opens a connection per concurrent command"). Latency is small (parallel lanes; ~1–2 ms per sequential command), so this is cost and connection pressure, not TTFT.
- Fix: (1) delete the legacy key read (`spend_counter.py:65-66`); (2) read the spend verdict once per turn (it is a daily dollar threshold) and pass it, or cache the boolean in-process for 1–2 s; (3) `unhealthy_aliases`: a per-process `TtlCache` of the computed set for 2–5 s (the `core/user_cache.py` pattern; a row in SCALING.md's per-machine table), or one pipeline; (4) `list_sessions` → `MGET`. Seams: `core/spend_counter.py`, `services/model_health.py`.
- Effort: S
- Verify: the `world` scratch test with the spend cap on (`daily_global_spend_usd=1`): Redis commands per warm plain turn today ≈ 43 → ≈ 30 after; no `GET spend_mcents:*`; `ZRANGE` ≤ 6 per 5 s per machine. Production: Upstash daily command count per turn.

### NET-06 — The query embedding is requested two or three times per personal turn; the shared cache that should prevent it is read before anyone has written it
- Severity: Low
- Confidence: High
- Locations: `apps/api/app/gateways/embedding_gateway.py:21-24,145-192` (the comment: *"so a single chat turn embeds the query once, not twice"*); concurrent callers started together by `asyncio.gather` in `apps/api/app/modules/chat/prompt_context.py:208-212` and `:233-239`: memory (`apps/api/app/modules/memory/retrieval.py:318-323`), chat-history RAG (`apps/api/app/modules/chat/history_rag.py:161-193`), attachment RAG (`apps/api/app/modules/attachments/rag.py:299-308`).
  - Same class on the worker: the per-turn `message_index` job embeds the user line and the reply in two separate requests and two transactions (`apps/api/app/modules/chat/history_rag.py:128-139` → `index_message` `:57-70` → `repositories/message_chunks.py:57-71`, which commits per message), although `embed_many` batches up to 64 inputs (`core/settings/llm.py:41`).
- Evidence: all three read `memembed:{user}:{sha(query)}` before any of them has embedded; the two RAG paths first spend a DB probe (~70 ms), which is still shorter than the embedding call, so both miss. No single-flight. Each miss is one embedding HTTP call, one 34 KB `SET` and one spend `INCRBY` (`embedding_gateway.py:70`, `gateways/llm_spend.py:49-53`). In the measured world the user had no chat chunks yet, so only one embed ran; any user with indexed turns (all after their first turn, NET-02) takes the second.
- Impact: 2× (3× with document chunks in the chat) embedding requests on personal turns: provider rate-limit headroom and Redis bandwidth (34 KB per duplicate `SET`); each call also exposes the turn to the slower of two tail latencies within the 0.75 s budget. Money is negligible.
- Fix: one lazily started task per turn in `_ContextReads` (e.g. a `cached_property` returning `asyncio.ensure_future(get_or_embed_query(...))`) whose result the three readers await; memory keeps its block-cache check first. In `index_turn_messages`, chunk both messages, embed them in one `embed_many` call and write both in one transaction. Seams: `modules/chat/prompt_context._ContextReads`, `modules/chat/history_rag.py`.
- Effort: S
- Verify: unit test: a personal turn for a user with history chunks and a counting fake `embed_text` → 1 call (today 2; 3 with attachment chunks); `index_turn_messages` with a counting fake `_embed_request` → 1 request per turn (today 2).

### NET-07 — Reference-photo candidates are fetched one at a time with 8 s each against a 6 s wait; a late photo is still stored, then orphaned
- Severity: Low
- Confidence: High
- Locations: `apps/api/app/modules/images/search.py:111-131` (`_fetch_candidates`: sequential loop, per-candidate deadline `image_search_fetch_timeout_seconds` 8.0, `apps/api/app/core/settings/search.py:23-24`, 3 candidates); Tavily image search 12 s (`apps/api/app/gateways/image_search_gateway.py:21`); answer photo waits 6 s (`apps/api/app/modules/images/answer_photo.py:30,78`) and lets the late task finish storing (`:79-81,102-106`: *"stays unlinked; the attachment reaper removes it"*); the photo-lookup intercept turn (`turn_intercepts.py:217-225` → `search.py:240-243`) fetches up to 3 photos this way before answering.
- Evidence:
  ```python
  # modules/images/search.py:123-130
  for hit in hits:
      if len(fetched) >= max_images:
          break
      # One slow candidate gets the fetch timeout in all, then the next is tried.
      result = await _fetch_one_image(client, hit, deadline_seconds=settings.image_search_fetch_timeout_seconds)
  ```
- Impact: one slow host (common for arbitrary image URLs) costs the whole 6 s answer-photo budget, so the reply goes out without a photo although candidates 2–3 would have arrived in time; the late photo still spends an image-search slot, an R2 `PUT`, a DB row and a reaper delete. A lookup turn can take 12 + 3 × 8 s before its R2 writes.
- Fix: fetch candidates concurrently under one deadline below the caller's wait (`asyncio.wait(..., FIRST_COMPLETED)` until `max_images` are in, cancel the rest); on the answer-photo timeout cancel the task instead of letting it store an orphan. Seam: `images/search._fetch_candidates`, `answer_photo.attach`.
- Effort: S
- Verify: unit test with fake fetches taking 8 s, 0.2 s, 0.2 s: photo in < 1 s; production: rate of "Answer photo took too long" logs and orphan-reaper deletions of `source="search"` rows.

### NET-08 — `done` waits on a SELECT whose result nobody reads
- Severity: Low
- Confidence: High (measured)
- Locations: `apps/api/app/modules/chat/turn_settle.py:208-219` (ignores the return of `usage_repo.add_tokens`), `apps/api/app/repositories/usage.py:52-61` (`session.get(UsageDaily, …)` after the Core upsert: the identity map is empty, so it queries). Only caller: `turn_settle.py:208`.
- Evidence: measured `SELECT usage_daily: 1` on every warm turn (`io-counts.json`), last statement before `COMMIT` in `sql-text.json` ("plain turn"). `ws_turn.py:115-124` holds `done` for this commit.
- Impact: one round trip (~12 ms) inside the commit that gates `done`, on every turn; one statement per turn on Neon.
- Fix: return nothing (or `RETURNING` when a caller needs the row). Seam: `repositories/usage.add_tokens`.
- Effort: S
- Verify: the same scratch count: `SELECT usage_daily` 0 on a warm turn.

### NET-09 — The drawer's chat list reads every column of up to 250 chats, including each chat's summary, to return seven fields
- Severity: Low
- Confidence: High (columns), Medium (plan)
- Locations: `apps/api/app/modules/chat/service.py:58-88`, `apps/api/app/repositories/chats.py:76-95,98-109` (`select(Chat)`, limit 200 + 50 archived), `apps/api/app/models/orm/chat.py:51` (`summary` Text), `apps/api/app/services/context_window.py:14,217-221` (summaries up to 6,000 chars), `apps/api/app/models/schemas/chats.py:55-64` (`ChatOut`: 7 fields). Measured SQL text (`sql-text.json`) shows `chats.summary` in every chat `SELECT`, including the per-turn `get_by_id` (`turn_load.py:121-122`), which also never needs the summary when the window is not full.
- Impact: small today because summaries rarely exist (SCALE-02 keeps compression from running); once compression works, a heavy user's drawer open moves up to ~1.5 MB per call, on a start-up endpoint.
- Fix: `load_only` the seven columns for the list; read `summary` only where the prompt uses it. Seam: `repositories/chats.list_for_user`.
- Effort: S
- Verify: `EXPLAIN (ANALYZE, BUFFERS)` and response bytes from Postgres for a user with 300 chats with summaries.

## 2b. Scratch test for the lead (wire round trips per turn; NET-03, NET-04, NET-08)

Add next to the existing `apps/api/app/tests/security/test_zz_audit_io_counts.py` (same `world`
fixture from `tests/security/conftest.py`, real Postgres + fakeredis, mock model). It counts what
`before_cursor_execute` cannot see: pool checkouts and the `BEGIN`/`;`/`ROLLBACK`/`COMMIT` that
asyncpg sends itself.

```python
import collections, asyncpg, pytest
from sqlalchemy import event
from app.core.background_tasks import drain_background_tasks
from app.core.db import engine

@pytest.mark.asyncio
async def test_audit_wire_roundtrips(world, monkeypatch, thread_sympy_executor):
    calls = collections.Counter()
    Conn = asyncpg.connection.Connection
    orig_execute, orig_fetchrow = Conn.execute, Conn.fetchrow
    async def execute(self, query, *a, **k):          # BEGIN / ROLLBACK / COMMIT
        calls[query.strip().split()[0].rstrip(";").upper() or "?"] += 1
        return await orig_execute(self, query, *a, **k)
    async def fetchrow(self, query, *a, **k):         # the pre-ping is fetchrow(";")
        calls["PING" if query.strip() == ";" else "FETCHROW"] += 1
        return await orig_fetchrow(self, query, *a, **k)
    monkeypatch.setattr(Conn, "execute", execute)
    monkeypatch.setattr(Conn, "fetchrow", fetchrow)
    on_checkout = lambda *_: calls.update(["CHECKOUT"])
    event.listen(engine.sync_engine.pool, "checkout", on_checkout)
    on_sql = lambda conn, cur, stmt, *_: calls.update(["SQL " + stmt.split()[0]])
    event.listen(engine.sync_engine, "before_cursor_execute", on_sql)
    c, a, chat = world.client, world.a, world.a_data.chat_id
    for text in ("warm up", "Any tips for a short walk?"):   # second one is measured
        await drain_background_tasks(); calls.clear()
        await c.post(f"/chats/{chat}/messages/stream", json={"content": text}, headers=a.headers)
        await drain_background_tasks()
    print(dict(calls))   # expect CHECKOUT≈PING, BEGIN≈2×CHECKOUT, ROLLBACK+COMMIT≈2×CHECKOUT
```
Variants for NET-04: seed 25 messages in the chat first (`messages_repo.create` in a loop), then send
"yes" after an assistant line ending in "?", "make it shorter" after a drafted email, and
"Solve 2x + 5 = 17"; count `SQL SELECT` on `messages` and `count(*)`. For the WebSocket path, drive
`modules.chat.ws_api.chat_websocket` with Starlette's `TestClient.websocket_connect` (as
`tests/modules/chat/test_ws.py` does) and look for `SELECT users` on a warm turn.

## 3. Same class, already reported by other auditors (not re-reported here)

- **SCALE-02** (compress dedupe key fixed per chat + 24 h done marker). Network angle only: every turn still enqueues the job (`XADD`+`XPENDING`+`XTRIM`) and the worker claims, checks and acks it (`SET NX`, `GET`, `TTL`, `XACK`) for nothing: ≈ 7 Redis commands per turn; and because `summary_message_count` stays 0, every long-chat turn pays the gap read in NET-04.
- **SCALE-03 / LEAK-01 / LEAK-02** (pooled connections held idle-in-transaction across R2 I/O, waits, an LLM call, and SSE streams after a user-cache miss; measured in `idle-in-transaction.json`). Two more places (three functions) of the same class that I did not see in their lists:
  - `apps/api/app/modules/memory/crud.py:72-127` (`delete_memory_fact`: embedding call at `:105` after `get_by_id` opened the transaction) and `:141-200` (`update_memory`: `update_status` then the embedding call at `:172`) — user-facing memory edits hold a connection across a provider call (`background_llm_timeout_seconds` 60 s).
  - `apps/api/app/modules/chat/service.py:273-288` (`set_message_feedback`): the first `set_feedback` `SELECT` opens the transaction, then `wait_for_pending_finalize` waits up to 10 s with it open.
  - My scanners for this class: `scratch-net/session_awaits.py`, `scratch-net/session_fn_awaits.py`.

## 4. Looked wrong, actually fine

- **Redis commands do not retry.** redis-py 8.1's `Redis()` default is `Retry(10 attempts, jittered backoff)`, which with a 5 s socket timeout could stretch one command toward a minute. But `core/redis.py:22-28` uses `from_url`, which builds the pool without that object, so connections get `Retry(NoBackoff(), 0)` (`.venv/.../redis/asyncio/connection.py:666-682`; the client docstring: "When 'connection_pool' is provided - the retry configuration of the provided pool will be used"). Commands fail within 5 s, as the module intends.
- **No ORM N+1.** Relationships exist (`models/orm/chat.py:58,61,104`, `user.py`) but nothing iterates them; under async SQLAlchemy a lazy load raises `MissingGreenlet` instead of silently issuing N queries. No `selectinload` is needed anywhere (grep: none, none missing).
- **The turn's independent loads already overlap.** User, chat, quota probe, window and model health are one `gather` (`turn_load.py:157-166,245-253`); greetings skip the window (`:235-243`); the mode session only touches the wire for three message shapes (lazy checkout). The user-row insert overlaps the prompt build and the provider's time to first token (`turn_prep/prepare.py:199-222`, `stream_paths.py:265-270`).
- **No extra model call on an ordinary turn.** The tool loop runs only for search, unsolved maths, photo lookup or image generation (`tool_loop/selection.py:75-120`); an obvious lookup searches without a selection round (`tool_loop/rounds.py:106-128`); the web-search classifier is off in production (`fly.toml` `WEB_SEARCH_CLASSIFIER_ENABLED=false`); the heuristic pre-stream search is skipped while the tool loop is on (`web_search/augment.py:64-70`), so Tavily runs once per search turn on one reservation (`web_search/search_cache.py:30-103`).
- **Every outbound call is bounded.** LiteLLM stream: connect, per-chunk idle and wall-clock limits (`gateways/litellm_gateway.py:311-382`); structured/tool/vision/embedding calls under `asyncio.timeout` (`structured_completion.py:152-155`, `tool_completion.py:176`, `vision_completion.py:55-59`, `embedding_gateway.py:66`); httpx pooled clients with named timeouts (`gateways/http_client.py`; PubChem 10 s, Tavily 12 s, Mathpix, speech); R2 boto3 connect 5 s / read 20 s / 3 attempts with backoff (`storage_gateway.py:179-183`); Redis socket 5 s; DB connect 10 s, command 120 s, pool 5 s.
- **Retries are deliberate.** Background calls retry once on a *different* alias (`litellm_gateway.py:56-111`); quota settle backs off 0.1/0.2 s (`turn_settle.py:241-254`); chat fallbacks happen only before the first visible token (`litellm_gateway.py:200-271`).
- **Maths reader and word-problem model calls before the first token** are bounded (2.5 s and 3 s, one retry on a second provider) and documented (`core/settings/stem.py:30-45`); they run only after the regex reader has already failed.
- **Embedding fan-out** is batched and bounded (ES-16, `embedding_gateway.py:88-115`).
- **Start-up REST calls are cheap** (measured): `GET /auth/me` warm 0 SQL; `GET /chats` 2 parallel queries; `GET /chats/{id}/messages` 2 statements + `EXISTS` + one `GET`; `GET /home` cached by generation (`modules/home/service.py:122-157`). Exceptions are NET-01 (`/memories`, `/memories/documents`) and NET-09.
- **Finalize passes** are CPU-only for a plain reply; photo, picture, SymPy, PubChem and reminder I/O happen only when the reply carries those fences. The answer photo's search starts when its fence closes, overlapped with the stream (`images/answer_photo.py:59-68`).
- **Follow-up questions** go out after `done` without holding the next message (`ws_turn.py:234-245`), are cached per message for 7 days (`related_prompts.py:138-171`), and are skipped when the user turned them off (`stream_pipeline.py:85-100`).

## 5. Open questions for the team

1. What is the production RTT from Fly `iad` to the Neon pooler in `us-east-2`, and does the pooler drop idle client connections? The first sizes NET-03; the second decides whether its "ping only idle connections" option is safe.
2. Facts per active user (p50/p95) and average `memories` row size in production — sizes NET-01 (`SELECT avg(pg_column_size(m.*)) FROM memories m`).
3. Which Upstash plan (pay-as-you-go or fixed)? Decides how much NET-05 is worth.
4. Do the RAG searches (`ORDER BY embedding <=> :q LIMIT 6` with `WHERE user_id = …`) use the global HNSW index — post-filtering, which can return few or no rows without pgvector's iterative scans — or the btree, computing exact distances over all of the user's chunks? Needs `EXPLAIN (ANALYZE, BUFFERS)` on production-sized data (overlaps SCALE-06).
5. The web-search cache is per user since #1100 (`web_search/search_cache.py:163-165`). Was that for privacy or for the daily Tavily count? A short shared cache for queries with no personal or location words (news, scores, weather in a named city) would save Tavily calls.
6. The WebSocket sends one frame per provider chunk (`ws_turn.py:68-78`); coalescing to ~30–50 ms frames would cut frames several-fold on long replies. Worth it only if the phone side (another auditor) shows the render cost.
7. `_load_prior_user_messages` and the gap count race the user-row insert (NET-04). Is the subject reader meant to see the current line among the "prior" lines?

## 6. Scratch files (parse-only)

- `tmp/code-audit/raw/scratch-net/session_awaits.py`, `session_fn_awaits.py` — `ast` scans for network-like awaits inside session blocks / session-taking functions.
- `tmp/code-audit/raw/scratch-net/loop_awaits.py` — awaited DB/Redis calls inside loops.
- `tmp/code-audit/raw/scratch-net/embed_sizes.py` — arithmetic for the stored size of one 1536-dim vector (JSON 34,151 chars; zlib 15,111 bytes; pgvector text ≈ 21 KB at 9 significant digits; binary 6,148 bytes).
- The selectable model count (6) was read from `apps/api/app/models/model_catalog.py:130-240` and matches the measured `ZRANGE` ×6.
