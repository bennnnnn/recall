import {
  CREATE_DEFAULT_LEVEL,
  createStepProgress,
  canAddLearningProject,
  resolveProjectDescription,
  resolveProjectTitle,
  languageClassTitle,
  languageProjectTitle,
} from "@/lib/projects/projectCreateFlow";
import type { Project } from "@/lib/api";

const t = (key: string) => key;

describe("projectCreateFlow", () => {
  it("tracks language as two steps ending on daily", () => {
    expect(createStepProgress("language", "language")).toEqual({ current: 1, total: 2 });
    expect(createStepProgress("daily", "language")).toEqual({ current: 2, total: 2 });
  });

  it("uses the language label as the class title on create", () => {
    expect(languageClassTitle("es")).toBe("Español");
    expect(languageClassTitle("en")).toBe("English");
    expect(CREATE_DEFAULT_LEVEL).toBe("level1");
  });

  it("builds settings title from level and target", () => {
    expect(languageProjectTitle("level2", "es")).toBe("Español · Elementary");
    expect(languageProjectTitle("level1", "en")).toBe("English · Beginner");
  });

  it("drops description when it matches title", () => {
    expect(resolveProjectDescription("Calculus", "Calculus")).toBe("");
    expect(resolveProjectDescription("Calculus", "Exam prep")).toBe("Exam prep");
  });

  it("uses title input when provided", () => {
    expect(resolveProjectTitle("Spanish class", "language", "level1", t)).toBe("Spanish class");
  });

  it("falls back to the language label without a level suffix", () => {
    expect(resolveProjectTitle("", "language", "level3", t)).toBe("English");
  });

  it("allows add learning until English and Spanish exist", () => {
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
    const spanish: Project = { ...english, id: "2", title: "Spanish", target_language: "es" };
    expect(canAddLearningProject([])).toBe(true);
    expect(canAddLearningProject([english])).toBe(true);
    expect(canAddLearningProject([english, spanish])).toBe(false);
    expect(canAddLearningProject([english, { ...spanish, archived: true }])).toBe(true);
  });
});
