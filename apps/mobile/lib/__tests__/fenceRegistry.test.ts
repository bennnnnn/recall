import {
  FENCES,
  fenceIdForLang,
  isNeverCodeBlockLang,
  isStructuredFenceLang,
  fallbackKindForLang,
  isMathFenceLang,
  isMathDiagramLang,
  isAnswerFenceLang,
  isChartFenceLang,
  isControlFenceLang,
  isVisualDiagramFenceLang,
  isDiagramFenceId,
  shouldLiftFenceOutOfList,
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
  "molecule",
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
  "facebook",
  "fb",
  "instagram",
  "insta",
  "ig",
  "tiktok",
  "threads",
  "caption",
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
  "twitter",
  "tweet",
  "x",
  "linkedin",
  "facebook",
  "fb",
  "instagram",
  "insta",
  "ig",
  "tiktok",
  "threads",
  "caption",
  "social",
  "clock",
  "time",
  "sources",
  "places",
  "graph",
  "geometry",
  "smiles",
  "chemistry",
  "molecule",
  "molecule3d",
  "mol3d",
  "3dmol",
  "math",
  "latex",
  "tex",
  "answer",
  "result",
  "final",
  "learning_launch",
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

  it("declares crash-fallback handling for callout, diagrams, answers, and transport", () => {
    expect(fallbackKindForLang("callout-tip")).toBe("callout");
    expect(fallbackKindForLang("geometry")).toBe("geometry");
    expect(fallbackKindForLang("graph")).toBe("graph");
    expect(fallbackKindForLang("answer")).toBe("answer");
    expect(fallbackKindForLang("sources")).toBe("sources");
    expect(fallbackKindForLang("places")).toBe("places");
    expect(fallbackKindForLang("mermaid")).toBe("visual");
    expect(fallbackKindForLang("chart")).toBe("visual");
    expect(fallbackKindForLang("python")).toBeNull();
  });

  it("marks every fence as model, server, or legacy", () => {
    for (const spec of FENCES) {
      expect(["model", "server", "legacy"]).toContain(spec.owner);
    }
    expect(FENCES.find((f) => f.id === "email")?.owner).toBe("model");
    expect(FENCES.find((f) => f.id === "answer")?.owner).toBe("server");
    expect(FENCES.find((f) => f.id === "steps")?.owner).toBe("legacy");
    expect(FENCES.find((f) => f.id === "molecule")?.owner).toBe("server");
    expect(fenceIdForLang("molecule")).toBe("molecule");
    expect(fenceIdForLang("molecule3d")).toBe("molecule3d");
  });

  it("has no duplicate language tag across fences", () => {
    const all = FENCES.flatMap((f) => f.langs);
    expect(new Set(all).size).toBe(all.length);
  });

  it("does not add fence types without an explicit contract change", () => {
    expect(FENCES.map((spec) => spec.id).sort()).toEqual([
      "answer",
      "callout",
      "chart",
      "chemistry",
      "clock",
      "collapsible",
      "comparison",
      "copy",
      "email",
      "geometry",
      "graph",
      "keyvalue",
      "learning_launch",
      "math",
      "mermaid",
      "message",
      "molecule",
      "molecule3d",
      "places",
      "quote",
      "social",
      "sources",
      "steps",
    ]);
    expect(
      FENCES.filter((spec) => spec.owner === "model").map((spec) => spec.id).sort(),
    ).toEqual([
      "chart",
      "chemistry",
      "copy",
      "email",
      "math",
      "mermaid",
      "message",
      "places",
      "social",
    ]);
  });

  it("treats latex/tex as math fence aliases (open-stream typeset, not CodeBlock)", () => {
    expect(fenceIdForLang("latex")).toBe("math");
    expect(fenceIdForLang("tex")).toBe("math");
    expect(isMathFenceLang("latex")).toBe(true);
    expect(isMathDiagramLang("geometry")).toBe(true);
    expect(isMathDiagramLang("python")).toBe(false);
  });
});

describe("fence registry round-trip (render, copy, fallback)", () => {
  it("every registered id has an explicit render slot", () => {
    const renderSlot: Record<(typeof FENCES)[number]["id"], "component" | "hidden"> = {
      email: "component",
      quote: "component",
      comparison: "component",
      keyvalue: "component",
      steps: "component",
      collapsible: "component",
      math: "component",
      answer: "component",
      clock: "component",
      mermaid: "component",
      chart: "component",
      geometry: "component",
      graph: "component",
      chemistry: "component",
      molecule: "component",
      molecule3d: "component",
      places: "component",
      callout: "component",
      social: "component",
      message: "component",
      copy: "hidden",
      sources: "hidden",
      learning_launch: "hidden",
    };
    for (const spec of FENCES) {
      expect(renderSlot[spec.id]).toBe(spec.structured ? "component" : "hidden");
    }
  });

  it("copy/speech routing derives from the registry, not parallel lang lists", () => {
    expect(isChartFenceLang("vega-lite")).toBe(true);
    expect(isAnswerFenceLang("result")).toBe(true);
    expect(isVisualDiagramFenceLang("smiles")).toBe(true);
    expect(isVisualDiagramFenceLang("chart")).toBe(false);
    expect(isControlFenceLang("sources")).toBe(true);
    expect(isControlFenceLang("reminder")).toBe(true);
    expect(isControlFenceLang("vocab_quiz")).toBe(true);
    expect(isControlFenceLang("python")).toBe(false);
    expect(isDiagramFenceId("mermaid")).toBe(true);
    expect(shouldLiftFenceOutOfList("latex")).toBe(true);
    expect(shouldLiftFenceOutOfList("python")).toBe(false);
  });

  it("every fence's fallback kind matches the registry declaration", () => {
    for (const spec of FENCES) {
      expect(fallbackKindForLang(spec.langs[0]!)).toBe(spec.fallback ?? null);
    }
  });
});
