import {
  createStepProgress,
  resolveProjectDescription,
  resolveProjectTitle,
} from "@/lib/projectCreateFlow";

const t = (key: string) => key;

describe("projectCreateFlow", () => {
  it("tracks math as two steps", () => {
    expect(createStepProgress("goal", "math")).toEqual({ current: 2, total: 2 });
  });

  it("tracks english as three steps ending on topics", () => {
    expect(createStepProgress("topics", "language")).toEqual({ current: 3, total: 3 });
  });

  it("drops description when it matches title", () => {
    expect(resolveProjectDescription("Calculus", "Calculus")).toBe("");
    expect(resolveProjectDescription("Calculus", "Exam prep")).toBe("Exam prep");
  });

  it("uses title input when provided", () => {
    expect(resolveProjectTitle("Calculus", "math", "level1", null, t)).toBe("Calculus");
  });
});
