import {
  createStepProgress,
  canAddLearningProject,
  resolveProjectDescription,
  resolveProjectTitle,
  englishProjectTitle,
} from "@/lib/projectCreateFlow";
import type { Project } from "@/lib/api";

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
    expect(resolveProjectTitle("World facts", "trivia", "level1", t)).toBe("World facts");
  });

  it("allows add learning until both english and trivia exist", () => {
    const english: Project = {
      id: "1",
      title: "English",
      description: "",
      kind: "language",
      level: "level1",
      target_language: "en",
      native_language: null,
      daily_goal: 5,
      archived: false,
      created_at: "",
      updated_at: "",
    };
    const trivia: Project = {
      id: "2",
      title: "General knowledge",
      description: "history,science",
      kind: "trivia",
      level: "level1",
      target_language: "en",
      native_language: null,
      daily_goal: 5,
      archived: false,
      created_at: "",
      updated_at: "",
    };
    expect(canAddLearningProject([])).toBe(true);
    expect(canAddLearningProject([english])).toBe(true);
    expect(canAddLearningProject([trivia])).toBe(true);
    expect(canAddLearningProject([english, trivia])).toBe(false);
    expect(canAddLearningProject([english, { ...trivia, archived: true }])).toBe(true);
  });
});
