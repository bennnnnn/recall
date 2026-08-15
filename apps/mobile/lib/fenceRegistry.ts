/**
 * Single source of truth for fence identity and per-fence behaviour flags.
 *
 * Adding or removing a fence type used to mean editing four independently
 * maintained language lists — `STRUCTURED_LANGS` in richBlocks.ts, the
 * code-block exclusions and copy-block list in copyBlock.ts, the pre-dispatch
 * lists in markdownFenceRender.tsx, and the crash-path classifier in
 * fallbackFence.ts. They had already drifted: `sources` and `copy` were known
 * to copyBlock alone, while 18 langs including `chart`, `mermaid` and `steps`
 * were known only to richBlocks.
 *
 * The two sets below are intentionally NOT unified — `structured` (does this
 * enter the rich renderer?) and `neverCodeBlock` (is this excluded from
 * syntax-highlighted code rendering?) genuinely differ, and collapsing them
 * would change what renders. The point is that the difference is now declared
 * per fence and reviewable in one table, instead of being an accident of which
 * list someone remembered to update.
 */

export type FenceId =
  | "answer"
  | "callout"
  | "chart"
  | "chemistry"
  | "clock"
  | "collapsible"
  | "comparison"
  | "copy"
  | "email"
  | "geometry"
  | "graph"
  | "keyvalue"
  | "math"
  | "mermaid"
  | "message"
  | "places"
  | "quote"
  | "social"
  | "sources"
  | "steps";

export type FallbackKind = "callout" | "geometry" | "graph";

export type FenceSpec = {
  id: FenceId;
  /** Every language tag that resolves to this fence. */
  langs: readonly string[];
  /** Routed through the rich fence renderer (was `STRUCTURED_LANGS`). */
  structured: boolean;
  /** Never rendered as a syntax-highlighted code block (was copyBlock's list). */
  neverCodeBlock: boolean;
  /** How the crash-fallback renderer degrades this fence, when not plain code. */
  fallback?: FallbackKind;
};

export const FENCES: readonly FenceSpec[] = [
  { id: "email", langs: ["email"], structured: true, neverCodeBlock: true },
  { id: "quote", langs: ["quote", "blockquote"], structured: true, neverCodeBlock: false },
  {
    id: "comparison",
    langs: ["compare", "comparison", "pros"],
    structured: true,
    neverCodeBlock: false,
  },
  {
    id: "keyvalue",
    langs: ["kv", "keyvalue", "fields"],
    structured: true,
    neverCodeBlock: false,
  },
  { id: "steps", langs: ["steps", "step"], structured: true, neverCodeBlock: false },
  {
    id: "collapsible",
    langs: ["details", "collapse", "summary"],
    structured: true,
    neverCodeBlock: false,
  },
  // `latex`/`tex` are aliases of `math`. The model is told never to emit
  // those tags, but it drifts; the settled path already retags closed
  // fences. Registering them here makes the *open* streaming tail typeset
  // instead of landing on CodeBlock (lang badge + raw source).
  { id: "math", langs: ["math", "latex", "tex"], structured: true, neverCodeBlock: true },
  {
    id: "answer",
    langs: ["answer", "result", "final"],
    structured: true,
    neverCodeBlock: true,
  },
  { id: "clock", langs: ["clock", "time"], structured: true, neverCodeBlock: true },
  { id: "mermaid", langs: ["mermaid"], structured: true, neverCodeBlock: false },
  {
    id: "chart",
    langs: ["chart", "vega", "vega-lite", "plot"],
    structured: true,
    neverCodeBlock: false,
  },
  {
    id: "geometry",
    langs: ["geometry"],
    structured: true,
    neverCodeBlock: true,
    fallback: "geometry",
  },
  {
    id: "graph",
    langs: ["graph"],
    structured: true,
    neverCodeBlock: true,
    fallback: "graph",
  },
  {
    id: "chemistry",
    langs: ["smiles", "chemistry"],
    structured: true,
    neverCodeBlock: true,
  },
  { id: "places", langs: ["places"], structured: true, neverCodeBlock: true },
  {
    id: "callout",
    langs: ["tip", "note", "warning", "info", "important", "callout"],
    structured: true,
    neverCodeBlock: false,
    fallback: "callout",
  },
  {
    id: "social",
    langs: ["twitter", "tweet", "x", "linkedin", "social"],
    structured: true,
    neverCodeBlock: false,
  },
  {
    id: "message",
    langs: ["sms", "message", "reply"],
    structured: true,
    neverCodeBlock: true,
  },
  // Not structured: `copy` and `sources` never reach the rich renderer, but
  // must not fall through to a syntax-highlighted code block either. `sources`
  // is emitted by the backend (web_search/formatting.py) and normally stripped
  // server-side before it reaches the client.
  { id: "copy", langs: ["copy"], structured: false, neverCodeBlock: true },
  { id: "sources", langs: ["sources"], structured: false, neverCodeBlock: true },
];

const BY_LANG = new Map<string, FenceSpec>();
for (const spec of FENCES) {
  for (const lang of spec.langs) BY_LANG.set(lang, spec);
}

function normalize(lang: string): string {
  return lang.trim().toLowerCase();
}

/** Resolve a fence language tag (including `callout-*`) to its spec. */
export function fenceSpecForLang(lang: string): FenceSpec | null {
  const l = normalize(lang);
  if (l.startsWith("callout-")) return BY_LANG.get("callout") ?? null;
  return BY_LANG.get(l) ?? null;
}

export function fenceIdForLang(lang: string): FenceId | null {
  return fenceSpecForLang(lang)?.id ?? null;
}

/** Routed through the rich fence renderer. */
export function isStructuredFenceLang(lang: string): boolean {
  return fenceSpecForLang(lang)?.structured ?? false;
}

/** Excluded from syntax-highlighted code rendering. */
export function isNeverCodeBlockLang(lang: string): boolean {
  return fenceSpecForLang(lang)?.neverCodeBlock ?? false;
}

/** How the crash-fallback renderer should degrade this fence, if specially. */
export function fallbackKindForLang(lang: string): FallbackKind | null {
  return fenceSpecForLang(lang)?.fallback ?? null;
}

/** Explicit ```math / ```latex / ```tex — never reinterpret as an answer pill. */
export function isMathFenceLang(lang: string): boolean {
  return fenceIdForLang(lang) === "math";
}

/** Display math or a diagram fence — not a syntax-highlighted code card. */
export function isMathDiagramLang(lang: string): boolean {
  const id = fenceIdForLang(lang);
  return id === "math" || id === "geometry" || id === "graph";
}
