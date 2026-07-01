import { formatProjectListTitle, projectStatsLabels } from "@/lib/projectUi";

const t = (key: string) => key;

describe("projectUi", () => {
  it("uses vocabulary stats for language projects", () => {
    expect(projectStatsLabels("language", t).new).toBe("projects.stats.new");
  });

  it("uses concept stats for math projects", () => {
    expect(projectStatsLabels("math", t).new).toBe("projects.stats.concepts_new");
    expect(projectStatsLabels("math", t).learned).toBe("projects.stats.concepts_mastered");
  });

  it("maps General list title to Topics for math", () => {
    expect(formatProjectListTitle("General", "math", t)).toBe("projects.list.topics");
    expect(formatProjectListTitle("Limits", "math", t)).toBe("Limits");
  });
});
