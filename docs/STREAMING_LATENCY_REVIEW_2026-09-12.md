# Streaming latency review and corrections — 2026-09-12

The supplied review correctly identified a discarded tool-selection completion on
the path to the first answer token. Its proposed first-prose streaming abort is
unsafe: an assistant may send prose before a tool call, and a token-limited response
can contain incomplete tool arguments. This implementation uses an explicit,
bounded tool decision instead.

## Changes

- Tool selection requests a function call, including a private no-tool option.
  It does not ask for the user's answer. The gateway consumes that decision;
  the ordinary answer stream remains responsible for visible text.
- Tool decisions use `MCP_TOOL_LOOP_PROBE_MAX_TOKENS` (default 1024) and
  latency-prioritized routing.
  Incomplete or ambiguous selections cannot invoke tools. Provider usage remains
  available because the decision response is consumed to completion.
- Eligible web-search classification overlaps other prompt preparation work.
  Preparation and streaming share the actual tool eligibility rule, and both
  positive and negative verdicts are reused. The classifier's deadline covers
  spend checks and accounting as well as the provider call.
- Timing records the tool phase and the start of the visible stream separately.
  Interrupted tool phases still record their end.
- A failed or empty history-retrieval query embedding is no longer attempted
  again after the concurrent context gather. Successful embeddings are reused.

## Corrections to the supplied review

- **No production latency numbers were measured.** The quoted 300 ms provider
  latency, 10–40 second reasoning delay, regional savings, and 1–2 second result
  are not established for Recall. Tests verify behavior and scheduling, not a
  production p50 or p95.
- **Overlapping classification does not remove it from the critical path.**
  Preparation still waits for the slower branch. Savings depend on how much
  independent work can overlap. Checked-in `fly.toml` already disables the
  classifier; deployed environment overrides were not inspected.
- **Default OpenRouter routing is price-weighted, not always the cheapest.**
  Latency sorting is a routing preference, not a response-time guarantee.
  [OpenRouter provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)
- **Reasoning is still work even when hidden.** `smart-chat` maps to DeepSeek R1,
  and the gateway keeps internal reasoning out of the visible answer. Changing
  that alias changes the product's reasoning behavior and needs measured quality,
  cost, and latency comparisons. Tool selection already substitutes a fast alias
  for reasoning aliases. [OpenRouter reasoning parameters](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
- **A region comment does not establish deployed topology.** Fly lists `iad` as
  Ashburn and `ord` as Chicago; its current region list does not include `cle`.
  No machines or databases were moved.
  [Fly regions](https://fly.io/docs/reference/regions/)
- **Pre-ping protects stale pooled connections.** Its behavior is dialect-specific
  and fresh connections can skip it. Recycle is age-based and does not replace
  protection against arbitrary disconnects. Pool settings remain unchanged.
  [SQLAlchemy disconnect handling](https://docs.sqlalchemy.org/en/20/core/pooling.html#disconnect-handling-pessimistic)
- **Memory and history retrieval are distinct.** Checked-in Fly configuration
  already sets the memory embedding timeout to 0.75 seconds; the Settings default
  is 2 seconds. Memory candidates are ranked in Python. The fixed duplicate retry
  was in chat-history retrieval, which has its own embedding deadline. These
  embedding deadlines cover provider work; cache IO has separate deadlines.

## Validation and measurement

Regression tests cover bounded tool decisions, complete arguments before execution,
no-tool decisions, usage accounting, classifier eligibility and verdict reuse,
interrupted phases, and a single history-embedding attempt. Run the repository gate
with `./scripts/dev.sh check` against an isolated test database.

After deployment, compare `chat_stream_timing` across equivalent model and turn
cohorts. `tool_loop_done - tool_loop_start` measures the tool phase.
`gateway_to_first_token_ms` measures from `gateway_request_start` to the first
answer token. It also includes retries, provider reasoning, and whitespace
filtering; it is not pure provider TTFT. Subtracting tool
time from `post_prompt_first_token_ms` does not isolate provider latency because
reserve top-up and other work can occur in that interval.

Use client latency measurements for the user-visible goal, since the server timer
does not include client upload, transport, and rendering. The current scorecard
remains non-tool chat below 2 seconds p50 and 6 seconds p95; this patch does not
claim those targets have been achieved in production.

## Follow-up: first-token delay on a plain cubic graph

The exact request `graph y = x^3` selects `smart-chat` under Auto. Its verified
graph already exists before streaming, but the original direct-math policy
excluded graphs, so it still waited for a model answer. A local synthetic check
produced the 96-point graph in 11–49 ms after imports; this excludes DB, network,
and process startup and does not explain every millisecond of the reported turn.
Using the actual spawned-worker path on the same machine took 0.38–1.34 seconds
for the first three requests, then about 11 ms warm. Existing startup warmup only
warms one of three worker slots; calls after that warmup took 0.21–0.38 seconds
before settling to about 11 ms. Those timings still exclude DB and provider IO.

Plain, fully matched single-function plot requests now emit the existing canonical
graph through the direct-reply path. No tool-selection or visible-answer model call
is needed. A trailing newline closes the mobile streaming fence immediately.
Explanations, additional tasks, unmatched ranges, and image requests retain model
handling. Model aliases are unchanged.
