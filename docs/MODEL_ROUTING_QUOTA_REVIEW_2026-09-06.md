# Recall — Model Catalog, Routing & Core Text-Chat Quota Review (Sep 2026)

Scope: `services/model_catalog.py` (+ `models/model_catalog.py`, the real catalog data),
`services/routing.py`, `services/plan.py` (pool/fallback selection), the core per-user
daily-token quota path in `services/quota.py` + `services/chat/turn_resources.py` +
`services/chat/post_turn.py`, and `gateways/litellm_gateway.py`'s fallback/retry behavior.
Explicitly **not** in scope: speech/image-gen/live-talk quotas (reviewed separately), and
`docs/CODEBASE_REVIEW_2026-08.md` finding **C1** (turn quota/lock lifecycle architecture —
re-verified as closed below, not re-litigated).

Reviewed at `cursor/cross-domain-review-2026-09-05`.

---

## A. Verdict

**The routing/quota foundation is sound, and one previously-claimed-fixed bug is not
actually fixed.** C1 from the Aug 2026 review is genuinely closed — `turn_resources.py`'s
async context manager now owns acquire → refund-on-`BaseException` → release for both
remaining turn types (the third entry point, chat-message *edit*, no longer exists — it was
removed as banned UX), and a test (`test_stream_chat_releases_lock_when_prepare_fails`)
asserts exactly one refund. The weighted-reserve → top-up → real-usage-`adjust_usage`
pipeline (`turn_resources.py` + `post_turn.py:finalize_stream_turn_db`) is a genuinely good
design: reserve a cheap content-only estimate, top up once the full prompt is known, then
reconcile against the provider's *actual* reported tokens after the turn completes — with a
retry-with-backoff on the reconciliation write itself. The model catalog is current: every
spot-checked OpenRouter slug (`z-ai/glm-4.7-flash`, `openai/gpt-5.5`, `qwen/qwen3.8-max`,
`moonshotai/kimi-k3`) resolves to a real, live listing, and `gpt-5.5`'s catalog price
matches OpenRouter's published rate exactly. Alias validation has a belt-and-suspenders
design (`KNOWN_MODEL_ALIASES` duplicated in `core/validation.py`, but pinned to the catalog
by an explicit equality test) and per-message model overrides are correctly plan-gated —
a free user cannot force a Pro-only alias, and chat fallback candidates never cross the
plan boundary.

