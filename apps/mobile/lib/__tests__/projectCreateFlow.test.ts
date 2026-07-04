import {
  createStepProgress,
  resolveProjectDescription,
  resolveProjectTitle,
  englishProjectTitle,
} from "@/lib/projectCreateFlow";

const t = (key: string) => key;

describe("projectCreateFlow", () => {
  it("tracks english as three steps ending on daily", () => {
    expect(createStepProgress("level", "language")).toEqual({ current: 2, total: 3 });
    expect(createStepProgress("daily", "language")).toEqual({ current: 3, total: 3 });
  });

  it("tracks trivia as three steps ending on daily", () => {
    expect(createStepProgress("topics", "trivia")).toEqual({ current: 2, total: 3 });
    expect(createStepProgress("daily", "trivia")).toEqual({ current: 3, total: 3 });
  });

  it("builds english project title from level", () => {
    expect(englishProjectTitle("level2", t)).toBe("projects.kind.language · Elementary");
  });

  it("drops description when it matches title", () => {
    expect(resolveProjectDescription("Calculus", "Calculus")).toBe("");
    expect(resolveProjectDescription("Calculus", "Exam prep")).toBe("Exam prep");
  });

  it("uses title input when provided", () => {
    expect(resolveProjectTitle("Calculus", "math", "level1", t)).toBe("Calculus");
  });
});
