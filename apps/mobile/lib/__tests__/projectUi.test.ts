import { formatProjectListTitle, projectStatsLabels } from "@/lib/projectUi";

const t = (key: string) => key;

describe("projectUi", () => {
  it("uses vocabulary stats for language projects", () => {
    expect(projectStatsLabels("language", t).new).toBe("projects.stats.new");
  });

  it("uses trivia fact stats for trivia projects", () => {
    expect(projectStatsLabels("trivia", t).new).toBe("projects.stats.facts_new");
    expect(projectStatsLabels("trivia", t).learned).toBe("projects.stats.correct_total");
  });

  it("maps General list title for language and trivia", () => {
    expect(formatProjectListTitle("General", "language", t)).toBe("projects.list.general");
    expect(formatProjectListTitle("History", "trivia", t)).toBe("History");
  });
});
