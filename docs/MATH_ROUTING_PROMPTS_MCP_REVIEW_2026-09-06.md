# Recall — Math Model-Routing, Prompt-Engineering & Tool-Loop Integration Review (Sep 2026)

Scope: model routing for math turns (`services/routing.py`), math prompt hints and
their selection logic (`services/chat/prompt_constants/math.py`,
`services/chat/prompt_builder.py`), slim/rich turn-prep gating
(`services/chat/turn_prep/mode.py`), the owned MCP tool loop's SymPy integration
(`services/tool_loop.py`, `services/mcp/sympy_adapter.py`, `services/chat_tools.py`,
`gateways/mcp/registry.py`), and the `calculating` stream-status phase
(`services/chat/stream_status.py`). This is a "final pre-launch audit" of the math
feature's routing/prompt/tool-loop layer specifically — **not** a re-audit of
`services/mcp/sympy_adapter.py`'s RCE/sandbox surface (closed and covered by
`docs/MCP_TOOL_LOOP_SECURITY_REVIEW_2026-09-06.md`, one quick re-check only, see §C
item M1) and **not** a re-audit of `services/math_fence.py`'s rewrite/densify/cap
engine or `services/physics_solver.py`'s formula correctness (covered in depth,
concurrently, by `docs/MATH_FENCE_PHYSICS_REVIEW_2026-09-06.md` — referenced where
this review's findings intersect with theirs, not duplicated).

Reviewed at `cursor/cross-domain-review-2026-09-05` tip `6da97671` (2026-09-06).
`/workspace/apps/api/.venv/bin/python`, SymPy 1.14.0. Every claim below was run
against the actual code (script/command shown); none are inference-only.

---

## A. Verdict

