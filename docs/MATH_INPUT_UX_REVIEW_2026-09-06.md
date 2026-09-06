# Math Input UX Review — 2026-09-06

Scope: the student-facing math **input** experience — camera "Scan Math," the on-screen
math symbol keyboard/toolbar, fillable LaTeX templates, Unicode-paste normalization, and
the unit converter pad. Companion review to the backend vision-extraction accuracy audit;
this review is the **mobile UX** half — what a 12–17-year-old actually sees, taps, and gets
confused by. Read-only: no source files were modified.

Reviewed in full before this audit: `docs/math.md` ("Composer input (mobile)," "Camera math
is a specialization of step 1"), plus every file listed in scope (camera scanner UI/geometry,
backend vision-extract service, `turn_prep/attachments.py`, the math keyboard hook/UI/symbol
table, draft-slot template logic, paste normalization, unit converter, and their test suites).

## Executive summary

The **hard-bug count is low and the automated test suites are all green** — 264/264 mobile
Jest tests and 61/61 backend pytest tests in scope pass. The math keyboard's template/caret
logic (`mathDraftSlots.ts`) is well-designed: slot state is *derived fresh from the LaTeX text
on every keystroke* rather than tracked in parallel state, so there is no separate slot model
that can desync from the text, nest incorrectly, or survive backgrounding incorrectly — it's
stateless by construction. The unit converter's conversion factors are exact SI constants and
insertion into the composer is a single tap.

The real risk to a launch aimed at "wanted by all students" is **three specific defects that
land squarely on the target user (a kid photographing homework or pasting from a study site),
each demonstrated by direct execution, not speculation**:

1. **Tapping "Scan Math" silently deletes whatever the student had already typed** — a hard
   data-loss bug, not a UX nit (`useChatSend.ts:596-600`).
2. **Pasting `√9` from a textbook or search result corrupts it to `\sqrt{}9`** (empty radical
   + a stray `9`), verified by direct execution of `normalizePastedMath` — the single most
   common "copy the answer key" glyph is mishandled (`mathPasteNormalize.ts:101-102`).
3. **The camera-scan flow has zero confirm/edit step.** The vision model's read of the photo
   is injected straight into the prompt sent to the LLM (and into the SymPy-verification path)
   with no confidence signal in its own schema and no on-screen review — a misread digit turns
   into a *confidently "verified"* answer to a problem the student never actually asked.

