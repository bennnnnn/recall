import { classifyFence, classifyOpenFencePreview } from "@/lib/fenceDispatch";

describe("classifyFence — explicit tags win", () => {
  it.each([
    ["python", "x = 2", "code"],
    ["javascript", "const x = 2", "code"],
    ["rust", "let x = 2;", "code"],
    ["answer", "x = 2", "answer"],
    ["math", "x^2 + 1", "math"],
    ["latex", String.raw`\frac{x^2}{2}`, "math"],
    ["geometry", '{"type":"square"}', "rich"],
    ["smiles", "CCO", "rich"],
    ["copy", "120", "answer"],
    ["", "120", "answer"],
    ["", "x = 2 or x = -2", "answer"],
    ["image", '{"prompt":"a cat"}', "hide"],
  ] as const)("%s %j → %s", (lang, body, kind) => {
    expect(classifyFence(lang, body).kind).toBe(kind);
  });

  it("does not run the math-answer heuristic on tagged source code", () => {
    expect(classifyOpenFencePreview("python", "x = 2")).toBe("code");
    expect(classifyOpenFencePreview("javascript", "x = 2")).toBe("code");
    expect(classifyOpenFencePreview("math", String.raw`\frac{x^2}{2}`)).toBe("math");
    expect(classifyOpenFencePreview("", "x = 2")).toBe("answer");
  });
});
