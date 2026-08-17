import { estimateTokens, shouldShowDraftTokenHint } from "@/lib/estimateTokens";

describe("estimateTokens", () => {
  it("matches the API heuristic fixtures", () => {
    expect(estimateTokens("")).toBe(1);
    expect(estimateTokens("a".repeat(400))).toBe(111);
  });

  it("counts code fences denser than prose", () => {
    const plain = "a".repeat(400);
    const code = "```python\n" + "x = 1\n".repeat(40) + "```";
    expect(estimateTokens(code)).toBeGreaterThan(estimateTokens(plain));
  });

  it("hides the composer hint for short drafts", () => {
    expect(shouldShowDraftTokenHint(1)).toBe(false);
    expect(shouldShowDraftTokenHint(79)).toBe(false);
    expect(shouldShowDraftTokenHint(80)).toBe(true);
  });
});