Two further findings are best framed as **discoverability defects rather than bugs**: the
proactive math-keyboard chip (`textLooksLikeMath()`) misses the single most common way a
student would type a homework question ("what's 7 x 8", "convert 5 miles to km") while
simultaneously firing on any ordinary sentence that happens to contain a dollar amount ("can I
borrow $20") — it is both too narrow and too broad, for two independent, fixable reasons.

None of this requires a redesign. Every finding below has a small, scoped fix.

## Test results (exact commands run)

**Mobile (Jest), the exact 10 files in scope:**

```
$ cd apps/mobile && npx jest lib/__tests__/mathScannerRegion.test.ts \
    lib/__tests__/mathKeyboardSymbols.test.ts lib/__tests__/formatMathInput.test.ts \
    lib/__tests__/mathPasteNormalize.test.ts lib/__tests__/mathDraftSlots.test.ts \
    lib/__tests__/mathComposerIntent.test.ts lib/__tests__/mathComposerChange.test.ts \
    lib/__tests__/unitConverter.test.ts components/__tests__/ChatComposer.test.tsx \
    components/__tests__/AttachmentSourceSheet.test.tsx

Test Suites: 10 passed, 10 total
Tests:       264 passed, 264 total
Time:        6.596 s
```

**Backend (pytest), the vision-extract + turn_prep files in scope:**

```
$ cd apps/api && uv run pytest app/tests/services/test_math_image_extract.py \
    app/tests/services/test_math_image_extract_advanced.py \
    app/tests/services/test_turn_prep_attachments.py -q

61 passed in 6.58s
```

`pnpm install` in `apps/mobile` had already completed in this environment (async setup), so
these ran against the real installed toolchain, not a static read — every claim below that
cites a Jest/pytest run is a live execution, not a trace.

## Ranked findings (hard bugs)

### P0-1 — "Scan Math" silently destroys unsent composer text (data loss)

**Severity:** Critical · **Area:** Camera scanner / composer integration · **Effort:** Small

**Evidence** — `apps/mobile/hooks/useChatSend.ts:596-600`:

```596:600:apps/mobile/hooks/useChatSend.ts
const handleMathScanCaptured = useCallback((pending: PendingAttachment) => {
  setPendingAttachment(pending);
  setInput(defaultMathCameraPrompt());
  setMathScannerOpen(false);
}, [setInput, setPendingAttachment]);
```

`setInput(defaultMathCameraPrompt())` is an unconditional overwrite — it does not check whether
`input` is already non-empty. `defaultMathCameraPrompt()` just returns the fixed string
`"Solve the math problem in this image step by step."` (`apps/mobile/lib/mathCameraPrompt.ts:10`,
`apps/mobile/lib/attachments.ts:151-153`).

**Repro trace:** student types `"I got confused on part b, can you check"` into the composer,
then remembers they should attach a photo and taps the attach button → Scan Math → crops →
shutter. `handleMathScanCaptured` fires, and the sentence they just wrote is gone, replaced with
the boilerplate prompt, with no undo and no warning.

**Why it matters:** this is exactly the sequence a real student follows — type context first,
then realize a photo would help. Losing typed text with zero feedback is the kind of bug that
makes a student distrust the app ("it ate what I wrote") on the very flow this feature exists
to support. It is not a corner case; any composer text present before opening the camera
triggers it, 100% of the time.

**Recommended fix:** only set the boilerplate prompt when `input` is empty/whitespace;
otherwise append the attachment without touching existing text (mirrors how the regular
photo/file attach paths already behave — they never call `setInput` at all, per
`apps/mobile/components/chat/ChatComposer.tsx`'s `ComposerAttachmentPreview` usage sitting
alongside untouched input).

**Do not:** silently merge the boilerplate into existing text either (e.g.
`input + "\n" + prompt`) — that reintroduces confusing auto-generated text next to a student's
own words. Only fill the prompt when there is nothing to preserve.

### P0-2 — Pasting `√9` (or any bare `√n`) corrupts the expression instead of converting it

**Severity:** Critical · **Area:** Paste normalization · **Effort:** Small

**Evidence** — `apps/mobile/lib/mathPasteNormalize.ts:100-102`:

```100:102:apps/mobile/lib/mathPasteNormalize.ts
s = s.replace(/√\s*\(([^()]*)\)/g, "\\sqrt{$1}");
s = s.replace(/√/g, "\\sqrt{}");
```

Line 101 only fires when the radicand is already parenthesized (`√(16)`). For the far more
common bare form — `√9`, `√16 + 2`, or any handwritten-style textbook/search-result paste with
no parens — line 102 fires instead and replaces the `√` glyph with an **empty** `\sqrt{}`,
leaving the radicand as plain text *outside* the radical.

**Verified by direct execution** (`normalizePastedMath` called from a throwaway Jest test,
output captured verbatim, then removed — no source files were left modified):

```
RESULT:  normalizePastedMath("√9")        → "$\\sqrt{}9$"
RESULT2: normalizePastedMath("√16 + 2")   → "$\\sqrt{}16 + 2$"
```

`$\sqrt{}9$` renders as an empty radical sign immediately followed by a bare `9` — visually and
mathematically nothing like `√9`. Worse, this string is what gets sent into the SymPy pipeline
as the student's actual math input, so a "verify √9 = 3" ask silently becomes "verify (empty
radical) and separately 9," which will not parse as the student's intended expression.

**Why it matters:** `√` is the single glyph in the entire coverage set (√, ², ³, ×, ÷, π, θ, ≤,
≥, ≠, ∞, ½) that a student is *most* likely to paste bare, straight off a textbook PDF or a
Google "people also ask" snippet — no one copies `√(9)` with parens by hand. The one glyph the
task explicitly calls out as a completeness check is the one that's actively broken, not
missing.

