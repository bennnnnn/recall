# Streaming latency (TTFT) review — 2026-09-12

**Goal:** first visible token in 1–2s.
**Scorecard target today:** non-tool chat TTFT < 2s p50, < 6s p95 (`docs/PRODUCT_SCORECARD.md`).
The gap this review closes is that the scorecard only ever covered **non-tool** turns —
tool-gated turns had no budget, and they were the slow ones.

Scope: `services/chat/` (entry → prep → pipeline), `gateways/litellm_gateway.py`,
`services/tool_loop.py`, quota/Redis, DB pooling, and the mobile socket path.

## Verdict

The prompt-assembly path is **already well optimised** — memory, RAG, integrations,
web search and chemistry all run concurrently under `asyncio.gather`, short-lived
sessions keep Neon connections off the gather, and the mobile client pre-warms its
WebSocket on draft. That is not where the seconds were.

The seconds were in **one blocking LLM round that generated an answer nobody ever saw**,
plus **a second blocking LLM call** in front of it. Both are fixed here. What remains is
model choice and region placement, which are your calls, not code bugs.

## Measured before assuming

Two things I expected to be problems and measured instead:

- **Sync intent regexes** (web-search, math, image, calendar, email, settings, time,
  lightweight detection — 12 gates on one message): **p50 0.57ms, p95 0.64ms**.
  Negligible. Not a factor even on a shared vCPU.
- **Redis on the reserve path**: `reserve_usage` is a single `INCRBY`; the `EXPIRE`
  only fires on the first reserve of the day. Already 1 RTT. Not a factor.

I could **not** measure end-to-end TTFT against live providers from the review
sandbox. The changes below are structural — they remove a whole generation from the
critical path — but the numbers to confirm them are in `chat_stream_timing`
(see *Verifying* at the end).

## The critical path, as traced

```
ws.py → stream_entry.stream_chat_response
  ├ gather(wait_for_pending_finalize, load user+quota)       1 DB + 1-2 Redis
  ├ recent window + prior_count + turn mode                  1 DB session
  ├ image lookup / image gen intent                          CPU only (~0.1ms)
  ├ prepare_chat_turn
  │   ├ persist user row                        ← backgrounded, not awaited ✅
  │   └ build_stream_prompt_context
  │       ├ Phase A gather: prompt+memory+RAG | instant reply | model health
  │       └ Phase B gather: integrations | web | chemistry | calendar-write
  └ stream_and_finalize
      ├ run_tool_loop_path      ← ⛔ THE PROBLEM (see F1/F2)
      └ run_llm_token_stream    ← first visible token
```

Steps 1–4 are parallel and bounded. Step 5 was serial, unbounded by anything except
an 8s timeout, and **discarded its own output**.

---

## Findings

### F1 — The tool-selection round generated a full answer, then threw it away · **Critical** · fixed

`tool_loop._run_tool_rounds_bound` called `litellm_gateway.complete_with_tools` with
`stream=False` and `max_tokens=settings.max_output_tokens` (**8192**), fully awaited
before `run_llm_token_stream` ever started.

The loop reads **only `tool_calls`** from that response. When the model answers
without tools — the common case whenever the heuristic gate fires on an ambiguous
turn — the code does this:

```python
tool_calls = msg.get("tool_calls") or []
if not tool_calls:
    break          # ← the whole generated answer is discarded here
```

…and the caller then streams the *same answer again* from scratch.

So TTFT on any tool-gated turn was:

```
full non-streaming generation (up to 8192 tokens)  +  stream TTFT
```

At DeepSeek's throughput a 400-token answer is several seconds of pure waste, and the
per-chat prepare lock is held for all of it. The existing code comment claimed
"ordinary TTFT when this is round 1" — that is only true of the second call; the first
one had already been paid for.

**Fix:** the probe now *streams* (`_probe_tool_calls_streaming` in
`litellm_gateway.py`). It accumulates `tool_calls` deltas, and the moment content
arrives that can only be prose it aborts the stream and returns "no tools". A no-tool
turn now costs **one provider TTFT (~300ms), not a whole generation**. Tool-calling
turns are unaffected — tool-call deltas arrive first and are short.

