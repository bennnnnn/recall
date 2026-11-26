# Complexity and context tickets (2026-11-22)

A read-only audit for bad Big-O across `apps/api` and `apps/mobile`, plus a review of how a
turn's prompt is built (history, summary, memory, tokens, caching). Written for an agent
**with the development database**: the audit container had none, so every database
finding is from reading code, and none was checked with `EXPLAIN`.

How to read a ticket: **Verified** means someone ran or measured it; **Read** means it
comes from reading the code only. Line numbers are as of commit `acbf9dd3` on branch
`ccr-ecc2e3f1-9wi2qd`. Each ticket names a test to add so the fix stays fixed.

## Already done on this branch (verify with the database, do not redo)

Commits `237ee6b3` and `acbf9dd3`: the prompt's history starts at the summary's edge
(`prompt_context.load_anchored_history`), and the compress job folds only past a trigger
(`context_window.FoldRule`). See CLAUDE.md Golden Rule 3. Settings:
`context_token_budget` 32k, `history_max_messages` 80, fold at 24k tokens or 64 messages,
back to 12k / 24. The readers' `recent_message_window` stays 20.

To do with the database:

1. Run the full suite (`uv run pytest`). Without a database: 52,915 passed. The 98 failed
   and 397 errors all fail on the commit before the change too (most with connection
   refused to 127.0.0.1:5432, or a test that needs a migrated schema), so no failure is
   known to come from the change. The run also asks: does any test that needs the
   database fail now?
2. Run the decision diff (CLAUDE.md, Testing): `decisions dump` on `main` and on this
   branch, then `diff`. Expected: no decision changed (all 47 golden prompts were byte for
   byte the same).
3. With real traffic, run `uv run python -m app.tests.behavior.context_cache_eval logs`
   over the API log. It shows, per model, the share of input read from the provider's
   cache and the app's token estimate over the provider's count (`est_prompt_tokens` on
   the `turn_cost` line is new).
4. Only if Claude turns (`free-chat`) show cache reads past the stable system message,
   turn on `prompt_cache_history_breakpoint_enabled`. It is off because it is unconfirmed
   that OpenRouter keeps the context system message after the history in place for
   Anthropic. If OpenRouter lifts it into the system prompt, every history mark is a
   1.25x cache write that is never read.
5. CI's `speed` job (`scripts/bench_api.py`) runs on a pull request; the change adds one
   indexed read of older rows on turns of chats longer than 20 unsummarized messages.

Simulation (`context_cache_eval sim`, real code, no database). On the owner's 80-message
chat: 39 messages verbatim instead of 20; prompt share a prefix cache can serve 48% →
85%; input cost at a cached price of 25% $0.094 → $0.056.

---

## P0: denial of service on the event loop

### CX-1. `writing_request_kind` is quadratic and can run on the event loop — Verified

- **Where:** `apps/api/app/modules/turn_reading/writing_kind.py:334-341`
  (`_find_direct_writing_followup`), `:207-221` (`_starts_direct_writing_request`),
  `:245` (`_next_sentence_tail`).
- **Problem:** for each sentence it runs ~10 regex `.search()` calls over the whole rest
  of the message, though it only needs a match starting near the sentence's start
  (`match.start() <= prefix_end`). `_next_sentence_tail` also copies
  `text[:next_index].lower()` and runs an unanchored `re.search(...$)` at every period.
  O(sentences × n).