**Recommended fix:** capture the radicand instead of discarding it. A minimal fix: match a
following run of digits/simple-expression characters and wrap them, e.g.
`s.replace(/√\s*(\d+(?:\.\d+)?)/g, "\\sqrt{$1}")` before the parenthesized-form rule, only
falling back to the empty `\sqrt{}` (leaving the caret inside for the student to fill) when
nothing recognizable follows. Add a regression test asserting `normalizePastedMath("√9")` →
`"$\\sqrt{9}$"` next to the existing `mathPasteNormalize.test.ts` cases — the existing suite has
no case for a bare (unparenthesized) `√` despite testing many other glyphs, which is how this
shipped.

**Do not:** widen the bare-digit-capture regex to also swallow trailing operators/variables
(`√9x` should stay `\sqrt{9}x`, not `\sqrt{9x}`) — keep the capture narrow to a numeric/simple
token, matching how the parenthesized branch already scopes to `[^()]*`.

### P1-1 — Camera-scan photo → SymPy pipeline has no confirm/edit step; extraction is blind-trusted

**Severity:** High · **Area:** Camera scanner UX / vision extraction integration · **Effort:** Medium

**Evidence, three layers stacking into one gap:**

1. The extraction schema has **no confidence signal at all** — it is a binary
   `found: bool` plus the parsed fields, nothing else
   (`apps/api/app/services/math_image_extract.py:1-144`; schema in
   `apps/api/app/models/math_schemas/algebra.py`). The service either confidently returns a
   *fully-formed* equation or returns `None` on outright parse/network failure — there is no
   middle state the mobile app could render as "not sure, please check."
2. The result is injected straight into what the LLM sees, with **no mobile-side gate**:

```270:279:apps/api/app/services/chat/turn_prep/attachments.py
extracted = await math_image_extract_service.extract_equation_from_image(
    settings, content_type=mime, data=image_bytes
)
if extracted is not None:
    image_math_extract = extracted
    suffix = math_image_extract_service.camera_math_user_suffix(extracted)
    # Prompt/stream path sees Solve: for equations; stored bubble
    # keeps the image marker + original caption only.
    if suffix:
        content = f"{content}\n\n{suffix}"
```

   Note the comment itself: the model-facing `content` gets `"\n\nSolve: {lhs} = {rhs}"`
   appended, but the **persisted user bubble** (`user_content`, not shown here) stays just the
   image + boilerplate caption. The student's own chat history never shows what was actually
   extracted — only the model's eventual reply does, and only if the model happens to restate
   the equation in its answer.
3. On the mobile side there is no intermediate screen at all: `MathEquationScanner.tsx`'s
   `capture()` (`apps/mobile/components/MathEquationScanner.tsx:117-173`) crops the photo,
   calls `onCaptured`, and immediately `onClose()`s the modal. `handleMathScanCaptured`
   (P0-1 above) turns that straight into a send-ready attachment with no pause.

**Why it matters:** the explicit product goal is a flow "wanted by all students" doing real
homework — which means genuinely messy handwriting, glare, and cramped margins, not clean
printed textbook photos. A misread `7` as `1`, or a missed negative sign, produces a
SymPy-verified answer to a problem the student never actually posed, with the app presenting it
with exactly as much confidence as a correctly-read problem. A student has no way to know their
photo was misread unless they independently re-derive the answer or happen to notice the
model's restated equation doesn't match their own paper — an unreasonable ask of the target
age group, and the opposite of "wanted by all students": it actively erodes trust the first
time it happens on a graded assignment.

