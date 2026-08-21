import {
  FENCES,
  fenceIdForLang,
  isNeverCodeBlockLang,
  isStructuredFenceLang,
  fallbackKindForLang,
  isMathFenceLang,
  isMathDiagramLang,
} from "@/lib/fenceRegistry";

/**
 * Characterization test: the registry must reproduce the pre-existing language
 * sets exactly, plus deliberate additions. These literals started as the lists
 * in richBlocks.ts (STRUCTURED_LANGS) and copyBlock.ts (isExplicitCodeLang's
 * exclusions) before the registry existed. `latex`/`tex` were added as aliases
 * of `math` so an open streaming ```latex fence typesets instead of CodeBlock.
 * If a future change to FENCES alters what renders, it fails here rather than
 * silently in the app.
 */

const LEGACY_STRUCTURED = [
  "email",
  "quote",
  "blockquote",
  "compare",
  "comparison",
  "pros",
  "kv",
  "keyvalue",
  "fields",
  "steps",
  "step",
  "details",
  "collapse",
  "summary",
  "math",
  "latex",
  "tex",
  "answer",
  "result",
  "final",
  "clock",
  "time",
  "mermaid",
  "chart",
  "vega",
  "vega-lite",
  "plot",
  "geometry",
  "graph",
  "smiles",
  "chemistry",
  "molecule3d",
  "mol3d",
  "3dmol",
  "places",
  // callout langs
  "tip",
  "note",
  "warning",
  "info",
  "important",
  "callout",
  // social langs
  "twitter",
  "tweet",
  "x",
  "linkedin",
  "social",
  // message langs
  "sms",
  "message",
  "reply",
];

const LEGACY_NEVER_CODE_BLOCK = [
  "copy",
  "message",
  "email",
  "sms",
  "reply",
  "clock",
  "time",
  "sources",
  "places",
  "graph",
  "geometry",
  "smiles",
  "chemistry",
  "molecule3d",
  "mol3d",
  "3dmol",
  "math",
  "latex",
  "tex",
  "answer",
  "result",
  "final",
];

describe("fence registry reproduces the legacy language sets", () => {
  it.each(LEGACY_STRUCTURED)("%s is structured", (lang) => {
    expect(isStructuredFenceLang(lang)).toBe(true);
  });

  it("marks nothing else as structured", () => {
    const registered = FENCES.filter((f) => f.structured).flatMap((f) => f.langs);
    expect([...registered].sort()).toEqual([...LEGACY_STRUCTURED].sort());
  });

  it.each(LEGACY_NEVER_CODE_BLOCK)("%s is never a code block", (lang) => {
    expect(isNeverCodeBlockLang(lang)).toBe(true);
  });

  it("marks nothing else as never-code-block", () => {
    const registered = FENCES.filter((f) => f.neverCodeBlock).flatMap((f) => f.langs);
    expect([...registered].sort()).toEqual([...LEGACY_NEVER_CODE_BLOCK].sort());
  });
});

describe("fence registry lookups", () => {
  it("resolves callout-* variants to the callout fence", () => {
    expect(fenceIdForLang("callout-tip")).toBe("callout");
    expect(fenceIdForLang("callout-warning")).toBe("callout");
    expect(isStructuredFenceLang("callout-note")).toBe(true);
  });

  it("is case and whitespace insensitive", () => {
    expect(fenceIdForLang("  GEOMETRY ")).toBe("geometry");
    expect(isStructuredFenceLang(" Mermaid")).toBe(true);
  });

  it("returns null for unknown and code languages", () => {
    for (const lang of ["python", "javascript", "json", "", "rust"]) {
      expect(fenceIdForLang(lang)).toBeNull();
      expect(isStructuredFenceLang(lang)).toBe(false);
      expect(isNeverCodeBlockLang(lang)).toBe(false);
    }
  });

  it("keeps copy and sources out of the rich renderer but out of code blocks too", () => {
    for (const lang of ["copy", "sources"]) {
      expect(isStructuredFenceLang(lang)).toBe(false);
      expect(isNeverCodeBlockLang(lang)).toBe(true);
    }
  });

  it("declares crash-fallback handling only for callout, geometry and graph", () => {
    expect(fallbackKindForLang("callout-tip")).toBe("callout");
    expect(fallbackKindForLang("geometry")).toBe("geometry");
    expect(fallbackKindForLang("graph")).toBe("graph");
    expect(fallbackKindForLang("mermaid")).toBeNull();
    expect(fallbackKindForLang("chart")).toBeNull();
  });

  it("has no duplicate language tag across fences", () => {
    const all = FENCES.flatMap((f) => f.langs);
    expect(new Set(all).size).toBe(all.length);
  });

  it("treats latex/tex as math fence aliases (open-stream typeset, not CodeBlock)", () => {
    expect(fenceIdForLang("latex")).toBe("math");
    expect(fenceIdForLang("tex")).toBe("math");
    expect(isMathFenceLang("latex")).toBe(true);
    expect(isMathDiagramLang("geometry")).toBe(true);
    expect(isMathDiagramLang("python")).toBe(false);
  });
});
