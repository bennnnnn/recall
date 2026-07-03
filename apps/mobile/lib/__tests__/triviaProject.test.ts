import { encodeTriviaTopics, parseTriviaTopics, triviaTopicLabel } from "@/lib/triviaTopics";
import { findTriviaProject } from "@/lib/triviaProject";
import type { Project } from "@/lib/api";

const t = (key: string) => key;

describe("triviaTopics", () => {
  it("round-trips topic ids in description", () => {
    expect(parseTriviaTopics(encodeTriviaTopics(["history", "science"]))).toEqual([
      "history",
      "science",
    ]);
  });

  it("labels known topics via i18n keys", () => {
    expect(triviaTopicLabel("history", t)).toBe("projects.trivia.topic.history");
  });
});

describe("triviaProject", () => {
  const trivia: Project = {
    id: "t1",
    title: "General knowledge",
    description: "history,science",
    kind: "trivia",
    target_language: "en",
    native_language: null,
    level: "level1",
    daily_goal: 10,
    archived: false,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  };

  it("finds the trivia project", () => {
    expect(findTriviaProject([trivia])).toEqual(trivia);
    expect(findTriviaProject([])).toBeUndefined();
  });
});