**Test suite: green, and it actually targets this scope.** All 177 tests across the
six requested files pass; 38 of them match `-k "math or sympy or symbolic"` and pass
individually. No regressions, no skips, no xfails hiding a known-broken path (exact
commands and counts in §C's evidence, repeated in the "swept and clean" section).

**The routing claim ("math turns get the smart model") is real for a bare math
question, but `_verified_math_stays_fast()`'s exception is scoped to substrings of
the message, not to "the whole message is this trivial computation" — so a
multi-part turn where a genuinely hard, non-math question happens to share the
message with a one-line arithmetic/factorial ask gets silently kept on the fast
model.** `needs_symbolic(content)` correctly evaluates the *entire* message and
would route "explain Rayleigh scattering" to `smart-chat` on its own. But
`_verified_math_stays_fast`'s "what is X op Y" and factorial checks use `in`
(substring-anywhere) tests against the full cleaned content, not a fullmatch or a
check that the arithmetic *is* the whole ask — so as soon as any part of a longer
message looks like "what is 9 * 7" or contains a factorial cue, the whole turn is
flagged "stays fast," even when the rest of the message is a hard, non-math,
non-verified question. Reproduced twice with two independent trigger paths (arithmetic
substring, factorial-combinatorics substring); both route a compound
math-trivia + hard-conceptual question to `free-chat` instead of `smart-chat`. See
**R1** (P1).

**The tool loop's `has_verified_math` gate is an all-or-nothing switch scoped to the
message, not to the specific sub-problem that got verified — so an incorrect or
partial pre-stream heuristic match disables the model's own SymPy tool for the
*entire* turn, including parts the heuristic never touched.** `extract_math_intent`
is first-match-wins across ~30 intent extractors; a multi-part ask can bind to the
wrong extractor for a fragment of the message (reproduced: "graph y=x^2 and also
solve 3x = 9" is parsed as the single intent `vertical, point_x=9.0` — a vertical
line `x=9`, silently discarding both the graph and the actual equation). If that
misparsed intent still "verifies" (SymPy has no way to know the extraction itself
was wrong), `ctx.verified_math` becomes non-`None`, and `turn_needs_tool_loop(...,
has_verified_math=True, ...)` returns `False` unconditionally — the model never gets
the SymPy tool for this turn at all, even to fix the parts the heuristic silently
dropped. This is **not** the double-computation "race" the task brief hypothesized
(the two paths are in fact mutually exclusive by this same gate, so results never
disagree — see "swept and clean") — the actual bug is the opposite failure mode: a
wrong single-fragment match suppresses verification for everything else in the turn.
See **R2** (P0 — this is the direct "math powerhouse, error-free" promise failing
silently, with no error surfaced anywhere).

**The "formula emit rule" (no model-emitted `` ```geometry ``/`` ```graph ``/backticked
`$...$`) is prompt-only for the geometry/graph half and has zero server-side
enforcement when there is no canonical fence to substitute in — a model that
hallucinates a schema-valid but entirely fabricated diagram (wrong numbers, but
syntactically well-formed JSON) is shipped to the user completely unmodified,
indistinguishable from a real solver-verified diagram.** Reproduced: a fabricated
` ```geometry ` block with invented width/height/area passes through
`validate_math_fences(content, verified=None)` byte-identical because
`_replace_fence`'s only guard for the "no matching canonical" branch is
`_validate_geometry`, which checks **shape**, not **truth** — see
`math_fence.py:477-481`. This is the same root-cause class (schema-valid,
unverified, unmarked, indistinguishable from verified) as
`docs/MATH_FENCE_PHYSICS_REVIEW_2026-09-06.md`'s **F6** (their trigger is the
Nth-fence-beyond-cap; this review's trigger is simpler and more common — the very
first fence of a kind, whenever the heuristic/tool-loop produced no matching
canonical type at all, e.g. any geometry ask the extractor doesn't cover). Two
independent reviews finding the same class of gap through different triggers is a
strong signal this needs to be fixed as a single change (validate-or-strip on *any*
unmatched geometry/graph fence, not just densify/cap edge cases). The backtick-around-
`$...$` half of the rule is also unenforced server-side, but is fully mitigated
client-side today (mobile's `unwrapProseMathBackticks`) — flagged as lower severity
because a second (web) client sharing this API, per `CLAUDE.md`'s stated future
direction, would not inherit that client-side fix. See **R3** (P0 for the diagram
half, P2 for the backtick half).

**The `calculating` status is genuinely consistent across both paths — the task
brief's hypothesized "sometimes no indicator at all" UX gap does not exist.** Both
the pre-stream heuristic (`fetch_web_and_tools`) and the tool-loop SymPy call emit
`on_status("calculating", ...)` *before* the SymPy work starts, not after — so the
event always reaches the client ahead of (or concurrent with) the actual computation,
regardless of how fast that computation finishes. See "swept and clean."

**`MATH_SOLVER_HINT` and `MATH_TUTORING_HINT` cannot conflict because they are never
independently selected — they are an unconditional bundle with `MATH_INTENT_HINT`
whenever `math_intent` is true, and their content is complementary (formatting vs.
diagram vs. tutoring-behavior), not contradictory.** The real hint-selection gap is
different from what the brief hypothesized: `_math_viz_intent()` calls
`needs_symbolic_math(query_text)` **without** `has_image_attachment=True`, so for
camera-math submissions whose extracted kind is anything other than
equation/system/inequality (rectangle, circle, triangle, statistics, graph,
calculus, limit — i.e., most non-algebra homework photos), the caption text alone
does not trip `needs_symbolic`, so the three richer math hints are skipped for that
turn even though `build_math_augmentation` (called correctly with
`has_image_attachment=True`) *did* inject a verified system block. The baseline
`SHORT_MATH_SAFETY_HINT` — which does carry the core "don't emit ```geometry/
```graph, don't recompute a verified value" rules — is still present unconditionally
on this code path, so this is a hint-richness gap (missing diagram-description and
Socratic-tutoring guidance), not a total absence of guardrails. See **R4** (P2).

**Everything else is genuinely solid**: `invoke_validated`'s Pydantic gate is real
and rejects malformed tool args before they reach the adapter; the sympy-tool
canonical-fence plumbing (`_fence_data` → `ToolResult.data["canonical_fence"]` →
`tool_loop._canonical_from_tool_result` → `VerifiedMathBlock`) is the exact same
shape the pre-stream heuristic path produces, so a tool-loop-invoked SymPy call is
consumed identically by `validate_math_fences`, not through a second, differently-
behaved path; the `mcp_tools_enabled` legacy pre-stream MCP round explicitly refuses
to touch math (`chat_tools.py:35-41`) specifically to avoid double-injecting a
verified-math block; and the RCE sandbox in `math_service/parse.py`'s
`_reject_unsafe_expr` is unchanged and still in place.

---

## B. What's working (don't "fix" these)

- **Test suite is real and targeted.** `pytest app/tests/services/test_routing.py
  app/tests/services/test_tool_loop.py app/tests/test_mcp.py
  app/tests/services/test_chat_tools.py app/tests/services/test_prompt_builder_style_hints.py
  app/tests/services/test_enrich_final_content.py -q` → **177 passed** (10.05s). The
  same command with `-k "math or sympy or symbolic"` → **38 passed, 139 deselected**
  (9.67s), covering sympy dispatch/timeout/canonical-fence tests, tool-loop
  canonical-fence collection, chat-tools math-injection-once tests, and math-safety
  prompt-hint tests. No skips.
- **`needs_symbolic()` genuinely gates routing on the whole message, and the smart
  alias resolves correctly.** `_route_current_line` (`routing.py:296-319`) calls
  `needs_symbolic(content)` (not a truncated prefix or a keyword-only check) and
  routes to `model_catalog.auto_smart_alias()` when `needs_symbolic(content) and not
  _verified_math_stays_fast(content)`. A bare "solve 2x + 3 = 7" or "differentiate
  x^2" with no trivializing substring correctly resolves to `smart-chat`.
- **No double-computation / conflicting-results race between the pre-stream heuristic
  and the tool loop.** Traced precisely: `stream_pipeline.py:78` sets
  `has_verified = ctx.verified_math is not None` from the pre-stream result;
  `run_tool_loop_path` (`stream_pipeline.py:83-116`) passes that into
  `turn_needs_tool_loop(..., has_verified_math=has_verified, ...)`, which
  (`tool_loop.py:255`) returns `False` immediately whenever `has_verified_math` is
  `True` — the tool loop's `run_tool_rounds` (and therefore any tool-invoked SymPy
  call) **never executes** when the heuristic already produced a verified block. The
  replacement at `stream_pipeline.py:141-142` (`ctx.verified_math = tool_verified`)
  is consequently only ever reached when the heuristic produced *no* verified block
  in the first place — the two sources are mutually exclusive by construction, not
  racing. (The real bug this surfaces is R2 above — the gate being all-or-nothing at
  message granularity, not per-sub-problem.)
- **The `calculating` status fires before the computation, on both paths, with no
  gap.** Pre-stream: `prompt_builder.py:244-248` computes `needs_math` once, then
  `if needs_math and on_status is not None: await on_status("calculating")`
  **before** the `asyncio.gather` that actually runs SymPy — camera-math OCR path
  emits its own `on_status("calculating")` at `turn_prep/attachments.py:259-260`,
  also before the vision-extract call. Tool-loop: `tool_loop.py:414-416` emits the
  status via `_status_for_tool("sympy") == "calculating"` right before
  `mcp_registry.invoke_validated(...)`. Both call sites await the status callback
  before starting the work, so there is no scenario where SymPy computation
  completes before the "calculating" event is dispatched.
- **`MATH_SOLVER_HINT` / `MATH_TUTORING_HINT` do not conflict** — traced the only
  call site (`prompt_builder.py:691-702`): both are appended together with
  `MATH_INTENT_HINT` in a single `parts.extend([...])` whenever `math_intent` is
  `True`; there is no branch that selects one over the other. Read in full
  (`prompt_constants/math.py:1-123`): `MATH_INTENT_HINT` governs formatting/LaTeX
  shape, `MATH_SOLVER_HINT` governs diagram/fence prohibition plus a
  physics-specific "use the verified numbers" rule, `MATH_TUTORING_HINT` governs
  Socratic-vs-direct tutoring behavior when the user submits an answer to check —
  three orthogonal concerns, not alternatives.
- **The tool-loop SymPy path and the pre-stream heuristic path feed the exact same
  consumer with the exact same shape.** `sympy_adapter.py`'s `_fence_data()`
  (`:38-49`) writes `{"canonical_fence": ..., "canonical_answer": ...}` onto
  `ToolResult.data`; `tool_loop.py`'s `_canonical_from_tool_result` /
  `_canonical_answer_from_tool_result` (`:64-77`) read exactly those two keys and
  fold them into a `VerifiedMathBlock` (`:456-467`) with the identical field names
  `build_math_augmentation` uses for the heuristic path. `math_fence.py`'s
  `validate_math_fences` therefore treats a tool-loop-sourced verified block
  identically to a heuristic-sourced one — there is one consumer, one contract, not
  two subtly different code paths that could silently diverge in behavior.
- **The legacy `mcp_tools_enabled` pre-stream round explicitly excludes math to avoid
  double-injection**, and says so in its own comment: `chat_tools.py:35-41` — "Math
  intent is NOT handled here... This function used to also build and inject its own
  verified-math block, so a math-intent turn got the same... block injected twice."
  `augment_prompt_with_mcp_tools` also short-circuits entirely
  (`chat_tools.py:27`) whenever `mcp_tool_loop_enabled` is `True` (today's default),
  so this legacy path and the owned tool loop cannot both run for the same turn.
  Covered by `test_chat_tools.py::test_mcp_tools_does_not_handle_math_itself` and
  `test_augment_web_and_tools_injects_math_block_only_once` (both pass).
- **`invoke_validated` genuinely validates tool args against the adapter's Pydantic
  schema before invocation** (`registry.py:66-91`) — malformed JSON args return a
  `ToolResult` with an "Invalid arguments" message rather than raising into the tool
  loop or reaching `SympyAdapter.invoke` with unvalidated input.
- **RCE sandbox unchanged and still enforced.** `math_service/parse.py`'s
  `_reject_unsafe_expr` (re-read in full) still rejects `__`, `[`/`]`, non-decimal
  `.`, and anything outside `_SAFE_EXPR_CHARS` before `parse_expr`/`sympify` ever
  see the string — confirmed by direct read of the current function body (matches
  the version `MCP_TOOL_LOOP_SECURITY_REVIEW_2026-09-06.md` already closed) and by
  `test_mcp.py::test_sympy_adapter_rejects_rce_payload_via_solve` passing.

---

## C. Findings — ranked

### Routing

---

**R1 — `_verified_math_stays_fast()`'s "trivial arithmetic" checks are substring
matches against the whole message, not a check that the trivial math *is* the whole
message — a hard, non-math question sharing a message with a one-line calculation
gets silently routed to the fast model**
**Severity:** P1 · **Area:** routing · **Effort:** S

**Evidence:**

- `routing.py:346-368`, full function:
  ```python
  def _verified_math_stays_fast(content: str) -> bool:
      cleaned = prepare(content)
      if not cleaned:
          return False
      sig = combinatorics_signal(cleaned)
      if sig is not None and sig[0] == "factorial":
          return True
      if _BARE_ARITH.fullmatch(cleaned):
          return True
      lower = cleaned.lower()
      if "what is" not in lower or not any(ch.isdigit() for ch in cleaned):
          return False
      if not any(op in cleaned for op in ("+", "-", "*", "/", "\u00d7", "\u00f7", "^")):
          return False
      return not has_algebraic_equation(cleaned)
  ```
  Only `_BARE_ARITH.fullmatch(cleaned)` requires the *entire* cleaned content to be
  the arithmetic expression. The "what is X op Y" branch (lines 363-368) requires
  only that `"what is"` and a digit and an operator character appear **anywhere** in
  `cleaned`, with no check that they're part of the same clause or that nothing else
  substantive follows. `combinatorics_signal` is likewise a whole-content scan, not
  scoped to a leading/isolated clause.
- Reproduced (`.venv/bin/python`):
  ```python
  from app.services.routing import route_chat_model, _verified_math_stays_fast
  from app.services.math_text_match import needs_symbolic

  q1 = "What is 9 * 7? Also, can you explain why the sky is blue in terms of Rayleigh scattering, including the wavelength dependence?"
  needs_symbolic(q1)              # True
  _verified_math_stays_fast(q1)   # True  <-- should be False; most of q1 is not verified
  route_chat_model(q1)            # 'free-chat'  (smart alias is 'smart-chat')

  q2 = "What is 5 factorial? Also, why do stars appear to twinkle at night but planets do not?"
  needs_symbolic(q2)              # True
  _verified_math_stays_fast(q2)   # True
  route_chat_model(q2)            # 'free-chat'
  ```
  Both reproduced live against the current tree; output shown is the actual
  `python -c` output, not inferred.
- `_SMART_TRIGGERS` (`routing.py:21-57`) has no generic "explain/why" trigger by
  design (explicit comment: "broad words like why/explain route too often to the
  strong model") — so there is no independent escalation path rescuing these
  examples once `_verified_math_stays_fast` has already claimed the turn for "fast."

**Why it matters:** `needs_symbolic(content)` correctly flags the whole message as
math-adjacent and would route to `smart-chat` on its own — the intent of
`_verified_math_stays_fast` (per its own docstring: "SymPy already covers these; a
reasoning model only writes a CoT essay") is sound *when the message is only that
trivial calculation*. But because the check is substring-anywhere, any multi-part
message that happens to contain a one-liner like "what is 9*7" or "what is 5
factorial" downgrades the entire turn to the fast model — including the genuinely
hard, non-verified, non-math half of the question (Rayleigh scattering,
twinkling-stars physics) that the smart-model routing exists specifically to catch.
This is a common real-world phrasing pattern (a quick aside calculation attached to
a real question), not a contrived edge case, and it silently produces a weaker
answer for the part of the turn that actually needed the stronger model — directly
undermining the "math powerhouse, trusted" goal by degrading the *non-math* half of
a mixed turn whenever math happens to be present.

**Recommended fix:** scope `_verified_math_stays_fast` to require that the trivial
pattern accounts for (approximately) the *entire* message, not merely that it
appears somewhere in it — e.g. require the arithmetic/factorial substring match to
cover the full cleaned string modulo a short "what is ... ?" wrapper (a stricter
regex like `_BARE_ARITH` but tolerant of the "what is" prefix and trailing "?"),
and fall through to `smart-chat` whenever there is a non-trivial trailing clause
after the arithmetic/factorial expression. A simple heuristic that would already
catch both repro cases: reject the fast-stay exception if `len(cleaned)` minus the
matched trivial span exceeds a small character budget (e.g. ~15-20 chars), or if the
message contains a `_SMART_TRIGGERS`-independent "compound question" cue (a second
`?`, or `"also"` / `"and"` / `"why"` after the arithmetic clause).

**Do not:** delete `_verified_math_stays_fast` entirely to "fix" this by always
routing any math-adjacent turn to `smart-chat` — the exception is correct and
valuable for the common case of a genuinely standalone trivial computation (its own
existing tests, e.g. bare "1+1" / "4!", should keep routing fast); the bug is
specifically the lack of a "this covers the whole message" scope check, not the
existence of the exception.

---

### Tool-loop / verified-math integration

---

**R2 — A single mis-parsed math sub-problem "verifying" (even incorrectly) disables
the SymPy tool for the entire rest of the turn, because `has_verified_math` is an
all-or-nothing, message-level gate rather than scoped to the specific sub-problem
that was verified**
**Severity:** P0 · **Area:** tool-loop / math-augmentation · **Effort:** M

**Evidence:**

- `extract_math_intent` (`math_tools/extract.py`) is first-match-wins across roughly
  30 intent extractors run in a fixed order over the raw message — it returns as
  soon as any extractor matches, with no signal to the caller about whether other,
  unmatched math content remains in the same message.
- Reproduced (`.venv/bin/python`):
  ```python
  from app.services.math_tools import extract_math_intent
  extract_math_intent("graph y=x^2 and also solve 3x = 9")
  # kind='vertical' ... point_x=9.0 ... operation='graph'
  ```
  The extractor matched a vertical-line pattern on the `x = 9` fragment of "3x = 9"
  (misreading the coefficient) and returned before ever considering "graph y=x^2" or
  the actual linear equation "3x = 9". This is not a contrived string — "graph
  \<expr\> and also solve \<equation\>" is a completely ordinary multi-part homework
  phrasing.
- `stream_pipeline.py:78`: `has_verified = ctx.verified_math is not None` — this is
  a single boolean over the whole turn, derived from whatever
  `build_math_augmentation` (pre-stream) managed to extract and "verify," correct or
  not.
- `tool_loop.py:232-280`, `turn_needs_tool_loop`, line 255:
  `if has_instant_reply or lightweight or has_verified_math: return False` — reached
  before any other check (web search, image gen). Reproduced directly:
  ```python
  from app.services.tool_loop import turn_needs_tool_loop
  from app.core.config import Settings
  settings = Settings(mcp_tool_loop_enabled=True, math_tools_enabled=True)
  q = "graph y=x^2 and also solve 3x = 9"
  turn_needs_tool_loop(q, has_verified_math=True, settings=settings)   # False
  turn_needs_tool_loop(q, has_verified_math=False, settings=settings)  # True
  ```
  Confirms that once the heuristic marks the turn "has verified math" — regardless
  of whether that verification actually covers the user's real question — the tool
  loop (and therefore the `sympy` tool, and therefore any chance of a model-invoked,
  server-checked computation for the graph or the equation) is completely
  unavailable for this turn. The model is left to answer both parts from its own
  unverified reasoning, silently, with no note anywhere that verification was
  attempted and only partially succeeded.
- No test in `test_tool_loop.py` or `test_chat_tools.py` constructs a multi-intent
  message and asserts the tool loop still runs for the unaddressed part; all
  `has_verified_math=True` tests use single, correctly-parsed intents.

**Why it matters:** this is the sharpest gap between the product's stated goal
("math powerhouse... error-free... trusted by students") and what actually happens:
a common multi-part homework message can have its *entire* server-side verification
mechanism silently disabled by a wrong parse of one fragment, with the model's own
attempt to compute the rest going completely unchecked and no signal to the user or
to logs that this happened. Because `extract_math_intent`'s failure mode here is
silent (it doesn't raise or return partial/low-confidence results — it just returns
*a* `MathIntent`, right or wrong), there is no natural place today to detect "this
verification might have missed part of the ask" without a structural change.

**Recommended fix:** make `has_verified_math` (or an equivalent signal passed to
`turn_needs_tool_loop`) reflect whether the *entire* user message was addressed by
the heuristic extraction, not merely whether extraction produced *a* result. Two
independent options, either one closes the gap: (1) have `extract_math_intent`
(or a wrapping caller) detect multi-intent messages up front (e.g. via the existing
"and also" / multiple imperative-verb heuristics already used elsewhere in this
codebase, such as `_FOLLOWUP_CUES` in `routing.py`) and skip pre-stream heuristic
verification entirely for those messages, letting the tool loop's own per-call
SymPy invocations handle each part explicitly instead; or (2) keep the heuristic
single-shot extraction, but do not let it alone flip `has_verified_math=True` when
the extraction match consumed only a small span of a much longer/compound message
— require some additional confidence signal (e.g. the matched span vs. total length)
before disabling the tool loop.

**Do not:** widen the tool-loop gate to "always run the tool loop when math is
present" as a blunt fix — that reintroduces the TTFT cost `turn_needs_tool_loop`'s
own docstring explains this gate exists to avoid, and defeats the (correct) design
goal of skipping the extra non-streaming round when the heuristic path already fully
covers the turn. The fix should specifically distinguish "heuristic covered
everything" from "heuristic matched *something*."

---

### Formula emit rule enforcement

---

**R3 — The formula emit rule is prompt-only for model-fabricated geometry/graph
fences: a schema-valid but entirely invented diagram (wrong numbers, syntactically
correct JSON) passes through `validate_math_fences` completely unmodified when there
is no canonical fence of the same type to substitute**
**Severity:** P0 (diagram/JSON half) / P2 (backtick half, mitigated client-side) ·
**Area:** math-fence validation · **Effort:** S–M

**Evidence:**

- `docs/math.md`'s explicit rule: "the model must not emit diagram JSON... Recall
  attaches `canonical_fence` after the stream" and `MATH_INTENT_HINT`
  (`prompt_constants/math.py:13-14`): "Do NOT emit ```answer, ```graph, or
  ```geometry fences." This is a system-prompt instruction only — nothing forces
  model compliance.
- `math_fence.py:455-497`, `_replace_fence` — the only guard on the "no matching
  canonical fence" path (i.e. `_canonical_replacement` returned `None`, which is
  what happens whenever `verified` is `None` or the model's fence type doesn't match
  anything the solver actually computed) is, for `label == "geometry"`:
  ```python
  if label == "geometry":
      if not _validate_geometry(raw):
          raise ValueError("invalid geometry")
      return original
  ```
  `_validate_geometry` (`:81-113`) only checks that the JSON parses and matches one
  of the `*GeometryBlockSpec` **schemas** — it has no way to check whether the
  width/height/area/perimeter values are *true*. A schema-valid, numerically
  fabricated block returns `original` — the model's exact text, byte-for-byte.
