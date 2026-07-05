import {
  looksLikeLatexFence,
  retagMathAndDiagramFences,
} from "@/lib/mathFenceRetag";

describe("mathFenceRetag", () => {
  it("retags latex fence to math", () => {
    const input = "```latex\n\\text{Area} = 8 \\times 5\n```";
    const out = retagMathAndDiagramFences(input);
    expect(out).toContain("```math");
  });

  it("does not retag json geometry to geometry fence", () => {
    const input = '```json\n{"type":"square","side":5,"unit":"cm"}\n```';
    const out = retagMathAndDiagramFences(input);
    expect(out).toContain("```json");
    expect(out).not.toContain("```geometry");
  });

  it("detects latex body", () => {
    expect(looksLikeLatexFence("\\text{Area} = L \\times W")).toBe(true);
    expect(looksLikeLatexFence(String.raw`x = \pm \sqrt{4}`)).toBe(true);
  });

  it("retags plain fences with algebra or latex to math", () => {
    const input = [
      "Step 1:",
      "```",
      "x^2 + 2 - 2 = 6 - 2",
      "```",
      "```",
      String.raw`x = \pm \sqrt{4}`,
      "```",
    ].join("\n");
    const out = retagMathAndDiagramFences(input);
    expect(out).toContain("```math");
    expect(out).not.toMatch(/```\n\s*x\^2/);
  });
});