**Recommended fix:** add a lightweight confirm step between capture and send — even a single
non-blocking line above the composer ("Read as: `2x + 3 = 7` — looks right?") sourced from the
same `extracted` object already computed server-side (or a fast client-side OCR summary before
the full turn), with a one-tap "that's wrong, let me retype" escape hatch that keeps the photo
attached but lets the student correct the equation as typed text instead. This does not require
blocking the flow for well-lit printed photos — it requires *surfacing* the one signal (the
model's own read of the image) that currently exists only inside the LLM prompt and never
reaches the screen.

**Do not:** try to solve this by adding a numeric "confidence score" to the vision-extraction
prompt — vision-LLM confidence self-reports are notoriously uncalibrated (a model asked to rate
its own OCR confidence will say "95%" on a misread as often as a correct one). The fix belongs
in the mobile UX layer (show the read-back, let the student correct it), not in inventing a
number the model can't reliably produce. This is explicitly the boundary with the sibling
extraction-accuracy review — that review owns whether the *extraction* is accurate; this
finding is that **whatever it produces, right or wrong, currently never becomes visible or
editable to the student before being spent as a turn.**

### P1-2 — Camera permission permanently denied is a dead end

**Severity:** High · **Area:** Camera scanner · **Effort:** Small

**Evidence** — `apps/mobile/components/MathEquationScanner.tsx:183-189`:

```183:189:apps/mobile/components/MathEquationScanner.tsx
) : !permission.granted ? (
  <View style={s.center}>
    <Text style={s.permissionText}>{t("chat.math_scan_permission")}</Text>
    <Pressable style={s.permissionBtn} onPress={() => void requestPermission()}>
      <Text style={s.permissionBtnText}>{t("chat.math_scan_allow_camera")}</Text>
    </Pressable>
  </View>
```

`expo-camera`'s `permission` object exposes `canAskAgain` — false once the OS has permanently
denied the prompt (e.g. after "Don't allow" is tapped twice on iOS, or the user manually revokes
it in Settings). This component never reads `permission.canAskAgain`, and there is no
`Linking.openSettings()` call anywhere in the file (confirmed by grep — zero matches for
`canAskAgain`, `openSettings`, or `Linking` in `MathEquationScanner.tsx`). Once permanently
denied, `requestPermission()` on iOS resolves immediately without showing the native prompt
again, so tapping "Allow camera" does nothing — silently, with no changed state, no error, and
no way out except backing out of the whole feature and hunting for Settings unaided.

**Why it matters:** this is a common real path for a 12–17-year-old — a shared/school-managed
device where a sibling or parent denied camera access once, or the student panic-tapped "Don't
Allow" the first time a permission dialog ever appeared to them. Once in this state, "Scan
Math" — one of the two headline math-input features — is permanently, silently unusable, with
a button that looks actionable but is not.

**Recommended fix:** branch on `permission.canAskAgain`: when false, swap the button's copy and
action to "Open Settings" → `Linking.openSettings()`, matching the pattern already presumably
used elsewhere in the app for other permission-gated features (camera roll, notifications).

**Do not:** auto-open Settings without a tap (iOS/Android both require an explicit user action
before backgrounding the app to Settings) — keep it as a clearly-labeled button, just make the
button actually do something once `canAskAgain` is false.

## UX friction points

These are not counted above as ranked bugs because they involve product/heuristic judgment
calls rather than a single clearly-wrong line, but they directly affect whether a first-time
student discovers and successfully uses the math tools. Each is grounded in the actual code
path and copy, not speculation, with direct execution where the claim is about runtime
behavior.

- **The proactive math-keyboard chip misses the most common way students actually type a
  question.** `textLooksLikeMath()` (`apps/mobile/lib/math/mathComposerIntent.ts:15-26`) is
  meant to surface the chip before the student has to know a toggle icon exists. Executed
  directly against realistic inputs:

  ```
  "what is 7 x 8"              → false
  "what is 12 divided by 4"    → false
  "2+2"                        → false
  "convert 5 miles to km"      → false
  "solve for x: 2x+3=7"        → true
  "x^2 = 4"                    → true
  ```

  The heuristic requires an explicit LaTeX-ish marker (`\frac`, `$`, `^`, `√`, an algebra
  keyword like "solve"/"equation") or a paste-sized delta. Bare arithmetic phrased as an
  English question — arguably the single most common thing a middle-schooler types — never
  trips it, so the chip that's supposed to proactively teach a first-time user "there's a math
  keyboard" never appears for exactly that user's first, simplest query. It only shows up once
  a student is already typing something LaTeX-flavored, at which point they didn't need the
  discoverability nudge.

- **The same chip is falsely triggered by any bare currency amount in ordinary prose**, for an
  identifiable, fixable reason. `MATH_MARKERS` in the same file starts with a literal `\$`
  (`apps/mobile/lib/math/mathComposerIntent.ts:8`), intended to catch inline `$...$` LaTeX
  delimiters, but the regex only checks for *the presence of one dollar sign*, not a matching
  pair. Executed directly:

  ```
  "I only have $6 left for lunch"   → true
  "can I borrow $20"                → true
  "the shirt costs $6"              → true
  ```

  None of these are math-notation asks; they're everyday sentences a teenager chatting with a
  homework helper would plausibly send. The chip (and the reactive math preview UI it opens
  the door to) popping up over ordinary chat prose is the "too broad, intrusive" failure mode
  the review explicitly asked about, and it has a narrow root cause: `\$` should require a
  second `$` later in the string (or reuse the existing paired-dollar check already present two
  lines below it — `/\$[^$\n]+\$/` in `mathPasteNormalize.ts:64` — rather than a bare
  single-character class test).

- **The 20-second vision-extraction wait reuses generic "calculating" copy, not scan-specific
  copy.** The rotating status labels shown while `on_status("calculating")` is active
  (`apps/mobile/lib/i18n/en.json:202-204`: "Crunching the numbers…", "Working through the
  math…", "Solving equations…") are the same three strings used for an ordinary typed-equation
  SymPy solve. A student who just took a photo gets no explicit "reading your photo" signal
  distinguishing a vision-extraction wait (which can legitimately run close to the 20s
  `math_image_extract_timeout_seconds` ceiling) from a typed-equation solve (which is normally
  much faster) — the rotation is a nice touch generally, but it doesn't set the specific
  expectation "this one takes longer because there's a photo to read," which is the case where
  a silent 15-20s wait is most likely to make a student think the app is stuck.

- **No post-capture preview before the photo is attached and sent.** `capture()`
  (`MathEquationScanner.tsx:117-173`) crops and immediately calls `onCaptured` +
  `onClose()` — there is no "here's your crop, looks good?" pause. In practice this is
  softened by the crop-region UI itself: state (`region`, `busy`, `error`) is not reset when
  `visible` toggles false (the component returns `null` at the very end of the function, after
  all hooks have already run and updated state), so re-opening the scanner after a bad capture
  reopens with the previous crop rectangle still in place rather than the default frame — a
  real, verified piece of retry-friendliness. But the *photo itself* is never shown back to the
  student before it's attached; the only preview is the resulting 88×112px thumbnail in the
  composer (`ComposerAttachmentPreview.tsx`), which is too small to judge whether handwriting
  came out legible before spending a turn on it.

- **Symbol-toolbar grouping is reasonable, not buried.** `MATH_KEYBOARD_GROUPS` is ordered
  `["basics", "trig", "calc", "greek", "converter"]`
  (`apps/mobile/lib/mathKeyboardSymbols.ts:3`), rendered as tabs in that exact order
  (`MathKeyboardBar.tsx:126-141`), and "basics" already contains the operators a student
  actually reaches for first — fraction, √, exponent/subscript, absolute value, π, ≤/≥/≠, `<`/`>`
  (`mathKeyboardSymbols.ts:36-47`) — with trig/Greek correctly demoted to their own later tabs.
  This is called out here as a friction point that **turned out not to be one** on inspection —
  worth stating explicitly since the task asked to check whether trig/Greek were "prominent"
  ahead of basics; they are not.

## What's working

- **Fillable-template slot handling is well-architected, not just well-tested.**
  `mathDraftSlots.ts` computes `DraftNode`s (frac/sqrt/script/abs/group) fresh from the LaTeX
  string on every call via `findDraftNodes` — there is no separate "which slot is active" model
  state that can drift out of sync with the text. Nesting one template inside another (a `\sqrt`
  inside a `\frac` numerator, etc.) is naturally handled because the parser recurses through
  brace groups positionally rather than tracking a flat slot list; backgrounding the app or
  navigating away loses nothing beyond ordinary React state persistence, because there is no
  extra state to lose. `spliceMathBackspace` (`mathDraftSlots.ts:272-364`) specifically protects
  template delimiters (`{`/`}`) from accidental deletion and collapses an emptied template back
  to plain text rather than leaving dangling braces. All 514 lines' worth of
  `mathKeyboardSymbols.test.ts` plus `mathDraftSlots.test.ts` pass, and static reading confirms
  the design, not just the test count.
- **Scan-region geometry is genuinely resistant to degenerate states.**
  `clampScanRegion` (`mathScannerRegion.ts:33-39`) enforces `MIN_REGION_RATIO = 0.12` /
  `MAX_REGION_RATIO = 0.92` on both axes before clamping position — a pinch cannot shrink the
  crop to zero or blow it up off-screen, and `scaleScanRegion` resizes around the region's own
  center rather than the screen's, which is the intuitive pinch behavior. `maxPointers(1)` on
  the pan gesture (`MathEquationScanner.tsx:92-103`, with an explanatory comment) specifically
  prevents the classic two-finger-pinch-also-triggers-pan conflict.
- **The unit converter is numerically correct and well-connected, not a bolted-on side
  feature.** Conversion factors are exact SI constants — 1 mile = 1609.344 m, 1 lb =
  0.45359237 kg, temperature uses proper affine Kelvin round-trips
  (`unitConverter.ts:145-165`) — verified by direct execution (1 mi → km, 32°F → 0°C, 1 kg →
  2.20462…lb, 100°C → 212°F all matched the true conversion factors). Its "Insert" button
  writes the formatted result plus unit directly into the composer as a single LaTeX token
  (`converterInsertSnippet`, `unitConverter.ts:215-217`) rather than requiring a manual copy/paste
  round-trip, and "Ask" hands off to the LLM instead when the student wants an explained
  conversion rather than just the number.
- **Rich, useful discoverability nudge for the one case that's easy to miss entirely:** pasting
  an image directly into the text field (rather than using the attach sheet) triggers
  `onImageOnlyPaste` → a one-line hint, `"That paste looks like an image. Use the math scanner
  instead?"` (`chat.math_paste_scan_hint`, `en.json:154`), which is exactly the moment a student
  who screenshotted a problem from another app would otherwise be confused why nothing appears
  in the composer.
- **"Scan Math" is the first, most prominent row in the attach sheet**, not buried below the
  generic camera/photo/file options (`AttachmentSourceSheet.tsx:44-49`), which is the right call
  for a feature the product wants students to actually find.

## Swept and clean

Reviewed with no material findings, beyond what's already folded into the sections above:

- `apps/mobile/lib/math/formatMathInput.ts` — `x2` → `x^2` and spacing/relation formatting is
  narrowly scoped and covered by `formatMathInput.test.ts` (part of the 264 passing tests); no
  edge case surfaced that produces malformed LaTeX from reasonable input.
- `apps/mobile/lib/math/mathComposerChange.ts` — caret-preserving text-change application;
  passes `mathComposerChange.test.ts` and the logic (diff prefix/suffix, replay against a pinned
  selection) matches its stated purpose with no off-by-one found on inspection.
- `apps/mobile/lib/math/mathClipboard.ts` — small, single-purpose image-only-clipboard check;
  nothing to flag.
- `apps/mobile/components/chat/MathConverterUnitSheet.tsx` — unit picker sheet; straightforward,
  no correctness or UX issues found.
- Backend `apps/api/app/services/chat/turn_prep/attachments.py` attachment resolution/dedup
  logic upstream of the math-specific branch (lines 1-255) — outside this review's UX mandate
  and already covered by the 61 passing `test_turn_prep_attachments.py` cases; no math-specific
  issue found beyond P1-1 above.
- `apps/api/app/models/math_schemas/intent.py` / `algebra.py` schema validation — Pydantic
  models validate structurally as expected; the *absence* of a confidence field is called out
  as part of P1-1, not a separate schema bug.

## Non-goals of this review

- **Vision-extraction accuracy itself** (whether the vision model correctly reads a given
  handwritten photo) — explicitly owned by the sibling backend extraction-accuracy review. This
  review's P1-1 finding is scoped to "the mobile app has no way to catch or correct a wrong
  read," not "the model reads photos badly."
- **SymPy solve correctness** downstream of a correctly-extracted equation — out of scope; this
  is an input/UX review, not a math-engine review.
- **General composer/attachment infrastructure** not specific to math (upload retry, generic
  file-type handling, non-math paste behavior) — reviewed only where it intersects the math
  flows in scope.
- **i18n/localization completeness** of the strings cited above — only the `en.json` copy was
  checked for accuracy of the English UX; parity across the other 8 locale files was not
  audited here.
- **Accessibility** (screen-reader labels, contrast) beyond noting that accessibility props
  (`accessibilityLabel`, `accessibilityRole`) are present on the interactive elements touched
  during this review — a full a11y pass was not performed.