- Reproduced (`.venv/bin/python`):
  ```python
  from app.services.math_fence import validate_math_fences
  content = (
      "Here is the rectangle you asked about.\n\n"
      '```geometry\n{"type": "rectangle", "width": 47, "height": 13, "unit": "cm", '
      '"area": 611, "perimeter": 120}\n```\n'
  )
  out = validate_math_fences(content, verified=None)
  # out is unchanged: same fabricated width/height/area/perimeter values, verbatim
  ```
  (area 611 = 47×13 is arithmetically self-consistent here, but nothing checks that
  either — a model could emit `area: 999999` and it would ship identically.)
- This is the same underlying gap class independently found by
  `docs/MATH_FENCE_PHYSICS_REVIEW_2026-09-06.md`'s **F6** ("the (N+1)th fence of a
  kind beyond the per-kind rewrite cap is shipped... with zero schema validation and
  zero unverified marker"), but with a simpler, more common trigger: this doesn't
  require exceeding any `_MAX_GEOMETRY_FENCES`/`_MAX_GRAPH_FENCES` cap — it happens
  on the very *first* fence of a kind whenever the heuristic/tool-loop simply never
  produced a canonical fence of that exact `type` (e.g., any geometry shape the
  extractor doesn't cover, or a turn where `math_tools_enabled` degraded/timed out
  for that one fence but not others). Two independent reviews reaching the same
  design gap via different triggers is strong confirmation this needs a single fix
  at the "any unmatched geometry/graph fence" level, not two separate cap/edge-case
  patches.
- **Backtick-around-`$...$`**: `math_fence.py` has no logic anywhere that inspects
  or strips backtick-wrapped inline math. Reproduced:
  ```python
  validate_math_fences("The result is `$x = 3$` after simplifying.", verified=None)
  # -> unchanged: '`$x = 3$` after simplifying.' backticks intact
  ```
  Mobile's `markdownPreprocess.ts` (`unwrapProseMathBackticks`) strips this
  client-side today, per the existing lessons-learned entry for the Recall repo —
  this fully mitigates rendering for the current mobile client, but per
  `CLAUDE.md`'s stated future direction ("a web client sharing this same API is
  planned for a later version"), a second client would not inherit this fix unless
  it duplicates the same client-side unwrap logic, since the backend API itself does
  not normalize this.

**Why it matters:** the entire premise of the "formula emit rule" — that Recall,
not the model, is the source of truth for any diagram/graph — assumes server-side
enforcement backs the prompt instruction. It does not, for the specific and highest-
stakes case: a model emitting a fabricated shape when the heuristic/tool-loop simply
didn't produce a same-type canonical fence for that ask. There is no visual, textual,
or metadata distinction on the wire between a Recall-verified diagram and a model-
invented one once it reaches `validate_math_fences` — both render identically on
mobile. For a product whose stated goal is being "trusted by students," a
confidently-wrong, syntactically-perfect fabricated rectangle or graph is the worst
possible failure mode: indistinguishable from a correct one until the student's
answer doesn't match their teacher's.

**Recommended fix:** when `_canonical_replacement` returns `None` for a geometry or
graph fence (no canonical fence of that type exists for this turn), do not fall back
to "pass through unchanged if schema-valid" — strip it to the same
`"*Could not render that diagram.*"` note already used for the malformed-JSON /
validation-failure branch (`math_fence.py:497`), consistent with the design
principle stated in the module's own docstring ("a drifted or hallucinated number
never reaches the user"). This aligns the "no canonical exists" branch with the
"canonical exists but doesn't validate" branch, which already fails closed. Land
this together with (or immediately after) `docs/MATH_FENCE_PHYSICS_REVIEW_2026-09-06.md`'s
F6 fix, since both need the same "no unverified fence ships unmodified" invariant.
For the backtick rule, add a small linear-scan normalizer to `validate_math_fences`
(mirroring mobile's `unwrapProseMathBackticks`) so the backend enforces its own
documented rule independent of any particular client.

**Do not:** attempt to validate the *numeric correctness* of an arbitrary
model-emitted geometry/graph fence server-side as the fix (re-deriving area from
width/height, etc.) — that reintroduces exactly the kind of ad hoc, per-shape
verification logic the canonical-fence design exists to centralize in one place
(the SymPy-backed builders). The correct fix is "don't trust it," not "re-verify
it a second way."

---

### Prompt-hint selection

---

**R4 — `_math_viz_intent()` omits `has_image_attachment`, so camera-math turns whose
extracted kind is geometry/statistics/graph/calculus (not equation/system/
inequality) never trigger the rich `MATH_INTENT_HINT` / `MATH_SOLVER_HINT` /
`MATH_TUTORING_HINT` bundle, even though a verified system block was correctly
injected for that same turn**
**Severity:** P2 · **Area:** prompt-builder · **Effort:** S

**Evidence:**

- `prompt_builder.py:121-130`, `_math_viz_intent`:
  ```python
  def _math_viz_intent(query_text: str | None) -> tuple[bool, bool]:
      if not query_text or not query_text.strip():
          return False, False
      math_intent = math_tools_service.needs_symbolic_math(query_text)
      ...
  ```
  No `has_image_attachment` argument is threaded through, unlike the pre-stream
  augmentation call site (`prompt_builder.py:244-246`, inside `fetch_web_and_tools`)
  which correctly passes `has_image_attachment=has_image_attachment`.
- `math_text_match/needs.py:80-135`, `needs_symbolic` — three of its detection
  branches are gated on `has_image_attachment` specifically because a camera-math
  caption alone is often too sparse to detect otherwise: line 84 (`if not cleaned
  and not has_image_attachment: return False` — an empty/whitespace caption only
  counts as math intent when an image is attached), line 88 (`is_math_camera_prompt`
  check, gated on `has_image_attachment`), and line 133 (`has_image_attachment and
  has_math_keyword(lower)` — a bare math-flavored caption with no equation syntax).
- `math_image_extract.py:62-84`: the fixed camera-flow caption is exactly `"Solve
  the math problem in this image step by step."` (`MATH_CAMERA_PROMPT`); a suffix
  like `"Solve: 2*x+3 = 7"` is appended to the message content *only* for
  `_SOLVE_KINDS = {"equation", "system", "inequality"}` (`:64, 71-84`) — for every
  other extracted kind (`rectangle`, `circle`, `triangle_sides`, `statistics`,
  `graph`, `calculus`, `limit`), `camera_math_user_suffix` returns `None` and the
  message content stays exactly the bare preset caption.
