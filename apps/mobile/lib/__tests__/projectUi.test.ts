import { formatProjectListTitle, projectStatsLabels } from "@/lib/projects/projectUi";

const t = (key: string) => key;

describe("projectUi", () => {
  it("uses vocabulary stats for language projects", () => {
    expect(projectStatsLabels("language", t).new).toBe("projects.stats.new");
  });

  it("maps General list title for language", () => {
    expect(formatProjectListTitle("General", "language", t)).toBe("projects.list.general");
    expect(formatProjectListTitle("History", "language", t)).toBe("History");
  });
});