Guarded by `mcp_tool_loop_stream_probe_enabled` (default **on**); flip it off to get
the blocking round back. A `<think>` preamble is read through rather than mistaken for
an answer, and the probe commits to prose on the first real token *after* `</think>`.

### F2 — That blocking round used price-weighted provider routing · **High** · fixed

`_litellm_kwargs(settings, route)` — no `latency_sensitive`. The comment said
"Background jobs and tool-selection calls keep the default routing", but this call is
not background: it sits directly in front of the user's first token. OpenRouter's
default route is price-weighted, so this round was routed to the *cheapest* endpoint
while the visible stream right behind it asked for `{"provider": {"sort": "latency"}}`.

**Fix:** the probe is now `latency_sensitive=True`, matching the visible stream.

### F3 — No token cap on a round whose output is always discarded · **High** · fixed

Related to F1: even in the fallback (non-streaming) path there was no reason to allow
8192 tokens. Added `mcp_tool_loop_probe_max_tokens` (default **640**) — enough for the
widest tool-argument list, and it bounds the think-block read-through on the streaming
path. `complete_with_tools` now also returns `finish_reason` so a genuine "no tools"
is distinguishable from a cap-truncated one.

### F4 — The web-search classifier was a second serial LLM call before the stream · **High** · fixed

`run_tool_loop_path` awaited `should_web_search(...)` — an LLM classifier with a
**4s** timeout (`web_search_classifier_timeout_seconds`) — inline, before deciding
whether to run the tool loop at all. On exactly the ambiguous turns where the sync
heuristic was unsure, that was up to 4s of dead time in front of the first token.

**Fix:** `build_stream_prompt_context` now resolves the classifier **concurrently**
with the other Phase B fetches and hands the verdict down as
`StreamContext.web_search_classified`; the gate consumes it instead of awaiting a
fresh one. Gated to exactly the turns that would have been classified later (not
lightweight, no instant reply, no sync-heuristic hit, no math), so this overlaps
existing work rather than adding new calls. The gate still classifies for itself if
nothing was precomputed.

### F5 — The tool-loop phase was invisible in timing logs · **Medium** · fixed

`TurnTimingTracker` marked `prompt_assembled` and `augment_done` but nothing around
the tool loop, so all of F1+F2+F4 landed inside `post_prompt_first_token_ms` — which
the tracker's own comment warns is "not provider latency". In practice that made the
single largest TTFT component look like provider slowness. Added `tool_loop_start` /
`tool_loop_done` phases.

---

## Not fixed — your call

### F6 — `smart-chat` is a reasoning model, and its reasoning is thrown away · **High**

`model_catalog.py`: `smart-chat` → `deepseek/deepseek-r1`. R1 emits a long chain of
thought *before* any answer content. The gateway discards it on both routes:

```python
_ = on_reasoning            # "CoT is not forwarded"
stripper = _ThinkStripper() # inline <think> blocks dropped
```

So on `smart-chat` the user stares at nothing for the entire reasoning phase — commonly
10–40s. **No amount of backend tuning fixes this**; it is inherent to routing a
reasoning model into a latency-sensitive chat slot while showing none of its output.

Three honest options:
1. **Re-point `smart-chat` at a fast non-reasoning model** and keep R1 as an explicit
   opt-in pick. Best TTFT, changes product meaning of "smart".
2. **Show a reasoning summary** while it thinks. `on_reasoning` is already plumbed
   through WS (`build_reasoning_event`) — only the gateway drops it. Conflicts with
   the "no status theater" rule in CLAUDE.md, though reasoning is real output, not theater.
3. **Accept it** and exclude reasoning aliases from the TTFT SLO explicitly.

I did not pick one — it is a product decision, not a bug.

### F7 — API region and database region do not match · **Medium**

