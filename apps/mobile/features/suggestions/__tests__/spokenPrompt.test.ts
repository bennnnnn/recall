import { spokenPrompt } from "@/features/suggestions/model/promptMath";

describe("spokenPrompt", () => {
  it("reads a maths follow-up in words, not LaTeX source", () => {
    const spoken = spokenPrompt(String.raw`What if $v_f = 36\text{ km/h}$?`);
    expect(spoken).not.toMatch(/[\\$_{}]/);
    expect(spoken).toBe("What if v subscript f = 36 km/h?");
  });

  it("reads a bare caret the way the row draws it", () => {
    const spoken = spokenPrompt("Why does X^2 = 9 have two solutions?");
    expect(spoken).toBe("Why does X squared = 9 have two solutions?");
  });

  it("leaves a plain question as it is", () => {
    expect(spokenPrompt("How do I find mass from moles?")).toBe("How do I find mass from moles?");
  });
});
