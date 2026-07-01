import {
  englishTopicsDescription,
  sortEnglishTopics,
} from "@/lib/englishLearningTopics";

const t = (key: string) => key;

describe("englishLearningTopics", () => {
  it("builds a focus description", () => {
    expect(englishTopicsDescription(["vocabulary", "grammar"], t)).toBe(
      "Focus areas: projects.english_topics.vocabulary, projects.english_topics.grammar",
    );
  });

  it("sorts topics in display order", () => {
    expect(sortEnglishTopics(["speaking", "grammar", "vocabulary"])).toEqual([
      "vocabulary",
      "grammar",
      "speaking",
    ]);
  });
});
