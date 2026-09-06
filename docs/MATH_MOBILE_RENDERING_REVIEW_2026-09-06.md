# Recall — Math Rendering (Mobile) Pre-Launch Review (Sep 2026)

Scope: line-by-line, read-only audit of the "math powerhouse" client rendering path —
inline math tokenizer, display-math WebView, geometry/graph SVG, crash-fallback, and
streaming-specific behavior. Goal: find anything that can show garbled math, a blank
screen, or a hard crash, even when the underlying computation is correct. No source
changed; no commits made.

Reviewed at `cursor/cross-domain-review-2026-09-05`. Prior WebView/CSP findings in
`docs/OUTPUT_FORMAT_REVIEW_2026-09-05.md` are re-verified narrowly (adversarial LaTeX
specifically) and not re-litigated in full.

---

## A. Verdict

**Ship it — the failure modes here are "briefly ugly," not "broken."** Every parser in
scope (`mathText.ts`'s LaTeX tokenizer, `geometryBlock.ts`, `graphBlock.ts`) is total: I
could not find an input — malformed JSON, unbalanced braces, missing fields, `Infinity`/
`NaN`, zero/negative dimensions, or 20-level-deep nesting — that throws instead of
returning `null` or a garbled-but-safe string. The specific claim in `docs/math.md`
("crash fallback still draws geometry/graph as SVG") is **true and verified**: the fallback
path (`fallbackFence.ts` → `FallbackMarkdown` → `GeometryBlock`/`FunctionGraphBlock`) reuses
the exact same defensively-coded parsers as the primary renderer, so a fence that breaks
`markdownRenderRules.tsx` for an unrelated reason still draws the diagram, not raw JSON.
Expo Go's math story is also better than the docs implied on first read: `@expo/dom-webview`
is a real project dependency, so Expo Go gets the actual KaTeX/MathJax WebView (not just
the native-Text fallback) for inline math preview — the honest "dev build only" fallback
only appears if *that* also fails to load.

**The one finding worth fixing before launch is M1: the per-message crash boundary
(`MarkdownErrorBoundary`) has no second line of defense.** `FallbackMarkdown` is rendered
directly as the boundary's own fallback UI with nothing wrapping it. If a message manages to
break *both* the primary renderer and `FallbackMarkdown` (e.g. `preprocessMarkdown`/
`markdownItInstance.render()` itself throwing on the same pathological structure that broke
the primary render), the error does not stay scoped to that one message — React error
boundaries do not catch errors thrown by their own fallback UI, so it propagates to the
route-level `expo-router` `ErrorBoundary` in `app/_layout.tsx` and takes down the *entire*
chat screen. This is a low-likelihood, high-blast-radius gap in an otherwise very
well-defended system, and the fix is small (one more nested boundary, or a try/catch with a
plain-`Text` last resort).

**The other genuine (not cosmetic) finding is M2: the documented streaming anti-flicker fix
has a real, reproducible gap.** `advanceStreamBlocks` only commits a closed rich block
(` ```math `, `$$...$$`) into its permanently-memoized chunk list once a *subsequent* full
line of new content arrives after the blank line that follows it. I reproduced a common
shape — reply ends a math fence, blank line, then keeps streaming the next sentence with no
further blank line — where the already-closed, correctly-rendered math block sat in the
non-memoized, re-parsed-every-32ms tail for 133 characters (the entire length of that next
sentence) before finally settling. During that window the KaTeX/MathJax WebView backing that
block remounts on every flush tick, per the component's own header comment. It self-corrects
and never shows wrong math — it's a flicker, not a garble — but it is a specific, provable
counter-example to "eager cut reduces math flicker."

Everything else below (F1–F4, the tokenizer edge cases, the XSS/CSP re-check, the Expo Go
gating) is confirmed either already correctly handled or cosmetic-only.

---

## B. What's working (don't "fix" these)

- **Every parser in scope is total.** `parseSimpleLatex` (mathText.ts), `parseGeometrySpec` /
  `parseGraphSpec` (geometryBlock.ts / graphBlock.ts) never throw on malformed input — they
  return `null` or a degraded-but-safe value. Verified directly (§C, evidence below), not
  assumed.
- **`MAX_MATH_NEST_DEPTH = 12` genuinely caps recursion.** A 20-level nested `\frac` does not
  stack-overflow or hang; it renders the outer 12 levels correctly and folds the remainder to
  plain text (`mathText.ts:32,578-580`).
- **The tokenizer has no perf cliff.** A 40k-char plain expression parses in 11ms; 2,000
  sequential `\frac{}{}` in 47ms; 20,000 unknown `\command`s in 30ms; 60k chars of math-free
  prose in 4ms (measured directly, Node/ts-jest, this machine — see §C methodology). No
  `CMD_REPLACEMENTS`/regex pass in `preprocessLatex` shows quadratic or worse blowup on any
  input tried, including ones designed to trigger it.
- **The crash-fallback SVG claim is real, not aspirational.** `fallbackFence.ts` classifies
  `geometry`/`graph` fences and hands the *same* body straight to `GeometryBlock` /
  `FunctionGraphBlock` (`fallbackFence.ts:108-111`, `FallbackMarkdown.tsx:92-97`) — the exact
  same total parsers as the primary path, not a simplified or JSON-dumping stand-in.
- **Geometry/graph input validation is thorough and already defends the exact "extreme
  aspect ratio" / degenerate cases this review was asked to probe.** `readPositive` bounds
  every geometry dimension to `(0, 1_000_000]` (`geometryBlock.ts:139-145`); `parseParallelogram`
  explicitly rejects `side < height` with a comment naming the exact bug it prevents ("guards
  the shear-offset math... against a malformed fence," `geometryBlock.ts:319-322`);
  `scaleToFit` floors the rendered size to 120px so a huge/degenerate shape never collapses to
  invisible (`geometryBlock.ts:833-842`); `graphBounds` pads a collapsed single-value axis by
  ±1 so a one-point graph isn't glued to the frame edge (`graphBlock.ts:264-271`);
  `triangleSidesVertices`'s `Math.max(0, ...)` under the `sqrt` prevents a `NaN` from
  floating-point error on a needle-thin (1,000,000 / 1,000,000 / 1) triangle
  (`geometryBlock.ts:453`). I generated all of these adversarial specs directly against the
  pure functions and inspected every returned number for `NaN`/`Infinity` — none found.
- **The WebView math paths are not newly vulnerable to XSS beyond what's already documented.**
  I built and traced three concrete adversarial LaTeX strings (`</script><script>...`,
  a backtick/`${`-breaking payload, and `\href{javascript:alert(1)}{...}`) through both the
  KaTeX (`katexRender.ts`) and MathJax (`mathHtmlMathjax.ts`) HTML builders. KaTeX's default
  `trust: false` (never overridden) refuses `\href`/`\includegraphics`; `escapeForHtmlTemplate`
  correctly escapes backtick/`${`/`</script>` (including case and whitespace variants) before
  it ever reaches a `<script>` block. No injected `<script>` or `javascript:` anchor survived
  in the rendered HTML in any of the three cases.
- **Expo Go's math story is genuinely honest, and better than it first appears.**
  `@expo/dom-webview` is a real, installed dependency (`package.json`, confirmed in
  `node_modules`), so `getPreviewWebView()` (`lib/webView.ts:38-69`) returns a working WebView
  in Expo Go too — `supportsInlineHtmlMathWebView` accepts both `"rnc"` and `"expo-dom"`
  (`mathWebViewSupport.ts:12-16`). Only if *neither* is available does the app fall back to
  `MathLatexFallback` — native `MathText` plus an explicit "dev build" hint badge
  (`MathFormulaWebView.tsx:179-181,289-298`) — never a blank or confusing box.
- **The streaming stable-prefix scanner is provably correct for append-only content**, not
  just fast. I fed the same content byte-by-byte through the incremental
  `preprocessMarkdownForStream` and compared the final result against a one-shot call on the
  full string: identical. It correctly withholds an unclosed `$...$`, `\[...\]`, `\(...\)`,
  ` ``` `/`~~~` fence, or `$$` block from the "stable" prefix at a single-`$` granularity — a
  stream cut off exactly after `$\frac{1}{` is *not* treated as safe to preprocess.
- **Backend-parity validation matches, and is not the weak link.** `MAX_GEOMETRY_DIMENSION`
  (1,000,000) and `MAX_GRAPH_POINTS` (500) mirror the backend Pydantic caps per their own
  comments, so an older client hitting a same-shaped-but-larger future fence degrades to the
  fallback error text, not an unbounded render.

---

## C. Findings — ranked

### Crash-fallback robustness

---

**M1 — The per-message crash boundary has no second line of defense; a fallback-render
failure escalates to a whole-screen crash, not a scoped one**
**Severity:** P1 · **Area:** rich-render / error-boundary · **Effort:** S

**Evidence:**
- `MarkdownErrorBoundary.render()` (`components/MarkdownErrorBoundary.tsx:33-38`) returns
  `<FallbackMarkdown content={this.props.content} />` directly when `state.failed` — nothing
  wraps it.
- `FallbackMarkdown` (`components/FallbackMarkdown.tsx`) itself calls `preprocessMarkdown`
  (l.53) and renders through `react-native-markdown-display` with a custom `fence` rule
  (l.43-52) that dispatches to `GeometryBlock`/`FunctionGraphBlock` (l.92-97) — all real,
  non-trivial code paths that *can* throw for reasons unrelated to the geometry/graph JSON
  itself (a `preprocessMarkdown` regex issue, a `markdown-it` plugin exception, a React-Native
  SVG native-side error).
- Per documented React behavior, an error boundary does not catch an error thrown while
  rendering *its own* fallback UI — that error is handled by the closest **ancestor**
  boundary. The only ancestor found by grep is the route-level `export { ErrorBoundary } from
  "expo-router"` in `app/_layout.tsx:157`, which replaces the *entire current screen*, not one
  message bubble.
- I did not find (and grepped for) any additional `ErrorBoundary` between `MessageBubble.tsx`
  (where `MarkdownErrorBoundary` is wired, l.442-448) and the route root.

**Why it matters:** the whole design of `MarkdownErrorBoundary` + `FallbackMarkdown` +
`fallbackFence.ts` exists specifically so *one bad message* degrades gracefully instead of
crashing the app. That design holds for the common case (primary renderer throws, fallback
renders fine) but has an unguarded seam for the rare "both throw" case — which is exactly the
kind of case a pre-launch audit for a "math powerhouse" should assume model output will
eventually hit (a future fence schema addition, a genuinely pathological nested structure,
etc.). Today that seam turns a one-message problem into a whole-chat-screen problem for every
user with that message in their history, until the message is deleted or edited server-side.

**Recommended fix (small):** wrap `FallbackMarkdown`'s render in a second, simpler boundary
(or a plain try/catch with `getDerivedStateFromError`) whose own fallback is a bare
`<Text selectable>{content}</Text>` — no markdown, no rich blocks, nothing that can itself
throw. This guarantees the crash never escapes past the single message bubble regardless of
how badly a future fence is malformed.

**Do not:** try to make `FallbackMarkdown` itself exhaustively defensive against every
possible internal exception — that's an unbounded task. A last-resort plain-text tier is
cheaper and strictly safer than trying to harden every intermediate function.

---

### Streaming

---

**M2 — The "eager cut reduces math flicker" fix has a reproducible gap: a closed rich block
followed by an in-progress next paragraph (no further blank line yet) stays un-memoized and
re-parses on every ~32ms flush for the length of that whole paragraph**
**Severity:** P2 · **Area:** streaming / markdown-render · **Effort:** M

**Evidence:** reproduced directly by driving `preprocessMarkdownForStream` +
`advanceStreamBlocks` (the exact pipeline `MarkdownContent.tsx:180-206` uses) character-by-
character over:

```
"Here is the derivation.\n\n```math\nx^2 + 2x + 1 = (x+1)^2\n```\n\nSo the final simplified
answer is that x equals negative one when the expression equals zero, which we can verify by
substitution.\n"
```

Result: the ` ```math ` fence closes (both markers present) at character 59, but is not
committed into `blocks.chunks` (the permanently-memoized, `React.memo`'d tier —
`markdownStreamBlocks.ts:71-186`, `MarkdownContent.tsx:216-223`) until character 192 — a lag
of 133 characters, i.e. the *entire* length of the next sentence, because that sentence has
no blank line inside it to complete the "blank run then next content line" pattern
`advanceStreamBlocks`'s cut-check requires (`markdownStreamBlocks.ts:161-184`: the cut only
fires when the loop reads a *complete, safe-region* content line following a blank run — if
the next paragraph's first line hasn't hit its own `\n` yet, or that `\n` falls outside the
`preprocessMarkdownForStream`-computed `safeLen`, the loop simply stops without cutting).
Until that cut happens, the block lives in `unsettledStable`
(`MarkdownContent.tsx:206,224-228`) — a **fresh, non-`React.memo`'d** `<Markdown>` element
re-created every render — as opposed to `MarkdownStreamChunk`, which is explicitly
`React.memo`'d (`MarkdownContent.tsx:45-55`) for exactly this reason. A second control
scenario (fence immediately followed by another closed fence with no in-progress prose
between them) cuts in 27 characters — confirming the lag is specifically tied to "next content
is still being typed," not a general scanner bug.

**Why it matters:** `STREAM_UI_INTERVAL_MS = 32` (`lib/streamUiTiming.ts:6`) means the UI
flushes roughly every 32ms while tokens are arriving. For a 133-char lag at typical streaming
speeds (several seconds for a full sentence), that's dozens of flush ticks during which — per
the file's own header comment ("react-native-markdown-display regenerates node keys per
parse... the entire message subtree remounted every time") — the just-finished, correctly
rendered math fence's KaTeX/MathJax WebView is torn down and recreated repeatedly, purely
because the *next*, unrelated sentence is still streaming. This is exactly the "visible
blank-then-repaint" class of bug the existing lessons log (`.cursor/rules/lessons.mdc`) and
the `#443` fix already targeted — this is a residual gap in that same fix, not a new bug
class. It never shows *wrong* math, only a flicker, so it's correctly P2 rather than P1/P0.

**Recommended fix:** loosen the cut condition so a rich block that has just closed can be cut
immediately at its own closing boundary (after the mandatory blank line), without waiting for
the *next* paragraph's first line to complete — i.e. treat "blank line immediately after a
`hasRichBlockSinceChunkStart` block, even if nothing follows it yet within `safeLen`" as
itself a valid cut point. This mirrors the existing early-cut special case for rich blocks
(`markdownStreamBlocks.ts:94-106`) but removes its dependency on a following content line.

**Do not:** relax `MIN_SETTLED_CHUNK_CHARS` for plain prose to "fix" this — the 320-char
batching for prose chunks is unrelated and works as intended; only the rich-block early-cut
path needs the boundary condition loosened.

---

### Tokenizer edge cases (all confirmed non-crashing; listed for completeness)

---

**L1 — Unbalanced/mismatched LaTeX braces render garbled (not raw, not a crash) — expected
given the design, but worth naming precisely for future test coverage**
**Severity:** P3 · **Area:** mathText.ts · **Effort:** N/A (document only)

**Evidence** (direct invocation of `parseSimpleLatex`, Node/ts-jest):

| Input | Output (`segmentsToPlain`) |
|---|---|
| `\frac{1}{2` (missing outer `}`) | `"1{2"` |
| `\frac{1` (missing both) | `"{1"` |
| `x^{2` (unclosed sup group) | `"x^{2"` (superscript is rendered as a literal `{` character, then plain `2`) |
| `\sqrt{4` (unclosed) | `"{4"` |
| `\begin{cases}x=1` (no matching `\end`) | `"casesx=1"` (environment name leaks, merged with the equation) |
| 20-level nested `\frac` | correctly renders the outer 12 levels; the 13th+ level's *literal source text* (including its own unprocessed `\frac{...}` commands) is folded in as plain text — visibly wrong but not corrupted binary/garbage |

**Why it matters:** `readGroup` (`mathText.ts:309-322`) returns `null` on an unmatched brace,
which correctly prevents an infinite loop or crash — but the caller (`parseFrac`,
`parseSqrt`) then falls through to the generic backslash-command handler, which *partially*
consumes the command name and leaves the dangling `{` as literal text. This is the expected,
designed-for degraded behavior for genuinely malformed model output (a truncated response,
a mid-token stream artifact that survived preprocessing) — LLMs essentially never emit
unbalanced braces in a *completed* response, so this path is reachable mainly via truncation
or an adversarial/corrupted payload, not routine model output.

**Recommended fix:** none required for launch. If test coverage is being expanded anyway,
add these exact input/output pairs as regression cases in `mathText.test.ts` so a future
tokenizer refactor can't silently regress from "garbled" to "throws."

**Do not:** try to make unbalanced-brace input "look nice" — there is no well-defined correct
rendering for genuinely malformed LaTeX; garbled-but-stable is the right target, not
prettified-but-guessed.

---

**L2 — `FunctionGraphBlock`'s chart width has no defensive floor (unlike the geometry code's
`scaleToFit`), so a pathologically narrow viewport could produce a negative-width SVG**
**Severity:** P3 · **Area:** graphBlock / FunctionGraphBlock · **Effort:** S

**Evidence:** `chartWidth = Math.min(screenWidth - 48, 360)`
(`FunctionGraphBlock.tsx:37`, and the same pattern in the `NumberLineChart` caller,
`FunctionGraphBlock.tsx:57`) has no lower bound. Contrast with the geometry code's
`scaleToFit`, which explicitly floors to 120px with a comment explaining why
(`geometryBlock.ts:833-842`, `inner = Math.max(maxWidth - padding, 120)`). Direct test:
`mapGraphPoint(5, 5, bounds, -50, -50, 28)` returns `{ px: -25, py: -25 }` — not `NaN`, but a
negative coordinate inside a would-be negative-width `<Svg>`.

**Why it matters:** `useWindowDimensions().width` returning less than 48px requires a
device/window narrower than 48 logical pixels, which does not happen on any current phone or
tablet in either orientation, including Android split-screen/foldable minimum pane widths.
This is a real gap in symmetry with the geometry code's defense-in-depth, not a reachable
crash on any realistic device today — hence P3, not higher.

**Recommended fix:** `const chartWidth = Math.max(Math.min(screenWidth - 48, 360), 120);` —
one line, matches the existing `scaleToFit` pattern, costs nothing.

**Do not:** treat this as urgent or block launch on it — no realistic path to trigger it was
found.

---

### WebView / CSP (re-verified, not re-litigated)

---

**Swept and clean — no new XSS surface found in the math-specific WebView paths.**
`docs/OUTPUT_FORMAT_REVIEW_2026-09-05.md`'s CSP findings for the general preview sandbox are
unaffected by this review's narrower, math-specific adversarial tests (`</script>` injection,
JS-template-literal breakout, `\href{javascript:...}`) — all three were blocked by existing
defenses (`katex.renderToString`'s default `trust: false`, `escapeForHtmlTemplate`'s
backtick/`${`/`</script>` escaping). Not re-tested: the general `injectPreviewCsp` head-
injection hardening already covered in that prior review (unchanged in this scope).

---

## D. Weak / unwanted / missing inventory

- **No dedicated regression tests for the exact unbalanced-brace / unclosed-environment
  inputs in L1**, despite `mathText.test.ts` otherwise having good coverage. Low cost to add;
  not blocking.
- **No test simulating the "closed rich block + in-progress next paragraph" streaming shape
  from M2** in `markdownStreamBlocks.test.ts` — the existing tests cover the "immediately
  followed by more closed content" and "isolated block" shapes well, but not this specific
  lag window.
- **No test asserting `MarkdownErrorBoundary`'s fallback (`FallbackMarkdown`) is itself
  crash-isolated** (M1) — there's no way to write this test today because the isolation
  doesn't exist yet; it becomes testable once the second boundary is added.

---

## E. Sequenced fix plan

1. **M1** — add a last-resort plain-text tier inside `MarkdownErrorBoundary`/
   `FallbackMarkdown` so a fallback-render failure stays scoped to one message. Small, no
   behavior change for the success path.
2. **M2** — loosen `advanceStreamBlocks`'s cut condition so a closed rich block can commit to
   a memoized chunk immediately after its own trailing blank line, without waiting on the next
   paragraph's first line to complete. Medium effort (touches the core streaming chunker;
   needs the existing `markdownStreamBlocks.test.ts` suite plus a new case for this exact
   shape).
3. **L2** — one-line defensive floor on `chartWidth`. Trivial, do opportunistically.
4. **L1** — add the unbalanced-brace regression cases to `mathText.test.ts` opportunistically;
   not required for launch.

---

## F. Explicit non-goals

- **Not re-auditing the general sandboxed-HTML/JS preview or its full CSP hardening** —
  covered by `docs/OUTPUT_FORMAT_REVIEW_2026-09-05.md`; this review only re-ran adversarial
  LaTeX specifically through the math-specific KaTeX/MathJax builders.
- **Not proposing a "prettified" rendering for genuinely malformed LaTeX** (L1) — garbled-but-
  stable is the correct target for truncated/adversarial input; there is no well-defined
  "correct" output for `\frac{1}{2` missing a brace.
- **Not benchmarking on-device (simulator/hardware) WebView remount cost for M2** — the
  finding is proven at the pure-function/chunking level (character-accurate lag measured
  directly); the *visual* severity of a WebView remount on real hardware was not measured in
  this pass (would need a device/simulator with an attached profiler), so M2 is ranked P2 on
  the strength of the reproducible logic gap, not a measured frame-drop count.
- **Not changing `MAX_MATH_NEST_DEPTH`, `MAX_KATEX_CHARS`, `MAX_GEOMETRY_DIMENSION`, or
  `MAX_GRAPH_POINTS`** — all four were checked against pathological input and hold correctly;
  no evidence they need to move in either direction.
- **Not touching KaTeX's `trust`/`strict` options** — verified safe as configured
  (`trust` unset → default `false`; `strict: "ignore"`); no argument found for changing either.

---

## Methodology notes

- Test suite: `cd apps/mobile && pnpm install` (already installed in this environment) then
  `npx jest --testPathPatterns="mathText|geometryGraphBlock|normalizeImplicitMath|mathRenderCorpus|markdownPreprocess|GeometryBlock|FunctionGraphBlock|MathText|MathView|MathFormulaWebView|AnswerBlock|markdownMathRender"`.
  Result: **13 suites, 342 tests, all passing**, both before and after this review's
  exploratory scratch tests (which were written, run, and deleted — no test files were left
  behind, no source file was modified).
- Tokenizer/perf/degenerate-input/XSS claims were verified by writing temporary `*.test.ts`
  files that directly imported and called the real pure functions (`parseSimpleLatex`,
  `parseGeometrySpec`, `parseGraphSpec`, `graphBounds`, `mapGraphPoint`, `scaleToFit`,
  `triangleSidesVertices`, `buildKatexStaticWebHtml`, `escapeForHtmlTemplate`) under Jest/
  ts-jest (Node environment, no simulator required for these — they are pure TS with no RN
  runtime dependency). Every file was deleted after use; `git status` confirms a clean tree.
- Streaming claims (M2) were verified the same way, driving the actual
  `preprocessMarkdownForStream` + `advanceStreamBlocks` functions character-by-character to
  reproduce the exact pipeline `MarkdownContent.tsx` runs, rather than reasoning about the
  code statically.
- What was **not** executed: anything requiring a live device/simulator (actual WebView
  remount visual behavior, actual React error-boundary propagation across a real component
  tree, actual Expo Go vs. dev-build device testing). Those claims rely on: (a) documented
  React error-boundary semantics (an error boundary does not catch errors from its own
  fallback render — well-established behavior, not this review's speculation) for M1, and
  (b) static confirmation that `@expo/dom-webview` is an installed, resolvable dependency
  (not just referenced in a comment) for the Expo Go finding. Both are labeled as such above.
