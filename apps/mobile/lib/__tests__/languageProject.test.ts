import { languageLabel, speechLocale } from "@/lib/i18n/languages";
import { findLanguageProject } from "@/lib/projects/languageProject";
import type { Project } from "@/lib/api";

const english: Project = {
  id: "p1",
  title: "English · Beginner",
  description: null,
  kind: "language",
  target_language: "en",
  native_language: null,
  level: "level1",
  daily_goal: 10,
  archived: false,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const spanish: Project = {
  ...english,
  id: "p2",
  title: "Spanish",
  target_language: "es",
};

describe("languageProject", () => {
  it("finds an existing language project by target language", () => {
    expect(findLanguageProject([english, spanish], "en")).toEqual(english);
    expect(findLanguageProject([english, spanish], "es")).toEqual(spanish);
  });

  it("returns undefined when no match", () => {
    expect(findLanguageProject([english], "fr")).toBeUndefined();
    expect(findLanguageProject([], "en")).toBeUndefined();
  });

  it("maps target language to label and TTS locale", () => {
    expect(languageLabel("es")).toBe("Español");
    expect(speechLocale("es")).toBe("es-ES");
    expect(speechLocale("am")).toBe("am-ET");
    expect(speechLocale("ja")).toBe("en-US");
  });
});