`fly.toml`: `primary_region = "iad"` with the comment *"Neon DB is in us-east-2"*.
`iad` is AWS **us-east-1** (Virginia); the database is **us-east-2** (Ohio). That is a
cross-region hop (~15–20ms RTT) on every DB round trip, and the TTFT path makes
several. CLAUDE.md says us-east-2 was chosen deliberately for Neon Storage, so the
cheaper fix is moving the Fly app to `cle`/`ord`, not moving Neon. Worth ~100–250ms.

### F8 — `pool_pre_ping=True` costs a round trip per checkout · **Low–Medium**

`core/db.py` pings (`SELECT 1`) on every pool checkout. The TTFT path takes roughly
3–6 checkouts (some parallel), so this is ~2–3 extra serial RTTs — cross-region, per F7,
that compounds. It is defensive against Neon's idle-connection closes, so do **not**
flip it blind: measure with F7 fixed first, then consider dropping it with a shorter
`pool_recycle`.

### F9 — Memory retrieval makes a live embedding HTTP call on the prompt path · **Low–Medium**

`memory/retrieval.py` → `embedding_gateway.get_or_embed_query` on a query-cache miss,
bounded at `memory_query_embed_timeout_seconds` (2.0s), followed by a pgvector query.
It runs inside the Phase A gather, but `build_prompt_messages` is the long pole of that
gather, so the embed is effectively on the critical path for any first-time query.
Bound is already sane; the win would be pre-warming embeddings for likely queries or
trimming the timeout to ~1s and leaning on the type-priority fallback.

---

## Expected effect

| Turn type | Before | After (structural) |
|---|---|---|
| Lightweight / instant reply | already fast | unchanged |
| Ordinary chat, no tool gate | prompt gather + stream TTFT | unchanged (already ~1–2s) |
| **Tool-gated, model wants no tool** | **discarded full generation + stream TTFT** | **one probe TTFT + stream TTFT** |
| Tool-gated, ambiguous web search | **+ up to 4s serial classifier** | classifier overlapped, ~0 added |
| Tool-gated, tool actually runs | round + tool + stream | round is latency-routed now |

1–2s is reachable for everything except `smart-chat` (F6), which needs a product
decision, and is helped further by F7.

Industry reference points for the bar: sub-1s TTFT is the target for user-facing chat
and sub-500ms is considered ideal, with p95 typically 1.6–3.2× p50 — so a 2s p50 goal
implies budgeting for a ~4–6s p95. DeepSeek V3's own TTFT is ~300ms, which is *not*
the constraint here; the app's own pre-stream work was.

## Verifying

`chat_stream_timing` now carries `tool_loop_start` / `tool_loop_done`. After deploy:

- `tool_loop_done - tool_loop_start` is the cost F1/F2/F4 addressed. Expect it to drop
  from seconds to roughly one provider round trip on turns that take no tool.
- `post_prompt_first_token_ms` minus that delta is real provider TTFT.
- Split the p50/p95 by `model` — `smart-chat` will stay an outlier until F6 is decided.

To roll back just the probe change: `MCP_TOOL_LOOP_STREAM_PROBE_ENABLED=false`.

## Changed in this pass

- `core/config.py` — `mcp_tool_loop_probe_max_tokens` (640),
  `mcp_tool_loop_stream_probe_enabled` (on)
- `gateways/litellm_gateway.py` — `_probe_tool_calls_streaming`,
  `_merge_tool_call_deltas`, `_content_commits_to_prose`; `complete_with_tools`
  dispatches to the probe, is latency-routed, and returns `finish_reason`
- `services/tool_loop.py` — probe cap instead of `max_output_tokens`
- `services/chat/turn_prep/context.py` — classifier resolved in the Phase B gather;
  `web_search_classified` on `TurnPromptBundle` / `StreamContext`
- `services/chat/stream_pipeline.py` — consume the precomputed verdict; tool-loop
  timing phases
- Tests: 5 new gateway probe tests (abort-on-prose, delta assembly, think-block
  read-through, post-`</think>` abort, flag-off fallback) + tool-loop gate coverage
  for the precomputed verdict
