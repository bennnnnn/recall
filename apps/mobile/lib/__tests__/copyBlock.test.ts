import {
  isAnswerLang,
  isCopyLang,
  looksLikeCode,
  looksLikeMathAnswer,
  looksLikeSendDeliverable,
  shouldRenderAsCopyBlock,
  shouldRenderAsCodeBlock,
} from "@/lib/copyBlock";

describe("copyBlock heuristics", () => {
  it("recognizes copy fence languages", () => {
    expect(isCopyLang("copy")).toBe(true);
    expect(isCopyLang("EMAIL")).toBe(true);
    expect(isCopyLang("python")).toBe(false);
  });

  it("detects source code vs prose", () => {
    expect(looksLikeCode("def hello():\n    print('hi')")).toBe(true);
    expect(looksLikeCode("Hi team,\n\nThanks for the update.\n\nBest,")).toBe(false);
  });

  it("routes email drafts to copy block", () => {
    const draft = `Subject: Follow up\n\nHi Alex,\n\nJust checking in.\n\nThanks,\nSam`;
    expect(looksLikeSendDeliverable(draft)).toBe(true);
    expect(shouldRenderAsCopyBlock("email", draft)).toBe(true);
    expect(shouldRenderAsCodeBlock("email", draft)).toBe(false);
  });

  it("routes python fences to code block", () => {
    const code = "def add(a, b):\n    return a + b";
    expect(shouldRenderAsCodeBlock("python", code)).toBe(true);
    expect(shouldRenderAsCopyBlock("python", code)).toBe(false);
  });

  it("does not treat advisory prose as copy deliverable", () => {
    const advice =
      "As a software engineer, Python is a solid choice for prototyping. JavaScript is great for the frontend.";
    expect(looksLikeSendDeliverable(advice)).toBe(false);
    expect(shouldRenderAsCopyBlock("copy", advice)).toBe(false);
  });

  it("treats short numeric finals as math answers, not Copy", () => {
    expect(looksLikeMathAnswer("120")).toBe(true);
    expect(looksLikeMathAnswer("$x = 3$")).toBe(true);
    expect(looksLikeMathAnswer("\\boxed{120}")).toBe(true);
    expect(looksLikeMathAnswer("x = 2")).toBe(true);
    expect(looksLikeMathAnswer("0! = 1")).toBe(false);
    expect(isAnswerLang("answer")).toBe(true);
    expect(shouldRenderAsCopyBlock("copy", "120")).toBe(false);
    expect(shouldRenderAsCopyBlock("answer", "120")).toBe(false);
  });
});
