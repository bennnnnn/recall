import {
  fenceContentAsGeometry,
  fenceContentAsGraph,
  looksLikeLatexFence,
  retagMathAndDiagramFences,
} from "@/lib/mathFenceRetag";

describe("mathFenceRetag", () => {
  it("retags json square to geometry fence", () => {
    const input = '```json\n{"type":"square","side":5,"unit":"cm"}\n```';
    const out = retagMathAndDiagramFences(input);
    expect(out).toContain("```geometry");
    expect(fenceContentAsGeometry('{"type":"square","side":5}')).toBe(true);
  });

  it("retags json right_triangle to geometry fence", () => {
    const input =
      '```json\n{"type":"right_triangle","base":6,"height":4,"unit":"cm","show_hypotenuse":true}\n```';
    const out = retagMathAndDiagramFences(input);
    expect(out).toContain("```geometry");
    expect(out).toContain("right_triangle");
    expect(fenceContentAsGeometry('{"type":"right_triangle","base":6,"height":4}')).toBe(true);
  });

  it("retags json triangle to geometry fence", () => {
    const input =
      '```json\n{"type":"triangle","base":8,"height":5,"unit":"cm"}\n```';
    const out = retagMathAndDiagramFences(input);
    expect(out).toContain("```geometry");
    expect(fenceContentAsGeometry('{"type":"triangle","base":8,"height":5}')).toBe(true);
  });

  it("retags json rectangle to geometry fence", () => {
    const input =
      '```json\n{"type":"rectangle","width":6,"height":4,"unit":"cm"}\n```';
    const out = retagMathAndDiagramFences(input);
    expect(out).toContain("```geometry");
    expect(out).not.toContain("```json");
  });

  it("retags latex fence to math", () => {
    const input = "```latex\n\\text{Area} = 8 \\times 5\n```";
    const out = retagMathAndDiagramFences(input);
    expect(out).toContain("```math");
  });

  it("detects geometry json body", () => {
    const body = '{"type":"rectangle","width":6,"height":4}';
    expect(fenceContentAsGeometry(body)).toBe(true);
    expect(fenceContentAsGraph(body)).toBe(false);
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