- **Measured** (`writing_request_kind.__wrapped__`, a message opening "How do I write a
  cover letter? " followed by "The sky is blue today. " repeated):

  | chars | 4k | 8k | 16k | 32k (the message cap) |
  |---|---|---|---|---|
  | seconds | 0.09 | 0.34 | 1.51 | 6.60 |

- **Why it is P0:** it is `@kept_per_turn` (`core/readings.py:99`), not `@reading`: when
  the pool read times out (3 s, `subject_read_timeout_seconds`) it is computed again on
  the event loop, and never declined. One 32k message stalls every turn on that machine
  for ~7 s. Loop-side callers: `chat/prompt_format.py:113,159,235`,
  `chat/tool_loop/live_denial.py:93`, `chat/generic_closer.py:73`,
  `chat/prompt_constants/writing.py:137`, `chat/prompt_sections.part_shape_hints` (`:451`,
  once per plan part; each part is a different text, so the memo misses). Also slow
  through it: `is_email_or_message_request`, `is_writing_deliverable_request`,
  `needs_rich_context`, `_looks_like_smart_continuation`, `should_include_profile_email`.
- **Fix:** match only the candidate sentence's head: `.match`, or a search bounded to the
  first sentence's end. Find the next sentence end with one forward scan, not a slice and
  re-search per period.
- **Test:** a 32k message of that shape returns in under 50 ms
  (`writing_request_kind.__wrapped__`), plus the module's existing cases unchanged.

### CX-2. Other loop-side readers that slow down on long messages — Read + timed by the auditor

| Where | Pattern | Measured at 32k | Fix |
|---|---|---|---|
| `modules/memory/commands.py:429-452` (`_is_command_at`; via `:296-321`, `:341-363`, `:366-392`) | per marker position copies `lowered[:index]`, rfinds per clause break, splits the whole rest to read 3 words; `_withdraws_the_ask` splits again | 150-170 ms/call ("forget i asked, " repeated); `asks_to_remember` calls two | bounded windows: `before[-200:]`, `rest[:200]` |
| `modules/web_search/weather.py:33-49` (`WEATHER_NOT_A_FORECAST`) | `(…)\b.*\bweather` and `weather\b.*\b(…)`: unbounded `.*` per occurrence | 310 ms per `is_weather_request` on one 32k line; called several times a turn (`chat/prompt_context_hints.py:34`, `web_search/tool.py:122`, `recency.py:67`, `homework.py:18`) | `[^\n]{0,80}` or two separate word checks |
| `modules/chat/whole_question.py:172` (`_ASKED_SENTENCE`) | unanchored `[^.?!\n]*\?`: O(L²) on a long sentence with no "?" | 350 ms at 16k | anchor, or find "?" first. Low: only verified-solve maths turns |
| `modules/chat/worked_solution.py:288-311` (`_separators`, `_inside_a_closed_bracket`) | rebuilds the bracket map per `\|` | 0.13-0.26 s at 16k | build once per line. Low: short lines |

**Test for each:** a 32k input under a fixed time budget, in the module's test file.

---

## P1: data access (verify each with `EXPLAIN ANALYZE` on the dev database)

### DB-1. Search builds the whole hit set before LIMIT — Verified by reading

- **Where:** `modules/search/repository.py:116-139`. The title, file and message branches
  have no ORDER BY or LIMIT; LIMIT applies only after `union_all`, for every cursor page.
- **Impact:** a common word reads, joins and sorts every matching message the user has.
- **Fix:** give each branch `ORDER BY created_at DESC, id DESC LIMIT limit+1`, with the
  cursor predicate pushed into each branch.
- **Check:** `EXPLAIN ANALYZE` before and after on a user with ~10k messages and a common
  word.

### DB-2. To-dos are cut by LIMIT in topic order, and done ones are never deleted — Verified by reading

**Status: the cut is done in #2590, except as noted below.** A turn's reads (the prompt's
100, a chat's edits and the reminder fence's 500, live talk's snapshot) keep the rows a
turn needs most (`repository._needed_first`): open before done, an open one by its due
time's distance from now (upcoming and recently overdue ahead of stale ones, undated last),
then the most recently changed. Still open: done to-dos are never deleted.

- **Where:** `modules/todos/repository.py:55-77` (`list_for_user` orders by topic,
  sort_order, checked, created_at), called with limit 100 from
  `modules/todos/prompt_context.py:298` (chat prompt), 500 from
  `modules/todos/actions.py:249` and `modules/todos/reminder_writes.py:111` (duplicate
  checks in Python: `select_todos_for_prompt`, `_existing_open_match`). Data retention
  does not delete done to-dos.
- **Impact (a correctness bug):** past 100 rows, open and overdue to-dos in topics late in
  the alphabet are missing from the prompt; past 500, duplicate detection misses rows.
- **Fix:** filter `checked = false` (or recently done) and order by urgency in SQL before
  the LIMIT; find a duplicate with a `lower(content)` WHERE.
- **Test:** a user with 150 done to-dos in topic "a" and one overdue open to-do in topic
  "z": the prompt's section names it.

### DB-3..DB-8 — Read

| ID | Where | Problem | Fix |
|---|---|---|---|
| DB-3 | `modules/memory/writes_repository.py:92` | every memory write loads all the user's memory rows, superseded and muted ones too, which are never pruned | `WHERE status IN ('active','muted')`; retain or cap superseded history |
| DB-4 | `modules/memory/erase.py:59-72` (`purge_fact_chunks`), from `memory/repository.py:99,245` | deleting a topic runs two DELETEs per fact, each an exact cosine scan over up to 2000 chunks plus an ILIKE, in one request | one `DELETE … USING memories m WHERE m.id = ANY(:ids) AND c.embedding <=> m.embedding <= d` and one combined ILIKE |
| DB-5 | `modules/chat/turn_load.py:87`; `compaction.py` (`message_count`, `messages_page(offset=…)`) | `COUNT(*)` of the chat on every turn once the 20-row window is full; the compress job counts again and pages with OFFSET | keep `message_count` on `chats` (increment in finalize), or anchor by a `(created_at, id)` cursor |
| DB-6 | `modules/conversation/chunks_repository.py:78-90` (`prune_beyond_window`) | `ORDER BY created_at DESC OFFSET 2000` on every `message_index` job; the `(user_id, created_at)` index lacks `id`, so ~2000 heap fetches | read the cutoff with `OFFSET 2000 LIMIT 1`, delete `created_at < cutoff`; or prune every Nth turn |
| DB-7 | `modules/notifications/push.py:332`, `modules/todos/due_reminders.py:228` | one UPDATE per delivered to-do, plus a `session.get(User)` per recurring one (a fresh session, so a real SELECT); ~200 round trips per 100-message Expo chunk, on the hour | **Done:** a chunk's pushes are marked in two statements (one stamps the one-off to-dos, one moves the recurring ones) after one read of their users' zones (`todos.mark_reminders_pushed`) |
| DB-8 | `modules/chat/finalize_registry.py:173` | waiting for the previous turn's finalize runs `EXISTS` every 50 ms for up to 10 s: up to 200 Upstash commands per wait | exponential backoff, or BLPOP on a completion key |

### DB-9..DB-15 — Read, low

| ID | Where | Problem | Fix |
|---|---|---|---|
| DB-9 | `modules/notifications/push.py:391`, `send_backoff.py:78-83` | per-to-do backoff hold, 2 Redis round trips each | one pipeline |
| DB-10 | `modules/attachments/repository.py:307-330` | gallery search ILIKEs every attachment's linked message plus a correlated subquery, no trigram | match `messages.search_text` through its trigram index |
| DB-11 | `modules/conversation/messages_repository.py:340,356` | no `(user_id, created_at)` index on messages; history backfill and account delete sort all the user's messages | replace `ix_messages_user_id` with `(user_id, created_at)` (still serves the cascade) |
| DB-12 | `modules/account/lifecycle.py:320` | `SCAN MATCH *<uuid>*` over the whole Redis keyspace per account delete (worker) | a per-user key-registry set, or user-prefixed keys |
| DB-13 | `background/billing_reconcile_scheduler.py:57` | one RevenueCat call + 0.2 s sleep + lock refresh per paid user, serially; no index on `users.plan`; past ~10k paid users a cycle outlasts the 3600 s interval | partial index `users(id) WHERE plan <> 'free'`, bounded concurrency, one lock refresh per batch |
| DB-14 | `conversation/chunks_repository.search_semantic` | exact scoring of up to 2000 vectors (~12 MB TOAST) per recall; deliberate (migration 0118) | if it shows in latency: lower `chat_history_rag_search_window` or iterative HNSW |
| DB-15 | `modules/conversation/service.py:152` (`edit_recent_reply`) | loads 30 full messages to find a substring | SQL `contains`, as `list_assistant_containing` does |

Already sound (checked, no ticket): no N+1 over chats, messages or memories on request
paths; no vector similarity in Python; message, chat, export and drawer paging is keyset
and capped; every cascade or SET NULL foreign key is indexed; reminder, retention and
analytics schedulers page by keyset over partial indexes.

---

## P1: mobile streaming (O(n²) over a reply)

**Status: done in #2555, except as noted below.** MX-1 to MX-7 were all real, and are fixed with
before/after numbers in the PR (bench: `components/markdown/__tests__/streamFlushBench.test.tsx`,
`STREAM_BENCH=1`). Do not redo them. What is still open:

- MX-2: a fence indented 4+ spaces (steps 10 and up, nested lists) still poisons the segment
  cuts, because strict passes read it as prose. So does a step line or heading inside a bare or
  maths fence, which `closeInterruptedMathFences` closes there. The worked-region part was left as it was:
  answer fences already end each region.
- MX-7: the prefix `startsWith` compares are left (memcmp). An open data fence is classified on
  every flush, because classifying it once would change its result as its body grows.
- MX-1: a `\(` inside inline code (`` `\(` ``) still holds the stable prefix until a `\)`, because
  some preprocess patterns (e.g. `normalizeImplicit`'s display-span regex) do not skip code spans,
  so skipping it in the scan is not proven safe yet.
- MX-6: fixed, but the gain is too small to measure.
- `eslint-plugin-regexp` is not added: `regexp/no-super-linear-backtracking` flags 54 places in
  23 files (see Tooling notes).

The text below is the audit as written.

n is the reply length (2-40k chars); a "flush" is one throttled UI update while a reply
streams (~30/s, `useStreamingDraft`), so 300-2000 per reply. `node_modules` was not
installed in the audit container: nothing here was run. Profile with the React DevTools
Profiler on a 20k-char reply.

### MX-1. One `$`, `\(` or `\[` freezes the stable prefix for the rest of the reply — Verified by reading

- **Where:** `apps/mobile/lib/markdown/preprocessStream.ts:268-298`
  (`scanStableMarkdownPrefix`). `inlineDollarOpen` toggles on any line with an odd `$`
  count and is carried across lines and paragraphs; `parenDepth`/`bracketDepth` likewise.
  It also counts `$` inside inline code (`` `$HOME` ``).
- **Trigger:** "a $300 deposit", a shell variable. `stableEnd` stays stuck until the next
  odd `$`, so the rest of the reply stays in the raw tail and is re-run every flush
  through `presentStreamTail`, `scanClosedBlocks` and `prepareStreamingMathText`
  (`lib/math/streaming.ts:71-127`: `out += text[i]` per char at :121, a copy of the rest
  per `$` in `unfinishedFormulaAt` at :62), then re-parsed by markdown-it and re-rendered
  as one live piece (`components/markdown/streamingEnd.tsx:120-130`).
- **Fix:** reset `inlineDollarOpen` (and the paren/bracket depths, for inline delimiters)
  at each line, consistent with the renderer's `readInlineMathSpan`, which already refuses
  a `$` span containing `\n`; skip `$` inside inline code.
- **Test:** streaming a reply with "a $300 deposit" in its first line, then 50 paragraphs:
  `stableEnd` advances past each closed paragraph.

### MX-2..MX-7 — Read

| ID | Sev | Where | Problem | Fix |
|---|---|---|---|---|
| MX-2 | High | `lib/markdown/segmentedPreprocess.ts:87-91,110-112`; `streamSegments.ts:83,166,179-193,211,223` | `state.poisoned` blocks cuts for the rest of the reply on any fence not at column 0 (```` ```bash ```` indented in a numbered step, a prose mention of ```` ``` ````), `<details`, Vega's `"$schema"`, `molecule3d`; a bold **Given**/**Required** blocks cuts for the region (`regionWorked`), so every worked maths reply. Then the full ~45-pass `preprocessMarkdown` re-runs on the growing open part per closed line, and a failed `tryCut` preprocesses it 3 times; `isWorkedReply(prefix.openRaw)` re-scans it per flush (`preprocessStream.ts:351`) | allow a cut after a fence indented ≤ 3 spaces that closes cleanly; treat a worked region as cuttable after its first closed maths block |
| MX-3 | Med | `lib/markdown/streamBlocks.ts:134,148` | one line matching `REFERENCE_DEFINITION_RE` (`[1]: https://…`, `[Note]: …`) drops every chunk: the whole reply re-parsed per flush | keep chunks before the definition; re-resolve references only in the live piece |
| MX-4 | Med | `features/chat/.../useAssistantMessageContent.ts:37` → `assistantMessageContent.ts:96-117`; `ChatMessageRow.tsx:67` → `emojiPlacement.ts:158-170` | per flush over the full text: `scanFences` split/join per fence, `JSON.parse` of untagged fences (`searchSources.ts:75-81`), 3-4 lower-cased copies (`scan.ts:179`, `tagPlacesJsonFences`), four `/\n{3,}/g` replaces; emoji placement's LESSON regex + split/map/join | run on the newly closed text only, or cache by prefix |
| MX-5 | Med | `useChatBulkActions.ts:60,107`; `chatListCache.ts:145`; `listSections.ts:112,200-202`; `useDrawerChatList.ts:336-338` | bulk archive/delete is O(k·n): `getCachedChat` copies every chat per lookup; each archive re-sorts the archived section with `Date.parse` twice per comparison and publishes once per chat; delete runs seven filters per chat, twice | one batched update with a Set/Map; parse dates once |
| MX-6 | Low-Med | `components/markdown/rules/lists.tsx:50-64`; `markdownAstHelpers.ts:268-302` | per list item `listHasOpenTask(parent)` walks every item (O(items²)); `astSource(node)` serializes the item's subtree, again at every nesting level | compute both once per list node, cached on the node like `pathOf` |
| MX-7 | Low | `preprocessStream.ts:352`; `segmentedPreprocess.ts:69-72,110`; `lib/preview/htmlPreviewBundle.ts:190`; `streamBlocks.ts:94`; `lib/fence/dispatch.ts:77-135`; `MarkdownContent.tsx:89-108` | smaller O(n) per flush: `split("\n").pop()` of the whole stable prefix (use `lastIndexOf`), prefix `startsWith`/slice compares, an open data fence re-classified with `JSON.parse` per flush, a settled reply re-preprocessed each time its row mounts | `lastIndexOf`; keep offsets instead of re-comparing; classify once per fence; a small LRU by message id + length |

Already sound: tokens never copy the messages array (`chatTurnFrames.ts:192` buffers into
a draft store); rows other than the live one do not re-render; closed fences are reused;
no catastrophic-backtracking regex in the parsers.

---

## P2: in-memory, backend, smaller

| ID | Where | Problem | Fix |
|---|---|---|---|
| CX-3 | `modules/memory/consolidation.py:83-90` (`facts_need_consolidation`) | all-pairs Jaccard over active facts, re-tokenizing both texts per pair (~22k tokenizations at 150 facts): 82 ms on every GET `/memories`, on the loop (`enqueue_policy.list_user_memories` → `request_consolidation`) | token sets once per fact; compare within a type (~20x) |
| CX-4 | `modules/chat/worked_stream.py:65-74,182-198` | worked-layout turns rebuild `_done + …` and `startswith(self._sent)` over the whole reply per token: 59 ms for a 64k reply vs 16 ms without | keep a sent offset |
| CX-5 | `memory/consolidation_workflow.py:74-90` (`_duplicate_pairs`) | same all-pairs pattern as CX-3, in a background job | same fix |

---

## P2: prompt cost (from the context review)

Measured with `render_rules` on 2026-11-22 (characters / 4; the real tokenizer could not
be downloaded): the fixed system message ~1.7k tokens; this kind of turn's rules ~1.3k
("hi"), ~3.4k (cover letter), ~6.5k (ordinary question), ~8.3k (maths); context after the
history ~1.0-1.3k.

- **PC-1. The rules cost as much as the conversation.** An ordinary question sends ~8k
  tokens of rules; the real 80-message chat's history is ~3.5k. The biggest cost and
  latency lever. Slimming needs the sweeps and the decision diff to show nothing changed.
- **PC-2. Memory is cheap to widen.** `memory_inject_max_chars` 1500 (~15 facts, ~400
  tokens) of up to 150 stored. 3000 chars / 25 facts costs ~400 tokens a turn. Check with
  `memory_recall_eval` before and after.
- **PC-3. Calibrate `estimate_tokens`.** `max(chars/3.6, words×1.35)`; text ≥ 40%
  non-Latin letters counts 1 token per char, which may be well off for Ethiopic. Compare
  with the provider's `prompt_tokens` via `context_cache_eval logs` (the
  `est_prompt_tokens` column), per locale if possible.
- **PC-4. This kind of turn's rules sit before the history.** A change of turn kind
  (coding → maths) breaks the cached prefix for the whole history. Moving them after the
  history would keep the history cacheable, but placement can change model behaviour:
  measure with the battery and sweeps first.

---

## Tooling notes

- Backend ReDoS is already gated in CI (`scripts/check_regex_redos.py` with regexploit).
- Mobile has no regex backtracking lint: `eslint-plugin-regexp`
  (`regexp/no-super-linear-backtracking`) would catch MX-class regressions in CI. Version 3.3.3
  flags 54 places in 23 files today. 4 are exponential, at three places: `lib/codeTokenize.ts:434`,
  `lib/copyBlock.ts:49` and `lib/math/latexStructure.ts:287` (twice). Fix those before turning it on.
- For a suspected quadratic, time it at 4k, 8k, 16k, 32k: ~4x per doubling is O(n²).
