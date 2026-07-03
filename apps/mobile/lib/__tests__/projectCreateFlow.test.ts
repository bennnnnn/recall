import {
  createStepProgress,
  resolveProjectDescription,
  resolveProjectTitle,
  programmingProjectTitle,
} from "@/lib/projectCreateFlow";

const t = (key: string) => key;

describe("projectCreateFlow", () => {
  it("tracks programming as two steps", () => {
    expect(createStepProgress("stack", "programming")).toEqual({ current: 2, total: 2 });
  });

  it("tracks english as three steps ending on daily", () => {
    expect(createStepProgress("level", "language")).toEqual({ current: 2, total: 3 });
    expect(createStepProgress("daily", "language")).toEqual({ current: 3, total: 3 });
  });

  it("tracks trivia as three steps ending on daily", () => {
    expect(createStepProgress("topics", "trivia")).toEqual({ current: 2, total: 3 });
    expect(createStepProgress("daily", "trivia")).toEqual({ current: 3, total: 3 });
  });

  it("builds programming project title from language", () => {
    expect(programmingProjectTitle("python", t)).toBe("Python · projects.kind.programming");
  });

  it("drops description when it matches title", () => {
    expect(resolveProjectDescription("Calculus", "Calculus")).toBe("");
    expect(resolveProjectDescription("Calculus", "Exam prep")).toBe("Exam prep");
  });

  it("uses title input when provided", () => {
    expect(resolveProjectTitle("Calculus", "math", "level1", null, t)).toBe("Calculus");
  });
});