**Two real defects, both new (not covered by the Aug review or the Aug 20 quota audit
PR #854):**

1. **`gateways/litellm_gateway.py`'s multi-alias fallback retry double-counts token
   usage.** When a model streams a whitespace-only reply (the code's own comment calls
   this "a common flaky provider quirk") and the system silently retries a fallback alias,
   the discarded attempt's provider-reported token usage is *not* discarded — it stays in
   the shared `usage` dict and gets added to the fallback's usage, so the user is charged
   for both the invisible failed attempt and the delivered reply.
2. **The H1 fix from PR #854 ("heal Redis/DB drift") is dead code.** `quota.py`'s
   `heal_usage_drift` is fully implemented and documented as the exact self-heal
   `post_turn.py`'s own comment says will run "on next turn" — but it is never called from
   anywhere in the app. If `adjust_usage` fails 3/3 retries after a successful commit
   (transient Redis blip), the daily counter under-counts real usage for the rest of the
   UTC day with no automatic recovery path, silently granting the user free quota.

Both are quiet, low-frequency, and asymmetric in who they hurt (#1 over-charges, #2
under-charges) — which is exactly why neither would show up in a smoke test, and why
neither has a regression test today.

---

## B. What's working (don't "fix" these)

- **C1 (turn quota/lock lifecycle) is closed.** `services/chat/turn_resources.py`'s
  `turn_resources()` async context manager is the single acquire/refund/release owner for
  both `stream_chat_response` and `stream_regenerate_response`
  (`services/chat/stream_entry.py:139,302`); the third entry point C1 flagged
  (`stream_edit_response`, and its `pre_reserved`/`held_chatprep_lock` transfer hack) no
  longer exists in the codebase — message edit/resend was removed as banned UX
  (`chat-ux-bans.mdc` §11). `refund()` is idempotent (`_refunded` flag,
  `turn_resources.py:46`) and fires exactly once on any `BaseException` exit
  (`turn_resources.py:92-96`), with a passing regression test
  (`tests/services/test_chatprep_lock.py:151-199`, `refund.assert_awaited_once()`).
- **Reserve → top-up → reconcile is real, not just claimed.** Initial reservation is a
  cheap content-only estimate (`weighted_reserve_tokens`, `turn_resources.py:161-174`);
  once the full prompt (memory, history, RAG, attachments) is assembled, `top_up_reserve_for_prompt`
  (`turn_resources.py:194-223`) tops up the difference — never down, so the reservation is
  always ≥ the real prompt size going into generation. After the stream ends,
  `finalize_stream_turn_db` (`post_turn.py:86-140`) computes the actual weighted total from
  the *provider's reported* `usage["input"]`/`usage["output"]` (falling back to a local
  estimate only if the provider didn't report usage) and reconciles with `adjust_usage`
  (`post_turn.py:224-248`), with a 3-attempt backoff retry on the reconciliation write.
- **Atomic reserve/rollback is race-free.** `reserve_usage` (`quota.py:224-259`) and
  `_reserve_daily_slot` (`quota.py:124-148`) use a single atomic Redis `INCRBY` followed by
  an over-limit rollback — not a check-then-act pair — so concurrent turns (same user,
  different chats) cannot both slip under the cap; the loser's slot is always given back.
  `test_quota_enforced` and `test_reserve_usage_rejects_over_limit` cover this.
- **Overshoot is capped, not open-ended.** `record_usage`/`adjust_usage` clip the daily
  counter at `daily_limit` (`quota.py:296-304`) so one turn's real usage exceeding its
  reservation can't push the counter past the cap and make the *next* turn's
  `reserve_usage` under-report remaining quota. Covered by
  `test_record_usage_caps_overshoot_at_daily_limit` / `test_adjust_usage_caps_overshoot`.
- **The model catalog is current, not stale.** Spot-checked against live OpenRouter
  listings: `z-ai/glm-4.7-flash`, `openai/gpt-5.5` ($5/$30 per 1M — exact match to
  `models/model_catalog.py:151-152`), `openai/gpt-5.5-pro`'s sibling slug pattern,
  `qwen/qwen3.8-max`, and `moonshotai/kimi-k3` are all real, live OpenRouter model ids.
- **Alias validation can't silently drift.** `core/validation.py:KNOWN_MODEL_ALIASES` is a
  hand-maintained mirror of `CATALOG`'s ids (needed because Pydantic schema validators
  can't import the services layer), but `test_known_model_aliases_match_catalog`
  (`tests/services/test_model_catalog.py:61-64`) asserts set-equality — a new/removed
  catalog entry that isn't mirrored fails CI, not production.
- **Plan gating on per-message overrides is correct.** `plan._override_pool` /
  `resolve_user_model_override` (`plan.py:97-131`) rejects (`UnknownModelOverrideError`,
  mapped to a client-safe `error` event in `stream_events.py:163-164`) any alias not in the
  user's own plan pool — a free user cannot force `smart-chat` or any other pro-only alias
  by passing it in the WS/SSE request body. `chat_fallback_models` (`plan.py:165-215`)
  builds its candidate list from the *same* `allowed_model_ids` pool, so a fallback can
  never cross the plan boundary either (a free user's `free-chat` only falls back to other
  free-tier models).
- **No provider API key or raw provider error ever reaches the client.** `routers/models.py`
  returns only a boolean `available` (key-presence check), never the key itself.
  `error_payload_for_exception`'s catch-all (`stream_events.py:174`) is a generic message —
  provider exception text never leaks into the WS/SSE error frame.
- **`fallback_used` / `resolved_model` are wired end-to-end**, from
  `run_llm_token_stream` (`stream_pipeline.py:209-215`) through `_DONE_PAYLOAD_KEYS`
  (`stream_events.py:32-44`) into both `stream_end` and `done`. Per `chat-ux-bans.mdc` §4
  the mobile client must not surface these as a chip — that's a deliberate, already-shipped
  product decision, not a gap in this review.
- **Auto-routing heuristic has real breadth of test coverage**, including a dedicated
  ReDoS-safety regression test for the code-fence detector on adversarial input
  (`tests/services/test_routing.py:145-169`).

---

## C. Findings — ranked

---

**Q1 — Fallback retry in `stream_chat_completion` double-counts provider token usage onto the user's daily quota**
**Severity:** P1 · **Area:** quota / gateway · **Effort:** S

**Evidence:** `apps/api/app/gateways/litellm_gateway.py`
- `stream_chat_completion` (l.294-378) builds `aliases = [model_alias, *(fallback_aliases or [])]`
  (l.313) and loops over them (l.316). The **same** `usage` dict is passed by reference into
  every attempt (l.330: `usage=usage` inside the `_stream_chat_once(...)` call), with no
  reset between attempts.
- `_apply_usage` (l.191-202) is additive: `usage["input"] = usage.get("input", 0) + int(prompt)`.
  It is called once per chunk inside `_stream_chat_once`, including for a whitespace-only
  reply — the code's own comment (l.317-319) documents that providers commonly finish a
  response with the correct final-chunk usage stats *even when the content is empty
  whitespace* ("common flaky provider quirk").
- When an attempt never produces a non-whitespace token, `started` stays `False`
  (l.321,334-337) and the attempt is discarded — `stream_chat_completion` logs "returned no
  content" (l.348) and raises `ModelUnavailableError`, retrying the next alias (l.359-371).
  **The tokens that discarded attempt already added to `usage` are never removed.**
- Real call site: `services/chat/stream_pipeline.py:167-176`
  (`run_llm_token_stream`) passes a shared `usage: dict[str, int]` into
  `litellm_gateway.stream_chat_completion(..., usage=usage, fallback_aliases=ctx.fallback_models, ...)`.
  That same `usage` dict flows straight into `post_turn.py:93-113`'s
  `finalize_stream_turn_db`, which computes `weighted_total` from it and charges the user
  via `adjust_usage` (`post_turn.py:231-237`).
- `ctx.fallback_models` is populated for real turns, not a theoretical parameter:
  `plan.chat_fallback_models(user, settings, model, unhealthy=unhealthy)`
  (`turn_prep/context.py:388`) returns up to 2 candidates by default
  (`plan.py:165-170`, `max_fallbacks=2`) whenever the user's enabled pool has other models.
- **Confirmed no test exercises this path**: every fallback test in
  `tests/test_gateways.py` (l.638-816: `test_stream_chat_completion_retries_fallback_alias`,
  `..._retries_when_primary_yields_no_tokens`, `..._retries_when_primary_yields_whitespace_only`)
  mocks `_stream_chat_once` directly and never passes a `usage` dict, so `_apply_usage`
  never runs in any of them — the accumulation behavior across a retry is untested.

**Why it matters:** the retry-on-empty-reply behavior exists specifically because empty
replies are a known, recurring provider flakiness (per the code's own comment) — meaning
this is not a rare edge case, it is the exact scenario the fallback path was built to
handle. Every time it fires, the user is billed against their 100k/500k daily cap for a
reply they never saw, on top of the reply they did see, for a provider failure that was
entirely outside their control. This is quota "double-charging" of the exact kind flagged
as in-scope for this review (concurrent-request races were the suspected cause; the actual
cause is simpler — accounting state that isn't reset between sequential attempts in the
*same* request).

**Recommended fix:** clear (or don't mutate) `usage` for a discarded attempt. Smallest
change: give each attempt its own local `usage` dict inside the loop and only merge it into
the caller's `usage` once that attempt is the one that returns (`started == True`) — i.e.
move the `usage=usage` argument to `usage=attempt_usage` (a fresh `{}` per iteration at
l.320, alongside `pending`/`started`), then `usage.update(attempt_usage)` (or add) right
before the `return` at l.344-347. If the product wants total *provider spend* to reflect
failed attempts too (a legitimate, separate concern for `record_global_spend`'s $ kill
switch), track that separately — don't conflate it with the user-facing daily token cap.

**Do not:** remove the whitespace-only retry behavior itself — it is correct and
documented; don't change the "mid-stream failure after real tokens started" no-retry rule
(l.361-364) — that's deliberately correct (avoids concatenating partial + full replies).

---

**Q2 — H1's Redis/DB drift heal (`heal_usage_drift`) is fully implemented but never called; the "next turn will heal it" comment is false**
**Severity:** P1 · **Area:** quota · **Effort:** S

**Evidence:**
- `apps/api/app/services/quota.py:193-221` defines `heal_usage_drift`, whose docstring
  states its exact purpose: *"if Redis holds a stale value lower than the DB total
  (repeated `adjust_usage` failures, partial outages, manual key edits), seeding is
  skipped forever for that UTC day and the user can exceed daily limits. This compares the
  two and raises Redis to `max(redis, db_total)`."*
- `apps/api/app/services/chat/post_turn.py:37-63` (`seed_usage_from_db`, called at the
  start of every turn via `stream_entry.py:151-162,307`) calls **only**
  `has_daily_usage_key` (skip if the key exists at all) and `seed_usage_if_missing` (which
  only writes when the key is **absent** — `quota.py:173-190`, `SET NX`). Neither branch
  ever calls `heal_usage_drift`.
- `post_turn.py:224-248` (`finalize_stream_turn_db`'s post-commit reconciliation) retries
  `adjust_usage` 3× with backoff, and on persistent failure logs: *"adjust_usage failed
  after finalize commit; Redis may be inflated — heal_usage_drift on next turn will correct
  the drift from the DB total"* (l.244-248, comment referenced again at l.228 before the
  retry loop). **That healing never happens** — `grep -rn "heal_usage_drift("` across
  `apps/` returns exactly one hit: the function's own definition.
- Confirmed via `git log -S"heal_usage_drift"`: this function was added in PR #854
  ("fix: auth + models + quota pipeline audit (H1-H2, ...)") explicitly as fix **H1**
  ("heal Redis/DB drift when Redis key exists"). It shipped as dead code — H2 (the
  `adjust_usage` retry, same PR) is wired in and working; H1 is not.
- Zero test coverage: `grep -rn "heal_usage_drift" apps/api/app/tests` returns no matches.
- Secondary issue if it *were* wired in: the implementation is not actually atomic. Its own
  docstring claims *"Atomic via a Lua compare-and-set so concurrent turns can't
  double-count"* (l.206-207), but the body (l.212-219) is a plain `GET` followed by a
  conditional `SET` — a textbook TOCTOU window, not a Lua script. A concurrent
  `adjust_usage`/`reserve_usage` `INCRBY` landing between the `GET` and the `SET` would be
  silently overwritten.

**Why it matters:** this is the one documented, intentional self-heal for quota
under-counting, and today it provides zero protection. The failure mode it exists to guard
against — a Redis blip during the post-commit reconciliation write, which is exactly the
kind of transient infra hiccup a 3-attempt-with-backoff retry is designed for the *rare*
case it still doesn't cover — leaves the daily counter permanently low for the rest of the
UTC day (the key still exists, so `seed_usage_if_missing`'s absent-only check never fires).
The user effectively gets free quota with no code path to correct it before the key's
48-hour TTL naturally expires. This is the "never-charged" counterpart to Q1's
"double-charged."

**Recommended fix:** call `heal_usage_drift` from `seed_usage_from_db` on the
key-exists branch (the function already has the DB total in hand at that call site via
`usage_repo.get_total_for_date`) — cheapest correct fix, reuses the DB round-trip that
branch already avoids paying on the hot path only when healing is actually needed (e.g.
throttle to once per N turns or gate on a recent `adjust_usage` failure flag, so this
doesn't reintroduce the per-turn DB read that M9/the hot-path comment in
`seed_usage_from_db` deliberately avoids). Separately, replace the GET-then-SET body with
a real Lua script (`EVAL`) doing the compare-and-set in one round trip, so the docstring's
atomicity claim becomes true — or rewrite the docstring to stop claiming atomicity it
doesn't have. Add a test that asserts a lower stale Redis value is raised to the DB total,
and that a *higher* Redis value (legitimate concurrent usage since the DB read) is never
lowered.

**Do not:** call `heal_usage_drift` unconditionally on every turn — that reintroduces the
per-turn Neon round-trip the hot-path skip in `seed_usage_from_db` was written to avoid
(see the M9/hot-path comment at `post_turn.py:49-52`); gate it behind "key exists but a
recent reconciliation failed" or a coarse time-based throttle.

---

**Q3 — Fallback failure/health attribution always blames the primary alias, even when a later fallback is what actually failed**
**Severity:** P2 · **Area:** gateway / observability · **Effort:** S

**Evidence:** `apps/api/app/gateways/litellm_gateway.py:359-375` — when the loop exhausts
all aliases without any producing content, the final raise is:
```python
raise ModelUnavailableError(
    _CHAT_MODEL_UNAVAILABLE_MSG,
    failed_alias=model_alias,
) from exc
```
`model_alias` here is `stream_chat_completion`'s own parameter — the **original primary**
— not `alias` (the loop variable holding whichever model actually raised last) and not
`exc.failed_alias` (which `_stream_chat_once` already set correctly to the alias that just
failed, l.372 vs the `exc` raised from `_stream_chat_once` internally). So if `smart-chat`
succeeds partially-empty and `free-chat` (its fallback) is the one that times out, the
client-visible error (`error_payload_for_exception`, `stream_events.py:167-173`, which
forwards `exc.failed_alias` verbatim as `failed_model`) still reports `smart-chat` as the
failed model.
The same primary-attribution bug affects model health telemetry:
`stream_pipeline.py:196-208` (`run_llm_token_stream`) records a health sample keyed by
`stream_meta.get("model_alias") or requested_model` — `stream_meta["model_alias"]` is only
ever set on the **success** path (`litellm_gateway.py:345-346`), so a total failure across
2-3 aliases always attributes the unhealthy sample to `requested_model` (the primary),
never to whichever fallback candidate(s) actually errored. Over time this means
`model_health.py`'s rolling health tracking (used by `chat_fallback_models`'s `unhealthy`
set, `turn_prep/context.py:378-388`) systematically mis-scores the primary model as
unhealthy while a genuinely-unhealthy fallback candidate keeps getting selected as a
"healthy" fallback.

**Why it matters:** this quietly undermines the model-health-based fallback exclusion
(M6 from PR #854) over time — the more a *fallback* model is actually the one failing, the
more the health system penalizes the (innocent) primary instead, making the system less
likely to correctly route around the genuinely bad model on subsequent turns.

**Recommended fix:** in the final-exhaustion raise, use `failed_alias=alias` (the loop
variable — the model that just failed) instead of `model_alias`; in
`run_llm_token_stream`, catch `ModelUnavailableError` around the token-stream loop and use
`exc.failed_alias` (falling back to `requested_model` only if unset) when recording the
health sample on total failure.

**Do not:** change what `failed_alias` means on a **mid-stream** failure after partial
content (`stream_chat_completion.py:361-364`, no-retry path) — that one is already correct
(it's the model that was actually streaming).

---

**Q4 — Minor: catalog price drift vs. live OpenRouter rates feeds the cost estimate and the global-spend kill switch with stale numbers**
**Severity:** P3 · **Area:** model catalog · **Effort:** S

**Evidence:** `models/model_catalog.py:174-183` prices `kimi-k3` at
`input_price_per_m=2.60, output_price_per_m=13.00`; live OpenRouter pricing (confirmed via
web search against multiple current pricing trackers) is `$3.00 / $15.00` per 1M — roughly
13-15% higher than the catalog. The module docstring already flags this as expected
(`models/model_catalog.py:7`: *"approximate OpenRouter rates — update as needed"*), and it
does not affect the user-facing token quota (which is pure token counts × `quota_multiplier`,
not dollars), but it does directly under-count `estimate_cost_usd` → `record_global_spend`
(`quota.py:482-497`), the one dollar-denominated safety valve in this system
(`daily_global_spend_usd` kill-switch, `quota.py:499-508`).

**Why it matters:** low severity since it's a known, documented approximation and doesn't
touch per-user quota correctness — but a kill switch that's meant to cap real spend is only
as tight as its weakest priced model, and pricing on frontier/new models moves fast (this
review is at Sep 2026; several of these models were listed as "Added 3 Sept 2026").

**Recommended fix:** no urgent action; consider a periodic (quarterly, or CI-flagged)
pricing refresh pass against the OpenRouter models API rather than manual updates on an
unknown cadence.

**Do not:** treat this as a per-user quota bug — it isn't one; `quota_multiplier` (the
number that actually gates the daily token cap) is unaffected by this drift.

---

## D. Weak / unwanted / missing inventory

| Item | Status | Evidence | Recommend |
|---|---|---|---|
| Fallback-retry usage accounting | **Bug** — double-counts a discarded attempt's tokens | `litellm_gateway.py:313-343` shared `usage` dict across retries | Fix now (Q1) |
| `heal_usage_drift` (H1, PR #854) | **Bug** — dead code, comment claims it runs | `quota.py:193-221`, `post_turn.py:37-63,225-248`, zero call sites | Fix now (Q2) |
| `heal_usage_drift` atomicity | Weak — docstring claims Lua atomicity; body is GET+SET | `quota.py:206-219` | Fix alongside Q2 |
| Fallback/health failure attribution | Weak — always blames the primary alias | `litellm_gateway.py:372-375`, `stream_pipeline.py:196-208` | Fix now (Q3) |
| Catalog $ pricing (kimi-k3 spot-checked) | Weak — ~13-15% stale vs. live OpenRouter | `models/model_catalog.py:174-183` vs. live listings | Periodic refresh (Q4), no urgency |
| Turn quota/lock lifecycle (Aug review C1) | **Resolved** | `turn_resources.py`, edit path removed, test asserts single refund | Keep as-is |
| Reserve → top-up → reconcile design | Solid | `turn_resources.py:161-256`, `post_turn.py:86-140` | Keep as-is |
| Atomic reserve/rollback (`_reserve_daily_slot`, `reserve_usage`) | Solid | `quota.py:124-148,224-259` | Keep as-is |
| Overshoot capping (`record_usage`/`adjust_usage`) | Solid | `quota.py:296-304`, tests pass | Keep as-is |
| Model catalog → OpenRouter slugs | Solid, current | spot-checked 4 slugs live | Keep as-is |
| `KNOWN_MODEL_ALIASES` / catalog sync | Solid — enforced by test | `test_known_model_aliases_match_catalog` | Keep as-is |
| Plan-aware alias override gating | Solid | `plan.py:97-131,165-215` | Keep as-is |
| Pydantic layer accepts internal (non-selectable) aliases in `model` field | Cosmetic — always rejected downstream by `_override_pool`, never exploitable | `core/validation.py:8-35` (unfiltered by `selectable`), `plan.py:97-106` (real gate) | Optional: narrower client-facing validator; not urgent |
| `last_error` fallthrough in `stream_chat_completion` | Dead code, harmless | `litellm_gateway.py:314,377-378` — every loop iteration returns or raises | Optional cleanup, not urgent |
| `reserve_usage`'s double-Redis-failure rollback | Minor robustness gap — second retry unguarded, could raise raw `RedisError` instead of `RedisUnavailableError` | `quota.py:248-254` | Optional: wrap the retry in the same try/except |

---

## E. Test coverage gaps (tie back to findings)

- **No test asserts token-usage accounting across a fallback retry.** All of
  `test_stream_chat_completion_retries_*` in `tests/test_gateways.py` mock `_stream_chat_once`
  directly without a `usage` dict, so `_apply_usage`'s accumulation behavior across attempts
  is completely untested — this is exactly why Q1 shipped unnoticed. Add a test that passes
  a real `usage` dict through a mocked `_stream_chat_once` that reports usage on a discarded
  whitespace-only attempt, then asserts the final `usage` matches only the winning attempt.
- **Zero tests for `heal_usage_drift`** (confirmed via `grep -rn "heal_usage_drift" apps/api/app/tests`
  → no matches) — add tests for: stale-lower-than-DB gets raised, key-absent is a no-op
  (that's `seed_usage_if_missing`'s job), and a concurrent higher value is never clobbered
  once the implementation is made atomic.
- **No test exercises `failed_alias`/health-sample attribution when a *fallback* (not the
  primary) is the one that fails.** Every existing fallback test has the primary fail and
  the fallback succeed, or the primary succeed; add a case where `fallback_aliases[-1]`
  raises on the final attempt and assert `failed_alias` / the recorded health sample name
  the actual failing alias, not the primary.
- **Routing (`services/routing.py`) and plan-pool selection (`services/plan.py`) have solid,
  broad table-driven coverage** (`tests/services/test_routing.py`,
  `tests/services/test_plan.py`) — no gap found there.
- **Quota math (`services/quota.py`) has solid coverage** for the pure Redis
  reserve/refund/adjust/cap functions (`tests/services/test_quota.py`) — the gap is
  specifically in the two integration seams above (fallback retry, drift healing), not in
  the quota primitives themselves.

---

## F. Explicit non-goals (per task scope)

- **Re-litigating C1** (turn quota/lock lifecycle architecture) — verified closed, not
  re-reported.
- **Speech/image-gen/live-talk quota** — out of scope; already reviewed separately.
- **The cancellation-unsafe-refund (`except Exception` vs `BaseException`) pattern** — swept
  elsewhere in this review series. Noted in passing: `turn_resources.py:94` already uses
  `except BaseException`, correctly. No new instance of the narrower-`except` bug found in
  this scope.
- **Auto-routing heuristic tuning** (which phrases trigger `smart-chat`) — this is product
  behavior with its own extensive test suite; not reviewed for "correctness" beyond
  confirming the tests pass and the pool-filtering logic around it is sound.
