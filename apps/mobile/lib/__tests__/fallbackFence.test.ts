import { classifyFallbackFence } from "@/lib/fallbackFence";

describe("classifyFallbackFence", () => {
  it("classifies callout fences as callouts with the parsed kind", () => {
    expect(classifyFallbackFence("callout-tip", "Try this at home")).toEqual({
      kind: "callout",
      calloutKind: "tip",
      body: "Try this at home",
    });
    expect(classifyFallbackFence("callout-warning", "Heads up")).toEqual({
      kind: "callout",
      calloutKind: "warning",
      body: "Heads up",
    });
  });

  it("treats a bare 'callout' lang as a callout (defaults to note kind)", () => {
    expect(classifyFallbackFence("callout", "Generic note")).toEqual({
      kind: "callout",
      calloutKind: "note",
      body: "Generic note",
    });
  });

  it("classifies non-callout langs as code (preserving the lang)", () => {
    expect(classifyFallbackFence("python", "print('hi')")).toEqual({
      kind: "code",
      lang: "python",
      code: "print('hi')",
    });
    // Rich structured langs stay as code in the fallback (raw source visible).
    expect(classifyFallbackFence("mermaid", "graph TD")).toEqual({
      kind: "code",
      lang: "mermaid",
      code: "graph TD",
    });
    expect(classifyFallbackFence("chart", '{"data":[]}')).toEqual({
      kind: "code",
      lang: "chart",
      code: '{"data":[]}',
    });
  });

  it("trims trailing newlines and whitespace from the body/code", () => {
    expect(classifyFallbackFence("callout-note", "Body\n\n")).toEqual({
      kind: "callout",
      calloutKind: "note",
      body: "Body",
    });
    expect(classifyFallbackFence("js", "code\n")).toEqual({
      kind: "code",
      lang: "js",
      code: "code",
    });
  });

  it("handles missing lang (plain code block)", () => {
    expect(classifyFallbackFence(undefined, "bare code")).toEqual({
      kind: "code",
      lang: "",
      code: "bare code",
    });
  });
});
