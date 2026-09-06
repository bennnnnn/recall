# Recall — Output Format / Rich Rendering Pipeline Review (Sep 2026)

Scope: **only** the structured-output pipeline — fence classification/dispatch, Pydantic
validation of LLM structured output (golden rule #6), the math post-stream correction pass,
CSP on WebView rendering, and the mobile rich-render/fallback chain. Chat streaming transport
(WS/SSE) is explicitly out of scope except where it touches formatting.

Reviewed at `main` (tip `a7580a9c`, 2026-09-04). This directly follows up on
`docs/CODEBASE_REVIEW_2026-08.md` findings **C5** (fence dispatch has no registry) and **C7**
(`contextSummarized` dead plumbing), and on three commits from an "output-routing review" that
landed the day before this review (`ac43e1f3`, `3cca5009`, `a7580a9c`, all 2026-09-04), on top
of the original registry commit `ce07e6ae` (2026-08-13, "one fence registry for structured,
code-block and fallback").

---

## A. Verdict

**C5 and C7 were both genuinely fixed, and the fix is real, not cosmetic.** `lib/fenceRegistry.ts`
is now the one place that declares a fence's language aliases, whether it enters the rich
renderer, whether it's excluded from syntax-highlighted code, who is allowed to emit it, and how
it degrades on a render crash. `richBlocks.ts`, `copyBlock.ts` (`isExplicitCodeLang`),
`fallbackFence.ts`, and `markdownFenceRender.tsx` all derive from it rather than maintaining their
own lists — confirmed by reading every one of those call sites, not by trusting the docstring.
`contextSummarized` (C7) is fully deleted from the mobile message pipeline. CSP is consistently
injected on every WebView rendering path I could find (KaTeX, MathJax, Vega charts, PDF, Mermaid,
chemistry, HTML Run preview) — the R5-style "math WebView missing CSP" class of bug is closed.

**The registry pattern is correct but the discipline it enforces is already leaking at the next
layer down.** The Sept 4 "output-routing review" introduced `lib/fenceDispatch.ts` as the single
classification function (`classifyFence`) — itself a good consolidation, now the one function both
`markdownFenceRender.tsx` and the open-stream preview path call. But it ships with a new
hand-written `DIAGRAM_IDS` set and reuses `copyBlock.ts`'s hand-written `isStructuredDraftLang` /
`COPY_LANGS` — three more lang lists that duplicate information the registry already has. They
agree with `fenceRegistry.ts` today; nothing stops them drifting apart the way the original five
lists did, and no test would catch it if they did.

**The more serious gap is validation, not dispatch.** Golden rule #6 says all LLM structured
output is Pydantic-validated before it touches the DB. `math_fence.py`'s geometry/graph path is a
clean example of doing this right. Two paths are not: the `vocab_quiz` fence — a fully
model-authored JSON blob — is parsed with hand-rolled `dict.get()` calls into a plain
`@dataclass`, and the result is persisted to SM-2 progress with no schema validation at all. And
the `places` fence, contrary to what `fenceRegistry.ts`'s own `owner: "server"` annotation claims,
is actually authored by the model on most turns (the prompt instructs it to emit the fence
directly) and the server only appends its own validated version when the model didn't already
write one — which, per the prompt, is the minority case. Neither gap is a new regression from the
Sept 4 review; both predate it and were out of that review's stated scope, but they are real,
current, and exactly the shape of thing golden rule #6 exists to prevent.

**Test coverage has not caught up to either fix.** C5's own recommended fix said: "Add a test
asserting every registered id round-trips through render, copy, and fallback." That test does not
exist. `fenceRegistry.test.ts` is a characterization test of the lookup tables; `fenceDispatch.test.ts`
tests `classifyFence`'s *decision*, not what `renderRichFenceById` / `renderCopyStyleBlock` /
`classifyFallbackFence` actually produce for that decision. It is entirely possible today to add a
fence id to `FENCES`, wire no case into `RichFence.tsx`'s switch, and have every existing test
still pass — `renderRichFenceById`'s `default: return null` swallows it silently.

---

## B. What's working (don't "fix" these)

- **The registry is real.** `lib/fenceRegistry.ts:78-250` is the sole `FENCES` table; `isStructuredFenceLang`,
  `isNeverCodeBlockLang`, `fallbackKindForLang`, `fenceIdForLang` are its only accessors.
  `richBlocks.ts` imports `isStructuredFenceLang` rather than re-declaring `STRUCTURED_LANGS`;
  `copyBlock.ts:416-423`'s `isExplicitCodeLang` explicitly derives from `isNeverCodeBlockLang`
  with a comment ("lives in lib/fenceRegistry.ts... so it cannot drift from the structured-fence
  list again"); `fallbackFence.ts:11,55,105` calls `fenceIdForLang`/`fallbackKindForLang` for
  every branch. This is the C5 fix landing as designed.
- **One classifier, one call site per surface.** `fenceDispatch.ts`'s `classifyFence` is now the
  single decision function; `markdownFenceRender.tsx:55` (settled render) and the open-stream
  preview path both call it — the "two if-chains with an implicit precedence contract" that C5
  flagged is gone. `markdownFenceRender.tsx:114-131` wraps the whole thing in `try/catch` and
  degrades to `neverCodeBlockFallback` or `CodeBlock`, never a blank screen or unhandled throw.
- **C7 is fully closed.** `contextSummarized` no longer appears in
  `lib/markdown/assistantMessageContent.ts` or `hooks/useAssistantMessageContent.ts` — verified by
  reading both files; grep for the identifier in `apps/mobile/lib` and `apps/mobile/hooks` returns
  nothing live (only removed from the dependency array and destructure, as C7 recommended).
- **CSP is consistently applied, not just on the paths a prior review happened to touch.**
  `lib/previewSandbox.ts` defines one `injectPreviewCsp` plus per-surface CSP strings
  (`PREVIEW_CSP`, `MATH_PREVIEW_CSP`, `CHART_PREVIEW_CSP`, `PDF_PREVIEW_CSP`), and every WebView
  HTML builder I checked calls it before the document is handed to a `WebView`:
  `katexRender.ts` (KaTeX), `mathHtmlMathjax.ts` (MathJax multiline/eqnarray), `chartPreviewHtml.ts`
  (Vega), `pdfPreviewHtml.ts` (PDF), and `HtmlPreviewModal.tsx`'s `prepareHtmlRunDocument` (the
  sandboxed HTML/CSS/JS Run preview — golden rule #5's one exception). `Molecule3DBlock.tsx`
  renders native SVG, not a WebView, so it has no CSP surface at all — correctly out of scope.
- **Geometry/graph fences are properly Pydantic-gated.** `math_fence.py:81-113`
  (`_validate_geometry`) dispatches on `type` to one of eight `*GeometryBlockSpec` Pydantic models
  (`app/models/math_schemas/geometry.py`) and only accepts the fence if `model_validate` succeeds,
  catching `ValidationError` explicitly. The graph path (`GraphBlockSpec.model_validate` at
  `math_fence.py:369,470,482`) is the same shape. Malformed model output here never reaches a
  render call — it fails validation and the surrounding pipeline substitutes the verified
  canonical fence or drops it.
- **Two other structured-LLM-output paths are correctly Pydantic-gated:**
  `services/todos/reminder_fences.py:50` (`_ReminderFence(BaseModel)`) and `services/calendar.py:80`
  (`CalendarProposalDraft(BaseModel)`) both validate before the reminder/event is persisted.
- **The `sources` fence is fully server-controlled, unlike its sibling `places`.**
  `stream_pipeline.py:300-308`: whenever there were search sources, the model's own `sources` fence
  (if any) is unconditionally stripped (`strip_sources_from_text`) and replaced with
  `format_sources_fence(ctx.search_sources)`, built only from the `WebSearchHit` dataclass the
  gateway returned — the model's text for this fence is never trusted. This closes the exact
  C5-flagged risk ("if the server-side strip is ever missed... raw JSON").
- **Client-side link-opening has a real scheme allowlist**, which is relevant defense-in-depth for
  the `places`-validation gap below: `lib/linkSchemePolicy.ts:22-30,32-44` only allows
  `http/https/mailto/tel/sms/maps/geo` before handing a URL to `Linking.openURL`, explicitly to
  stop a model-emitted `javascript:`/`data:` URL from executing. `lib/openPlaceLink.ts:4-18` and
  markdown link rendering both route through it.

---

## C. Findings — ranked

### Validation integrity (golden rule #6)

---

**O1 — The `places` fence is model-authored on the normal path, contradicting its own registry
annotation, and — unlike `sources` — is never validated before being shown or persisted**
**Severity:** P1 · **Area:** validation / rich-render · **Effort:** S–M

**Evidence:**
- `lib/fenceRegistry.ts:199-206` declares `places` with `owner: "server"`, per the type's own
  docstring at l.19-21: *"server: Recall attaches or rewrites this after the stream."*
- That is not what happens on the normal turn. Two backend prompt constants instruct the model to
  write the fence's JSON itself: `services/web_search/formatting.py:91-98`
  (`"Required: one-sentence intro, then a ```places fence with JSON array [...] url must be a
  Google Maps link to the venue address..."`) and `services/chat/prompt_constants/visuals.py:95-97`
  (`"**Places** (```places) — JSON array of {name, url, note?, address?, price?}..."`). Contrast
  with the same file's l.92-94, which correctly tells the model *not* to emit `geometry`/`graph` —
  those really are server-only, per the registry.
- `services/chat/stream_pipeline.py:309-315`: the server only builds and appends its own
  `format_places_fence(ctx.search_sources)` when
  `"```places" not in assistant_text.lower()` — i.e., only when the model failed to follow the
  instruction above. On the path the prompt is actually optimizing for (the model *does* emit the
  fence), the model's raw JSON — including the `url`, `name`, `note`, `address` fields — passes
  through untouched into the persisted assistant message.
- No Pydantic model validates that JSON at any point. `_is_generic_search_url`
  (`web_search/formatting.py:148-159`) is only ever called from `places_payload_from_hits`
  (l.174-198), which builds the server's own *fallback* seed — it is never applied to the model's
  self-authored fence. Client-side, `lib/placesList.ts:255-261` (`parsePlacesJson`) does
  `JSON.parse` plus ad-hoc `String(row.x ?? "")` coercion with no length/shape schema; the only
  hardening is `resolvePlaceLinkUrl` (l.198-206) substituting a Maps search URL when the URL
  matches a small blocklist of generic search hosts (`isGenericSearchUrl`, l.164-185) — a
  denylist, not a schema.
- Practical consequence: nothing stops the model (whether by hallucination or by content injected
  through a poisoned search snippet it's grounding on) from putting an arbitrary `https://`
  domain, or a name/note string with unbounded length or markdown-breaking characters, into a
  venue the user is invited to tap. The mobile link-scheme allowlist (`linkSchemePolicy.ts`,
  "what's working" above) stops the `javascript:`/`data:` class of attack, but the fence content
  itself is otherwise trusted end to end.

**Why it matters:** golden rule #6 exists so that "the model said so" is never sufficient for
anything that reaches the DB or a tappable UI affordance without a schema gate. `places` is the
one model-authored structured fence in the codebase that has neither — it looks server-owned by
the registry's own metadata, but isn't in practice, so it was presumably assumed covered when
`sources` was hardened.

**Recommended fix:**
1. Fix the registry annotation first (cheap, and it's actively misleading): either change
   `places`'s `owner` to `"model"` in `fenceRegistry.ts`, or change the actual behavior to match
   the declared contract — always regenerate the `places` fence server-side from
   `ctx.search_sources` the same way `sources` already does (drop the "only if missing" gate at
   `stream_pipeline.py:309`), which is the smaller, safer change and makes `places` exactly as
   trustworthy as `sources` already is.
2. If (1) is server-regenerate: `_is_generic_search_url`'s existing blocklist logic already runs
   on every row via `places_payload_from_hits` — no new backend model needed, this alone closes
   the gap.
3. Either way, add a Pydantic model (`PlaceRow(BaseModel)` — `name: str`, `url: HttpUrl | None`,
   `note`/`address`/`price`: bounded-length `str | None`) and validate the parsed rows before they
   are re-serialized into the fence or shown, matching the pattern already used for reminders and
   calendar proposals.

**Do not:** touch the `sources` fence — it is already the model to copy; don't add a domain
allowlist beyond the existing generic-search-host denylist without checking the product
implications of narrowing valid venue links (that's a product decision, not a validation-integrity
one).

---

**O2 — `vocab_quiz` is still a fully parallel, non-Pydantic fence whose parsed output drives DB
writes**
**Severity:** P1 · **Area:** validation · **Effort:** M

**Evidence:**
- `apps/api/app/models/vocab_quiz.py:35-43` — `ParsedVocabQuiz` is a plain `@dataclass(frozen=True)`,
  not a `BaseModel`.
- `parse_vocab_quiz` (l.154-186+) extracts the fence with a regex
  (`VOCAB_QUIZ_FENCE_RE`, l.9), calls raw `json.loads` (l.162), and then hand-validates by
  `dict.get()` with manual type coercion and manual business rules inline
  (`str(data.get("quiz_type") or data.get("quizType") or "").lower()` at l.168; the "require 4
  choices to match the mobile parser" comment and manual `len(choices) < 4` check at l.179-183).
  Any shape it doesn't expect either silently coerces to a default or returns `None` — there is no
  single point where the whole payload's shape is declared and enforced.
- This is not read-only: `apps/api/app/services/projects/quiz_grading.py:159`
  (`_apply_deterministic_quiz_answer`) calls `parse_vocab_quiz` on the raw assistant content, uses
  the result's `.correct`/`.choices` to grade the user's letter answer (l.161-185), and on
  `should_persist` (l.192) proceeds to `apply_quiz_result(...)` and `await session.commit()`
  (l.286) — SM-2 spaced-repetition state that later determines what the user is shown next.
- The mobile side has an independent, differently-shaped parser
  (`lib/parseVocabQuiz.ts`) that C5 already flagged as a parallel path never entering the
  `fenceRegistry.ts` dispatch — that part of C5 was explicitly deferred ("don't fold `vocab_quiz`
  into the registry in the same PR... quiz-state coupling is separate work") and correctly still
  isn't folded in. This finding is narrower and orthogonal to that deferral: it's specifically that
  the **backend's own parse of the same LLM-authored JSON, which the backend then persists,** has
  no schema validation, independent of whether the fence ever joins the mobile registry.

**Why it matters:** this is exactly the shape golden rule #6 is written for — LLM JSON, parsed,
then written to the DB — and it is the one path in the codebase still doing it by hand instead of
with a `BaseModel`. The manual coercions mean a malformed or adversarially-shaped `vocab_quiz`
fence degrades silently (returns `None`, or defaults a field) rather than failing loudly and
visibly the way `ValidationError` does in `math_fence.py`; a future change to the expected shape
(e.g., adding a field) has no schema to update, only prose comments describing the expected keys.

**Recommended fix:** add a Pydantic model (e.g. `VocabQuizFence(BaseModel)` with `word: str`,
`question: str | None`, `correct: str | None`, `quiz_type: Literal["vocab","trivia"] | None`,
`choices: list[tuple[str, str]]` with a `min_length=4` validator mirroring the existing comment at
l.180-183) in `app/models/vocab_quiz.py`, and have `parse_vocab_quiz` call
`VocabQuizFence.model_validate(data)` and catch `ValidationError` to return `None`, keeping the
existing `ParsedVocabQuiz` dataclass as the return type built from the validated model. This is a
mechanical swap of the parsing internals — it does not need to change `quiz_grading.py`'s call
site or grading logic.

**Do not:** fold `vocab_quiz` into `lib/fenceRegistry.ts` in the same change (still correctly
deferred per C5 and `lessons.mdc`'s rejected-quiz-UX notes) — this fix is backend-only validation
hardening, independent of the mobile dispatch question.

---

### Plug-in gaps (registry drift, round two)

---

**O3 — Three new hand-written lang lists have reappeared one layer below the registry**
**Severity:** P2 · **Area:** rich-render · **Effort:** S

**Evidence:**
- `lib/fenceDispatch.ts:50-58` — `DIAGRAM_IDS` is a hardcoded
  `Set(["geometry","graph","chart","mermaid","chemistry","molecule","molecule3d"])`, used at
  l.149 (`classifyOpenFencePreview`) to decide whether an *open, still-streaming* fence should
  preview as a `"diagram"` placeholder. Every one of those seven ids already has
  `fallback: "geometry" | "graph" | "visual"` declared in `fenceRegistry.ts` (l.157-198) — the set
  is fully derivable as `FENCES.filter(f => f.fallback && f.fallback !== "answer" && f.fallback !==
  "sources" && f.fallback !== "places" && f.fallback !== "callout").map(f => f.id)`, but is instead
  maintained by hand a second time.
- `lib/copyBlock.ts:309-322` — `isStructuredDraftLang` hardcodes
  `email|message|sms|reply|twitter|tweet|x|linkedin|social`, which is exactly the union of the
  registry's `email` (l.79), `message` (l.222-228), and `social` (l.215-221) fence lang lists,
  maintained independently a third time. It's called from `fenceDispatch.ts:79` as an extra gate
  on top of `spec.structured`.
- `lib/copyBlock.ts:5-12` — `COPY_LANGS` hardcodes
  `copy|text|message|email|sms|reply`, a fourth independent list, partially overlapping but not
  identical to the other two (it includes `text`, which isn't a registered fence lang at all, and
  omits the `social` family that `isStructuredDraftLang` includes).
- All three currently agree with `fenceRegistry.ts`'s content — I checked each one against the
  registry entries by hand and found no live drift today. That is the good news and also exactly
  the situation C5 described before it drifted: multiple lists, no shared source, no test tying
  them together.

**Why it matters:** this is the same failure mode C5 fixed, one abstraction layer lower. C5's fix
made the *presence* of a fence (`structured`/`neverCodeBlock`/`fallback`) single-sourced; these
three lists encode a second, narrower property — "is this one of the small-deliverable draft
fence families" and "is this one of the always-diagram-preview fence ids" — that the registry
already has enough information to answer (`fallback` kind, and the existing `langs` groupings) but
that nobody wired up. The next fence added to the `email`/`message`/`social` family (a currently
plausible product ask — the codebase already has 5 social platforms) or the next "always show a
loading diagram card while streaming" fence needs a developer to remember three extra places to
update, with nothing failing if they don't; the fence would just silently skip the streaming
preview treatment or the draft-vs-prose heuristic gate, degrading to a plain code/prose block
instead — not a crash, just quietly wrong.

**Recommended fix:** add two derived helpers to `fenceRegistry.ts` — e.g.
`isDraftFamilyLang(lang)` (`fenceSpecForLang(lang)?.id` is one of `email`/`message`/`social`) and
`isAlwaysDiagramPreviewLang(lang)` (`fenceSpecForLang(lang)?.fallback` is `geometry`/`graph`/`visual`)
— and have `fenceDispatch.ts`'s `DIAGRAM_IDS` check and `copyBlock.ts`'s `isStructuredDraftLang`
call those instead of re-listing langs. Leave `COPY_LANGS`'s `text` entry alone (it is intentionally
broader than any registered fence — it is the "no fence tag at all" catch-all) but source the
`copy`/`email`/`sms`/`reply`/`message` part of it from the registry too.

**Do not:** merge `DIAGRAM_IDS` and `isStructuredDraftLang`'s intents into one property on
`FenceSpec` — they answer genuinely different questions (open-stream preview kind vs.
draft-content heuristic gate) about overlapping but different fence sets; keep them as two derived
helpers, the same "declare the difference, don't collapse it" principle the registry's own
docstring already states for `structured` vs `neverCodeBlock`.

---

**O4 — No round-trip test exists for render/copy/fallback across registered fence ids, as C5
itself recommended**
**Severity:** P2 · **Area:** test coverage · **Effort:** S

**Evidence:**
- `lib/__tests__/fenceRegistry.test.ts` is a characterization test of the lookup functions
  (`isStructuredFenceLang`, `isNeverCodeBlockLang`, `fallbackKindForLang`, etc.) against literal
  lists that mirror the pre-registry state (l.21-102) — it asserts the *table*, not that any fence
  actually renders.
- `lib/__tests__/fenceDispatch.test.ts` asserts `classifyFence(lang, body).kind` for a curated set
  of lang/body pairs (l.1-55) — it stops at the *decision*, never calls
  `renderRichFenceById`/`renderCopyStyleBlock`/`classifyFallbackFence` to check what actually gets
  produced for that decision.
- I found no test file anywhere under `apps/mobile` that iterates `FENCES` and asserts
  `renderRichFenceById(spec.id, ...)` returns a non-null element for representative valid content
  of every id, or that `classifyFallbackFence` produces a matching `FallbackFence.kind` for every
  `fallback`-bearing spec.
- Concretely reproducible gap: `RichFence.tsx:117-123` has `case "copy": case "sources": case
  "learning_launch": return null;` plus a bare `default: return null;`. Add a 23rd `FenceId` to
  `fenceRegistry.ts` today, wire it nowhere in `RichFence.tsx`'s switch, and every existing test
  (registry, dispatch, richBlocks, copyBlock, markdownFenceRender) still passes — the new fence
  silently renders nothing wherever `classifyFence` returns `kind: "rich"` for it, with no failing
  test anywhere in the suite to catch it.

**Why it matters:** this is the exact gap C5 named as its own follow-up ("Add a test asserting
every registered id round-trips through render, copy, and fallback") and it is still open one
registry-hardening PR and three "output-routing review" PRs later. The registry makes *adding* a
list entry cheap; without this test, it does not make *forgetting the renderer* visible.

**Recommended fix:** one new test file, e.g. `components/rich/__tests__/RichFence.roundtrip.test.tsx`,
that iterates `FENCES` and, for each `structured` id, calls `renderRichFenceById` with a small
fixture body per id (most already exist as fixtures in `richBlocks.test.ts`/`copyBlock.test.ts` —
reuse them) and asserts the result is not `null` for the ids that are supposed to render something
visible (the deliberate `null` cases — `copy`, `sources`, `learning_launch` — get an explicit
"renders nothing by design" assertion instead, so a future accidental `null` for a *different* id
still fails). A second small test over `fallback`-bearing ids asserts `classifyFallbackFence`
returns the matching `kind`.

**Do not:** try to snapshot-test the full rendered component trees (KaTeX/Mermaid/chart WebView
output) — that's brittle and out of scope for this test's purpose, which is "does the id have a
wired renderer at all," not visual regression.

---

### Consistency (backend prompt ↔ mobile registry)

---

**O5 — `places` is the only prompt-instructed fence with a registry `owner` that doesn't match
who actually emits it (see O1); no other orphaned fence types found**
**Severity:** P3 · **Area:** consistency · **Effort:** — (fix folds into O1)

**Evidence:** I cross-checked every fence the backend's prompt constants
(`services/chat/prompt_constants/{format,writing,visuals}.py`, `services/web_search/formatting.py`)
instruct the model to emit against `fenceRegistry.ts`'s `owner` field:
- `email`, `mermaid`, `chart`, `smiles`/`chemistry`, `sms`/`message`/`reply`,
  `twitter`/`tweet`/`x`/`linkedin`/`social` are all prompted as model-emittable and are all
  `owner: "model"` in the registry — consistent.
- `geometry`/`graph` are explicitly prompted *against* ("Do not emit ```geometry or ```graph
  JSON... Recall attaches the labeled diagram" — `visuals.py:92-94`) and are `owner: "server"` in
  the registry — consistent.
- `places` is prompted *for* (`visuals.py:95-97`, `web_search/formatting.py:91-98`) but is
  `owner: "server"` in the registry — the one inconsistency, covered fully by O1.
- I found no fence type referenced in the prompt constants that is entirely absent from
  `fenceRegistry.ts` (no orphan on the backend side), and no `FenceId` in the registry whose
  `owner: "model"` claim has no corresponding prompt instruction anywhere I could find (no orphan
  on the mobile side, modulo `vocab_quiz`/calendar/reminder/settings fences, which are documented
  in the registry's own header comment as deliberately out-of-registry, l.24-25).

**Why it matters:** listed separately from O1 only because it's a distinct *symptom* (a doc/reality
mismatch you'd hit independently while auditing "who can emit what") of the same root cause; the
fix is the same one line change described in O1's recommendation.

**Recommended fix:** covered by O1(1).

**Do not:** open a second PR for this — it's one line, fix it alongside O1.

---

## D. Weak / unwanted / missing inventory

| Item | Status | Evidence | Recommend |
|---|---|---|---|
| `lib/fenceRegistry.ts` as single source of truth | **Fixed (C5)** | `richBlocks`/`copyBlock`/`fallbackFence`/`markdownFenceRender` all derive from it | Keep as-is |
| `contextSummarized` dead plumbing | **Fixed (C7)** | absent from `assistantMessageContent.ts`, `useAssistantMessageContent.ts` | Keep as-is |
| CSP on WebView rendering paths | **Fixed (prior R5 + verified here)** | `previewSandbox.ts` `injectPreviewCsp` called from every math/chart/PDF/HTML-preview builder | Keep as-is |
| `sources` fence | Sound — fully server-regenerated every turn | `stream_pipeline.py:300-308` | Keep as-is; model of what `places` should do |
| `places` fence | **Weak** — model-authored, unvalidated, mislabeled `owner` | `visuals.py:95-97`, `web_search/formatting.py:91-98`, `stream_pipeline.py:309-315` | Fix (O1/O5) |
| `vocab_quiz` fence backend parse | **Weak** — manual dict parsing feeds DB writes, no Pydantic | `models/vocab_quiz.py:154-186`, `quiz_grading.py:159-286` | Fix (O2) |
| `geometry`/`graph` fence validation | Sound — full Pydantic model family | `math_fence.py:81-113`, `models/math_schemas/{geometry,graph}.py` | Keep as-is |
| reminder / calendar structured fences | Sound — `BaseModel` gates before persistence | `reminder_fences.py:50`, `calendar.py:80` | Keep as-is |
| `fenceDispatch.ts` / `copyBlock.ts` new lang lists | **Weak** — 3 new hardcoded lists one layer below the registry | `fenceDispatch.ts:50-58`, `copyBlock.ts:5-12,309-322` | Fix (O3) |
| Round-trip render/copy/fallback test | **Missing** — C5's own recommended test was never written | no test iterates `FENCES` against `renderRichFenceById` | Fix (O4) |
| Unrecognized/hallucinated fence tags | Acceptable — falls through to a labeled `CodeBlock`, never silently dropped | `fenceDispatch.ts:95,117-119` → `markdownFenceRender.tsx:99-106` | Keep as-is |
| Link-scheme allowlist for model-emitted URLs | Sound — defense-in-depth even where fence content isn't schema-validated | `lib/linkSchemePolicy.ts:22-30` | Keep as-is |

---

## E. Executive summary

The Aug 2026 review's fence-dispatch finding (C5) and dead-plumbing finding (C7) were both
correctly implemented: `lib/fenceRegistry.ts` is a genuine single source of truth that
`richBlocks.ts`, `copyBlock.ts`, `fallbackFence.ts`, and `markdownFenceRender.tsx` all derive from,
`contextSummarized` is fully deleted, and CSP is now consistently applied across every WebView
rendering path in the app (KaTeX, MathJax, Vega charts, PDF, HTML Run preview). What's newly weak
is one layer below that fix and one layer outside its stated scope: a follow-up "output-routing
review" (landed 2026-09-04) introduced three more hand-written language lists
(`fenceDispatch.ts`'s `DIAGRAM_IDS`, `copyBlock.ts`'s `isStructuredDraftLang`/`COPY_LANGS`) that
duplicate information the registry already has instead of deriving from it — currently in sync,
but the same drift risk C5 fixed, one step removed; and C5's own recommended round-trip render
test was never written, so a fence added to the registry with no wired renderer would pass every
existing test today. Separately, golden rule #6 (Pydantic validation before DB write) has two open
gaps that predate and are independent of the registry work: the `vocab_quiz` fence is parsed with
hand-rolled `dict.get()` logic into a plain dataclass before driving SM-2 grading writes to the DB,
with no schema validation at all; and the `places` fence — despite the registry itself annotating
it `owner: "server"` — is actually authored by the model on the normal path (the prompt instructs
it to write the JSON directly), and unlike its sibling `sources` fence (which the server always
strips and regenerates from validated data), the model's `places` JSON is never schema-validated
or checked against the same URL-safety logic the server applies to its own fallback construction
of that fence — the one inconsistency found between backend prompt instructions and mobile
registry metadata. All five findings are concrete, evidence-cited, and independently fixable; none
requires touching the streaming transport.
