import { messagesLookLikeMath, textLooksLikeMath } from "@/lib/mathComposerIntent";

describe("textLooksLikeMath", () => {
  it("detects latex, glyphs, and homework verbs", () => {
    expect(textLooksLikeMath("$\\sqrt{9}$")).toBe(true);
    expect(textLooksLikeMath("solve x^2 = 9")).toBe(true);
    expect(textLooksLikeMath("√9")).toBe(true);
    expect(textLooksLikeMath("```math\n1+1\n```")).toBe(true);
  });

  it("does not treat ordinary chat as math", () => {
    expect(textLooksLikeMath("")).toBe(false);
    expect(textLooksLikeMath("what's the weather")).toBe(false);
    expect(textLooksLikeMath("I'm going later")).toBe(false);
  });
});

describe("messagesLookLikeMath", () => {
  it("looks at recent messages only", () => {
    expect(messagesLookLikeMath(["hi", "√9 = 3"])).toBe(true);
    expect(messagesLookLikeMath(["hello", "how are you"])).toBe(false);
  });
});