- `turn_prep/prepare.py:120-121` (`content = attachments.content`) confirms this
  post-attachment-processing `content` — including any (absent, for non-solve
  kinds) suffix — is exactly what flows into `query_text` for
  `build_prompt_messages` / `_style_format_hints` (`turn_prep/context.py:399`).
- Reproduced (`.venv/bin/python`):
  ```python
  from app.services.math_text_match import needs_symbolic
  caption = "Solve the math problem in this image step by step."
  needs_symbolic(caption, has_image_attachment=False)  # False
  needs_symbolic(caption, has_image_attachment=True)   # True
  # Equation-kind camera math DOES get a suffix and is fine either way:
  needs_symbolic(caption + "\n\nSolve: 2*x+3 = 7", has_image_attachment=False)  # True
  ```
  Confirms the gap is real and specifically limited to non-`_SOLVE_KINDS` camera
  math (geometry shapes, stats, graphs, calculus/limits from a photo) — a very
  common homework-photo category, not a narrow edge case.
- The baseline `SHORT_MATH_SAFETY_HINT` is still appended unconditionally on this
  same branch (`prompt_builder.py:693`, before the `math_intent` check at line 695),
  and it already contains the core rules ("Do NOT emit ```answer, ```graph, or
  ```geometry", "use those exact numbers — do NOT recompute", "Never invent geometry
  dimensions") — so this is a hint-*richness* gap, not a total absence of the
  formula-emit-rule instruction.

**Why it matters:** for exactly the camera-math flow most likely to be a geometry
or statistics homework photo (the majority of non-algebra "solve with camera"
submissions), the model receives the compact safety rules but not
`MATH_SOLVER_HINT`'s specific diagram-description guidance ("Describe the figure in
words using `$...$`... Never invent geometry dimensions... numbers in older examples
were illustrative only") or `MATH_TUTORING_HINT`'s Socratic-tutoring behavior
("CHECK it against the verified result before praising it... point to the specific
step where it went wrong"). The verified system block itself is still injected and
`validate_math_fences` still runs — so the final diagram is still solver-owned
(assuming R3 is fixed) — but the model's prose around it gets meaningfully less
specific guidance exactly on the turns most likely to need it.

**Recommended fix:** thread `has_image_attachment` (and, where available,
`image_math_extract`) into `_math_viz_intent`, mirroring the signature
`fetch_web_and_tools` already uses — `_style_format_hints` and its caller
(`prompt_builder.py:854, 925-926`) already have access to this context (it flows
through the same `build_prompt_messages` call that carries `query_text`); this is a
plumbing fix, not a new heuristic.

**Do not:** duplicate the `MATH_INTENT_HINT`/`MATH_SOLVER_HINT`/`MATH_TUTORING_HINT`
bundle's content into `SHORT_MATH_SAFETY_HINT` as a workaround — that defeats the
existing, deliberate design (`SHORT_MATH_SAFETY_HINT`'s own comment: "kept
deliberately compact... so it doesn't blow past Short mode's own token budget") and
would bloat every turn's prompt, not just camera-math ones.

---

## D. Weak / unwanted / missing inventory

| Item | Status | Evidence | Recommend |
|---|---|---|---|
| `needs_symbolic()` → smart-model routing (bare math turn) | **Solid** | `routing.py:296-319`; manually verified with plain algebra/calculus asks | Keep as-is |
| `_verified_math_stays_fast()` scope | **Broken** (whole-message substring match, not whole-message coverage) | `routing.py:346-368`; reproduced R1 | Fix scope check (R1) |
| Tool-loop vs. heuristic double-computation / race | **Not present** (mutually exclusive by design) | `stream_pipeline.py:78, 83-116, 141-142`; `tool_loop.py:255` | No action — do not "fix" a race that doesn't exist |
| `has_verified_math` gate granularity | **Broken** (message-level, not sub-problem-level) | `tool_loop.py:232-280`; reproduced R2 with mis-parsed multi-intent message | Fix gate granularity (R2) |
| `calculating` status timing (pre-stream vs. tool-loop) | **Consistent** | `prompt_builder.py:244-248`; `turn_prep/attachments.py:259-260`; `tool_loop.py:414-416` | Keep as-is |
| Formula-emit-rule enforcement — geometry/graph fences | **Zero enforcement when no canonical exists** | `math_fence.py:477-481`; reproduced R3; cross-confirmed by `MATH_FENCE_PHYSICS_REVIEW_2026-09-06.md` F6 | Fail-closed on any unmatched fence (R3) |
| Formula-emit-rule enforcement — backticked `$...$` | **Zero server-side enforcement, mitigated client-side only** | `math_fence.py` has no backtick-unwrap logic; mobile `unwrapProseMathBackticks` compensates | Add server-side normalizer for future web-client parity (R3) |
| `MATH_SOLVER_HINT` / `MATH_TUTORING_HINT` conflict potential | **Not present** (always co-selected, complementary content) | `prompt_builder.py:691-702`; `prompt_constants/math.py:1-123` | No action |
| Rich math hint selection for camera-math (non-solve kinds) | **Gap** (baseline safety hint still applies; richer hints skipped) | `prompt_builder.py:121-130`; `math_text_match/needs.py:84,88,133`; reproduced R4 | Thread `has_image_attachment` into `_math_viz_intent` (R4) |
| Legacy `mcp_tools_enabled` double-injection guard | **Solid** | `chat_tools.py:27,35-41`; tests pass | Keep as-is |
| SymPy tool canonical-fence plumbing vs. heuristic path | **Consistent, single contract** | `sympy_adapter.py:38-49`; `tool_loop.py:64-77,456-467` | Keep as-is |
| `invoke_validated` Pydantic gate | **Solid** | `registry.py:66-91` | Keep as-is |
| SymPy RCE sandbox (`_reject_unsafe_expr`) | **Unchanged, still enforced** | direct read of current source; `test_mcp.py::test_sympy_adapter_rejects_rce_payload_via_solve` passes | Keep as-is; not re-audited beyond this confirmation |
| Test coverage for this review's scope | **Solid, 177/177 green** | pytest output, this review, §B | Keep as-is; add regression tests alongside R1/R2/R4 fixes |

---

## E. Sequenced fix plan

One concern per PR, matching this codebase's own execution discipline.

1. **`fix(api): fail-closed on any geometry/graph fence with no matching canonical
   type`** — R3 (geometry/graph half). Highest severity, smallest blast radius
   (touches only the "no canonical match" branch of `_replace_fence`); land this
   first and coordinate with `docs/MATH_FENCE_PHYSICS_REVIEW_2026-09-06.md`'s F6 fix
   since both need the same invariant.
2. **`fix(api): scope has_verified_math to whether the extraction covered the whole
   message, not merely that it matched something`** — R2. Second-highest severity;
   requires slightly more design work (detecting multi-intent messages or gating on
   match-span coverage) — budget for a small design note before implementation.
3. **`fix(api): scope _verified_math_stays_fast's trivial-math exception to the
   whole message`** — R1. Independent of 1–2; small, isolated regex/heuristic change
   with two ready-made regression cases (the Rayleigh-scattering and
   twinkling-stars repros above).
4. **`fix(api): thread has_image_attachment into _math_viz_intent`** — R4.
   Independent, small, plumbing-only change.
5. **`fix(api): normalize backtick-wrapped inline math in validate_math_fences`** —
   R3 (backtick half). Independent, low urgency given client-side mitigation, but
   worth doing ahead of any web-client work per `CLAUDE.md`'s stated direction.

---

## F. Explicit non-goals

Considered and deliberately not raised as findings, or explicitly out of this
review's assigned scope:

- **Re-auditing `sympy_adapter.py`'s RCE/sandbox surface.** Already closed and
  covered by `docs/MCP_TOOL_LOOP_SECURITY_REVIEW_2026-09-06.md`; this review only
  re-confirmed `_reject_unsafe_expr` is unchanged (§B, §C M-item) as explicitly
  requested, not a full re-audit.
- **`math_fence.py`'s densify/cap/timeout engine and `physics_solver.py` formula
  correctness.** Covered in depth, concurrently, by
  `docs/MATH_FENCE_PHYSICS_REVIEW_2026-09-06.md`; this review's R3 finding
  intersects with their F6 at the "no canonical match" branch specifically and is
  cited rather than re-derived. Physics extraction bugs (sign flips, keyword
  substring matches, post-impact time handling) are entirely their scope, not
  reviewed here.
- **Mobile rendering of fences / `markdownPreprocess.ts`.** Read only enough to
  confirm the backtick-mitigation claim in R3; no line-by-line mobile review was
  performed as part of this task.
- **`services/chat/prompt_constants/visuals.py` / `writing.py` math sections
  beyond confirming consistency.** Both independently restate the "do not emit
  ```geometry/```graph" rule (`visuals.py:64-66`, `writing.py:105-108`) consistently
  with `math.py`'s hints — read and confirmed non-contradictory, not a deep review
  of those files' broader (non-math) content, which is out of this task's scope.
- **Re-deriving the general "at-least-once background jobs" or non-math prompt
  hints.** Out of scope for this math-specific audit.
- **Redesigning `extract_math_intent`'s first-match-wins architecture wholesale.**
  R2's recommended fix works within the existing single-extraction design (skip or
  down-weight the heuristic path for compound messages); a full multi-intent parser
  rewrite is a larger design question this review flags but does not spec out.
