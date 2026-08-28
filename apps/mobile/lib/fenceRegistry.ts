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
 *
 * `owner` classifies who may emit the fence on new turns:
 * - model: the active prompt may produce this
 * - server: Recall attaches or rewrites this after the stream
 * - legacy: still rendered for history; the prompt must not choose it for layout
 *
 * Calendar / reminder / settings / vocab-quiz control fences are parsed
 * outside this registry (see assistantMessageContent.ts).
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
  | "learning_launch"
  | "math"
  | "mermaid"
  | "message"
  | "molecule"
  | "molecule3d"
  | "places"
  | "quote"
  | "social"
  | "sources"
  | "steps";

export type FenceOwner = "model" | "server" | "legacy";

export type FallbackKind =
  | "callout"
  | "geometry"
  | "graph"
  | "answer"
  | "sources"
  | "places"
  | "visual";

export type FenceSpec = {
  id: FenceId;
  /** Every language tag that resolves to this fence. */
  langs: readonly string[];
  /** Routed through the rich fence renderer (was `STRUCTURED_LANGS`). */
  structured: boolean;
  /** Never rendered as a syntax-highlighted code block (was copyBlock's list). */
  neverCodeBlock: boolean;
  /** Who may emit this fence on new turns. */
  owner: FenceOwner;
  /** How the crash-fallback renderer degrades this fence, when not plain code. */
  fallback?: FallbackKind;
};

export const FENCES: readonly FenceSpec[] = [
  { id: "email", langs: ["email"], structured: true, neverCodeBlock: true, owner: "model" },
  {
    id: "quote",
    langs: ["quote", "blockquote"],
    structured: true,
    neverCodeBlock: false,
    owner: "legacy",
  },
  {
    id: "comparison",
    langs: ["compare", "comparison", "pros"],
    structured: true,
    neverCodeBlock: false,
    owner: "legacy",
  },
  {
    id: "keyvalue",
    langs: ["kv", "keyvalue", "fields"],
    structured: true,
    neverCodeBlock: false,
    owner: "legacy",
  },
  {
    id: "steps",
    langs: ["steps", "step"],
    structured: true,
    neverCodeBlock: false,
    owner: "legacy",
  },
  {
    id: "collapsible",
    langs: ["details", "collapse", "summary"],
    structured: true,
    neverCodeBlock: false,
    owner: "legacy",
  },
  // `latex`/`tex` are aliases of `math`. The model is told never to emit
  // those tags, but it drifts; the settled path already retags closed
  // fences. Registering them here makes the *open* streaming tail typeset
  // instead of landing on CodeBlock (lang badge + raw source).
  {
    id: "math",
    langs: ["math", "latex", "tex"],
    structured: true,
    neverCodeBlock: true,
    owner: "model",
  },
  {
    id: "answer",
    langs: ["answer", "result", "final"],
    structured: true,
    neverCodeBlock: true,
    owner: "server",
    fallback: "answer",
  },
  {
    id: "clock",
    langs: ["clock", "time"],
    structured: true,
    neverCodeBlock: true,
    owner: "legacy",
  },
  {
    id: "mermaid",
    langs: ["mermaid"],
    structured: true,
    neverCodeBlock: false,
    owner: "model",
    fallback: "visual",
  },
  {
    id: "chart",
    langs: ["chart", "vega", "vega-lite", "plot"],
    structured: true,
    neverCodeBlock: false,
    owner: "model",
    fallback: "visual",
  },
  {
    id: "geometry",
    langs: ["geometry"],
    structured: true,
    neverCodeBlock: true,
    owner: "server",
    fallback: "geometry",
  },
  {
    id: "graph",
    langs: ["graph"],
    structured: true,
    neverCodeBlock: true,
    owner: "server",
    fallback: "graph",
  },
  {
    id: "chemistry",
    langs: ["smiles", "chemistry"],
    structured: true,
    neverCodeBlock: true,
    owner: "model",
    fallback: "visual",
  },
  // Display-only: preprocessor collapses adjacent smiles + molecule3d.
  // The model/server must not emit this tag; persist still stores both fences.
  {
    id: "molecule",
    langs: ["molecule"],
    structured: true,
    neverCodeBlock: true,
    owner: "server",
    fallback: "visual",
  },
  {
    id: "molecule3d",
    langs: ["molecule3d", "mol3d", "3dmol"],
    structured: true,
    neverCodeBlock: true,
    owner: "server",
    fallback: "visual",
  },
  {
    id: "places",
    langs: ["places"],
    structured: true,
    neverCodeBlock: true,
    owner: "server",
    fallback: "places",
  },
  {
    id: "callout",
    langs: ["tip", "note", "warning", "info", "important", "callout"],
    structured: true,
    neverCodeBlock: false,
    owner: "legacy",
    fallback: "callout",
  },
  {
    id: "social",
    langs: ["twitter", "tweet", "x", "linkedin", "social"],
    structured: true,
    neverCodeBlock: false,
    owner: "model",
  },
  {
    id: "message",
    langs: ["sms", "message", "reply"],
    structured: true,
    neverCodeBlock: true,
    owner: "model",
  },
  // Not structured: `copy` and `sources` never reach the rich renderer, but
  // must not fall through to a syntax-highlighted code block either. `sources`
  // is attached by the backend (web_search/formatting.py) onto persisted
  // assistant text and the live `done.final_content`; clients strip it and
  // render the `search_sources` field / parsed fence as a chip.
  { id: "copy", langs: ["copy"], structured: false, neverCodeBlock: true, owner: "model" },
  {
    id: "sources",
    langs: ["sources"],
    structured: false,
    neverCodeBlock: true,
    owner: "server",
    fallback: "sources",
  },
  {
    id: "learning_launch",
    langs: ["learning_launch"],
    structured: false,
    neverCodeBlock: true,
    owner: "server",
  },
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
